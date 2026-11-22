# Reproducible Wine/Proton recipes

> **Status: two paths are verified, the rest are not.** The maintainer ran §3
> (Heroic + Proton-GE) on the real GOG install on 2026-11-21 and the game
> reached its main menu and played; on 2026-11-22 plain `wine` 11.21 reached the
> main menu inside a Wine virtual desktop, which the launcher now starts by
> default. Both runs are recorded in [`docs/verification.md`](verification.md);
> the checklist item stays unticked until the maintainer ticks it. Everything
> else below is a copy-paste start point a second machine should be able to
> follow — its "expected output" blocks describe what a correct run *would*
> show, not what has been observed.

---

## Start here: plain Wine needs a 640x480 display — the launcher starts a virtual desktop

**If `Disciple.exe` dies with an access violation at `0059559E`, the display
mode is the problem, not your INI.** The game asks for 640×480 at 8 bits per
pixel; plain Wine refuses that mode change when the display offers no 640x480
resolution, and the game then faults. Put it in front of a 640x480 mode — a Wine
virtual desktop is the cheapest way — and it reaches its own intro and menu.

**The launcher now does that for you.** On plain `wine` it runs the game inside
a virtual desktop:

```
wine explorer /desktop=Disciples,640x480 Exe/Disciple.exe
```

`--virtual-desktop WxH` changes the size, `--no-virtual-desktop` runs the old
direct `wine Exe/Disciple.exe` (see [`cli.md`](cli.md) and `--dry-run`, which
prints the exact command). A Proton runner is the other route that works.

### Measured on the maintainer's desktop

2026-11-22, system Wine 11.21, `InWindow=0`, a 2560×1440 screen:

| Observation | Result |
|---|---|
| `wine explorer /desktop=Disciples,640x480 Disciple.exe` | **the main menu appears and responds**; the mouse cursor lines up with the drawn menu (the pointer sits on QUIT in the screenshot), so input is 1:1 [V] |
| what the desktop looks like | the game's 640×480 surface sits in the **top-left corner**, the rest of the desktop is black, there is no title bar and no border [V] — the cause is **unknown**, see the limitation below |

Earlier runs on the same desktop (2026-11-21, real GOG install, `wine-staging`
11.21, default `~/.wine` prefix) had **no** virtual desktop:

| Attempt | Result |
|---|---|
| plain `wine`, wrapper staged, `WINEDLLOVERRIDES=ddraw=n,b` | `C0000005` at `0059559E` |
| plain `wine`, no wrapper, `InWindow=0` / `InWindow=1` | same crash at `0059559E` |
| plain `wine`, `DDraw=0` (GDI fallback) | starts, sound, **black screen** |
| Heroic + Proton-GE, its own prefix, the original `X:\…` INI | **plays** ✅ |
| Heroic + Proton-GE, its own prefix, **the pack's rewritten INI (21 keys → `Z:\…`)** | **plays** ✅ (re-run 2026-11-21 with the rewrite in place; the install holds a single, unmodified `Exe/Disciple.exe`, the same path the crash dumps name) |

The fault is `mov ecx,[eax] ; call [ecx+0x58]` with `EAX=0` — a virtual call
through a null object handed back by the graphics layer. **What precedes it is
measured** (see "What the runs on plain `wine` showed"): COM does return an
interface, `Initialize` and `SetCooperativeLevel` succeed, and the game's
`SetDisplayMode(640, 480, 8)` is refused (`NtUserChangeDisplaySettings` returns
`-2`) while the display has no 640x480 mode. Whether `-2` is `DISP_CHANGE_BADMODE`
— a missing **resolution** rather than an 8 bpp limit — is a hypothesis `[H]`;
the rig did not dump the mode list, because it has no `xrandr`/`xdpyinfo`. The
intervention is verified in two independent places: the maintainer's desktop
above, and the rig runs below.

### Rig experiments (headless, card `t_2504e165`)

Container `retrolab-dev:fedora44-gui`, `run-headless`, Xvfb, Kron4ek Wine
builds, a fresh prefix per build, `WINEDEBUG=+seh,+ddraw`, the game copied to a
scratch dir and normalised with `disciples-play --no-launch`, 40 s per run.
Every row below is `[V]` — a command run in that card produced it.

| Run | Wine build | X screen / desktop | `InWindow` | `SetDisplayMode(640,480,8)` | `GetDisplayMode` | Result |
|---|---|---|---|---|---|---|
| R1 | 11.21 Staging wow64 | Xvfb 1920x1440x24 | 0 | refused: `NtUserChangeDisplaySettings … returned -2` | 1920x1440, 32 bpp RGB | fault `0059559E` [V] |
| R2 | 10.0 Staging wow64 | Xvfb 1920x1440x24 | 0 | refused, -2 (identical line) | (same path) | fault `0059559E` [V] |
| R3 | 11.21 wow64 + `+xrandr` | Xvfb 1920x1440x24 | 0 | refused, -2 | (same path) | `Found XRandR 1.6`, "doesn't report any providers, faking one", then the same -2 [V] |
| R4 | 11.21 wow64 | **Xvfb 640x480x24** | 0 | **accepted**, no error | **PALETTEINDEXED8, 8 bits** | two `CreateSurface`, 0 faults, the "Strategy First Presents" intro on screen at 40 s [V] |
| R5 | 11.21 wow64 | Xvfb 1920x1440, `wine explorer /desktop=Disciples,640x480 Disciple.exe` | 0 | accepted | PALETTEINDEXED8 | two `CreateSurface`, 0 faults, still running at 40 s [V] |
| R6 | 11.21 wow64 | Xvfb 1920x1440, `explorer /desktop=Disciples,1920x1080` | 0 | accepted | PALETTEINDEXED8 | two `CreateSurface`, 0 faults, intro on screen in the 640x480 desktop [V] |
| R7 | 11.21 wow64 | Xvfb 1920x1440, **no command change**; registry `HKCU\Software\Wine\Explorer` `Desktop=Default` + `…\Explorer\Desktops` `Default=640x480` | 0 | accepted | PALETTEINDEXED8 | two `CreateSurface`, 0 faults, still running at 40 s [V] |

What the rig runs establish: the Wine **version** is not the variable — 10.0
wow64 and 11.21 wow64 refuse the mode in exactly the same way on a 1920x1440
Xvfb (R1, R2), so a bisect had nothing to look for and was not run — while an
available 640x480 resolution is: the X screen itself (R4) or a Wine virtual
desktop (R5, R6, R7) makes the 8-bit mode accepted and the game start. The rig
could not run a non-wow64 10.0 build (no 32-bit host libraries); Proton was not
tested there. `[H]` why Proton works: its display-mode emulation probably
always offers the standard resolutions; that was not measured.

**Open limitation (measured, cause unknown):** inside the virtual desktop the
game's picture occupies the top-left corner and the rest of the desktop is
black. Why is not known — the display server type was not measured, so do not
assume Wayland or X11. Scaling/integer upscaling (gamescope, FSR) and the game's
own windowed mode (`InWindow=1`) remain unsupported. Only the 640x480 default
was tried on a real desktop; the other sizes above were exercised in the rig
only.

To reproduce the crash instead, pass `--no-virtual-desktop` on a display that
offers no 640x480 mode. **Nothing in this pack rewrites `DDraw`, `InWindow` or
the Wine binary:** the virtual desktop is an argv change, visible in
`--print-command`.

The pack's launcher execs a **single `wine` binary** (override with `--wine`)
and has no Proton / `STEAM_COMPAT_*` path, so it cannot start the game inside a
Heroic or Lutris Proton prefix. Its plain-Wine route is the virtual desktop
above; its Proton route is the documented pair of steps: let the pack rewrite the
INI, then start the game from your runner.

```bash
disciples-play --no-launch --game-dir "<install>"   # rewrites the 21 keys only
# then press Play in Heroic / Lutris with a Proton runner
```

One fact to keep straight, because it changes what the pack is for: both INIs
play under that Proton runner — the install's **original `X:\…` values** and the
pack's **rewritten `Z:\…` values**. The rewrite is not what makes the game run;
the Proton runner is. What the rewrite buys is that the game boots with the
values the pack wrote where the pack wrote them; whether a *moved* folder still
finds its data is item 8 of the checklist, still unticked. §3 records both runs,
including the earlier one that was mis-recorded as using the rewrite when it was
not.

**cnc-ddraw was not in the picture in any of those runs.** Every plain-Wine
crash dump lists `C:\windows\system32\ddraw.dll` and
`wined3d.dll`; the `ddraw.dll` staged in `Exe\` was never loaded. That does not
prove the wrapper is useless — it proves none of the results above depend on
it. Do not credit it with the working run.

---

Three ways to get a prefix. Each one ends with the `disciples-play` launcher
doing the INI rewrite, and — under plain Wine and Bottles — with a `ddraw`
override that routes DirectDraw to the staged `cnc-ddraw` DLL. Two paths have
actually started this title: a Proton runner (§3) and plain Wine in the
launcher's virtual desktop (the section above).

The one thing every recipe shares is the **override**. `Disciple.exe` does not
import DirectDraw — `HA312W32.DLL` loads `ddraw.dll` by name — so a
`ddraw.dll` dropped next to `Disciple.exe` plus a `ddraw=n,b` override is
*meant* to take over the whole graphics layer. `n` = native (load our DLL),
`b` = builtin fallback. Treat that as the pack's intended presentation path,
not as a measured result for this title (see the caveat above and
[`verification.md`](verification.md) items 2–5, all still unticked). See
[`wrapper.md`](wrapper.md) for why, and the `doctor` subcommand for checking
that the override is at least in effect:

```bash
disciples-play doctor --game-dir "/path/to/Disciples Gold"
```

---

## Known crash at start-up: `0059559E` without a 640x480 mode

Plain `wine` reaches the main menu when the display offers a 640x480 mode and
dies with a `0059559E` access violation when it does not (both measured — see
"Start here"). On 2026-11-21 the maintainer's desktop had no 640x480 mode, so
every run there died; on 2026-11-22 the same desktop started the game inside
`wine explorer /desktop=Disciples,640x480`. A Wine setting is not what changes
this; the display the game is allowed to switch to is.

What the runs on plain `wine` showed (no virtual desktop, no 640x480 mode):

```
Disciple.log   "Midgard (v.2000, 6, 22, 1) started on Sat Nov 21 19:13:04 2026"
               -> the game's own startup code runs, then it dies
crash          Exception C0000005, write to 0x00000000, EIP 0059559E, EAX=0
               mov eax,[esi+8] ; mov eax,[eax+8] ; push eax
               mov ecx,[eax]   ; call [ecx+0x58]
               -> [this+8] is a valid object whose own +8 member is null, and the
                  game calls a virtual method through it with no null check
imports        Disciple.exe imports no ddraw/dsound/dinput; SHW32.dll is the
               graphics layer
launcher       all 21 installation keys rewritten, DISCIPLE.ini.orig written --
               the rewrite itself is fine
wrapper        no ddraw.dll staged in the first copy that crashed; the second
               run had the wrapper staged and faulted the same way
```

Tested and **ruled out** as the variable:

| Candidate | Result |
|---|---|
| `[Disciple] InWindow=1` (the game's own window mode) | **crashes at `0059559E`** without a 640x480 mode |
| `[Disciple] InWindow=0` (fullscreen, the retail baseline) | **crashes at `0059559E`** — same fault without a 640x480 mode |

So the crash is not about which of the game's own two display modes is set; it is
about the display mode it can actually switch to (the rig rows above). Two
further candidates are ruled out by later runs under plain `wine` (recorded in
the launch-path work): a **staged cnc-ddraw** (`ddraw.dll` + `ddraw.ini`)
reaches the same fault, and the engine's own **GDI path** (`DDraw=0`) starts
with sound but a black screen. Still open: a non-`wow64` Wine build, a different
Windows version in the prefix (`winecfg` → Windows version), and the mechanism
behind the refused `SetDisplayMode` `[H]`.

`doctor`'s `ini-window` line is a **configuration guard, not a crash fix**: it
warns on every `[Disciple] InWindow=1` (cnc-ddraw needs the game fullscreen,
so a window the game makes itself is never the supported setup), and passes only
on `InWindow=0`. Neither verdict says
anything about whether the game starts.

Root-cause work on `0059559E` continues outside this card. Do not add a
workaround that silently rewrites `DDraw`, `InWindow` or the Wine binary — a
silent change would hide the setting from whoever debugs it next.

---

## 1. Plain Wine

> **Starts this title when the launcher's virtual desktop is in place**
> (maintainer, 2026-11-22); without a virtual desktop and without a 640x480 mode
> plain `wine` crashes at `0059559E` with or without the wrapper staged — see
> [Start here](#start-here-plain-wine-needs-a-640x480-display--the-launcher-starts-a-virtual-desktop).
> The recipe is kept because a different Wine build or prefix may behave
> differently, and because `DDraw=0` at least starts the game (black screen).

The simplest path: one prefix, one override, done. The override can be set two
ways — per-run via `WINEDLLOVERRIDES` (the launcher does this automatically
once the wrapper is staged), or permanently via `winecfg`.

**1a. Create the prefix and boot it once** (this installs the Wine runtime into
the prefix; it must run once before the game):

```bash
WINEPREFIX=~/.local/share/wineprefixes/disciples wineboot -u
# expected: wineboot prints its normal boot messages and exits 0; a fresh
#           prefix takes ~10-30 s the first time.
```

**1b. Set the `ddraw` override permanently** (alternative to per-run env):

```bash
WINEPREFIX=~/.local/share/wineprefixes/disciples winecfg
# expected: the winecfg window opens. In the Libraries tab, "New override for
#           library" -> type "ddraw" -> Add -> Edit -> "Native then Builtin".
#           (Or skip this: the launcher sets WINEDLLOVERRIDES=ddraw=n,b itself
#           whenever it finds ddraw.dll staged.)
```

**1c. DPI.** Leave Wine's DPI at the default 96 — cnc-ddraw owns the scaling,
and a high DPI can blur the game's fixed 640×480 menus. In `winecfg` →
Graphics, "Screen resolution" should read **96 dpi**. (Unverified: the safe
default is documented, not a measured requirement.)

**1d. Stage cnc-ddraw, then launch.** cnc-ddraw must sit next to `Disciple.exe`
before the override does anything. The pack's `disciples_play.wrapper` module
fetches the pinned release and installs it (see
[`wrapper.md`](wrapper.md)); until that is wired to a one-line command, do the
same by hand: download cnc-ddraw `v7.1.0.0` and copy `ddraw.dll` (and
`ddraw.ini`) into `Exe\` next to `Disciple.exe`.

```bash
disciples-play --game-dir "/path/to/Disciples Gold" --dry-run
# expected: prints the INI diff (21 keys) and the exact wine command, without
#           writing or launching.

disciples-play --game-dir "/path/to/Disciples Gold"
# expected: "rewrote 21 installation keys (backup at …/Exe/DISCIPLE.INI.orig)"
#           then Wine starts the game inside a 640x480 virtual desktop, which is
#           what reached the main menu on the maintainer's desktop (2026-11-22).
#           If your display already offers a 640x480 mode, --no-virtual-desktop
#           gives the same result without the extra window.
```

---

## 2. Bottles

> **Expected to reach the same result as §1.** Bottles wraps a `wine` runner, so
> unless you point it at Proton it is plain Wine with a GUI — and the launcher's
> virtual desktop is what makes plain Wine start this title (see "Start here").
> Not re-run in Bottles since that change, so treat it as expected `[H]`, not
> measured. Untested with a Proton runner in Bottles.

Bottles wraps the same Wine prefix in a GUI. The parts that matter are the
**bottle template**, the **DLL override field**, and the **locale/DPI**.

1. Create a bottle with the **"Gaming"** template (a "Custom" bottle also
   works — the template only pre-tunes libraries this game does not need).
2. Open the bottle → **Settings → Components / Dependencies** (the name varies
   by Bottles version) → add a **DLL override** for `ddraw` set to
   **"Native, then Builtin"**. This is the `ddraw=n,b` equivalent; it is the
   one override the game needs.
3. **Locale**: set the bottle locale to `en_US.UTF-8` (the GOG build is
   English; a mismatch can show empty text). **DPI**: leave at 96 — cnc-ddraw
   scales, a high DPI blurs the fixed 640×480 menus.
4. From the bottle's **"Run Executable"** (or "Open terminal"), run the pack's
   launcher. That shell already has `wine` pointing at the bottle's runner and
   `WINEPREFIX` set, so the launcher (which execs `wine` from `PATH`) launches
   inside the bottle:

   ```bash
   disciples-play --game-dir "/path/to/Disciples Gold"
   # expected: the INI rewrite summary; then the game starts in the launcher's
   #           640x480 virtual desktop.
   ```

   From a *host* shell the launcher would pick the host's plain `wine`, not the
   bottle's runner, so pass the bottle's runner explicitly instead:
   `disciples-play --wine <runner>/bin/wine --game-dir …` (the runner path is
   shown under the bottle's **Settings → Runner**).

> Bottles field names shift between versions; the invariants are the bottle
> (any), the `ddraw` override (native,builtin) and DPI 96. If a field is
> missing, do the same thing in plain `winecfg` (see §1) against the bottle's
> prefix. A Bottles installed via **Flatpak** (the common case) keeps bottles
> under `~/.var/app/com.usebottles.bottles/data/bottles/<name>`; a native
> install uses `~/.local/share/bottles/bottles/<name>`. When in doubt, read the
> prefix path from the bottle's **Settings → Components** (or the details page).

---

## 3. Heroic / Proton

> **This is the verified path** (maintainer, 2026-11-21): Heroic with a
> Proton-GE runner reaches the main menu and plays — both with the install's
> **original `X:\…` INI** and with **the pack's rewritten `Z:\…` values**
> (`disciples-play --no-launch`, then Play in Heroic; the rewritten file was left
> untouched by the run). No wrapper was staged in either run, so nothing here
> credits cnc-ddraw with it. It is one of **two** verified routes: the other is
> plain Wine in the launcher's 640x480 virtual desktop (2026-11-22, "Start
> here"), which needs no Proton prefix at all.
>
> One correction worth keeping visible: an earlier run was recorded as using the
> rewritten INI when the file in place still held the original `X:\…` values
> (`DISCIPLE.ini.rewritten` turned out to contain `X:\Games\Heroic\…`). The
> rewrite was re-tested deliberately afterwards and plays — so this claim rests
> on a real run rather than on a file-copy assumption. **What that run shows is
> that the game boots with the rewritten values where the pack wrote them**; that
> a *moved* folder still finds its data is item 8 of the checklist and is
> still unticked.

The existing prefix named in `Exe\Disciple.log` (`X:\Games\Heroic\…`) came from
a Heroic install, so this is the path that reproduces what the maintainer
already has.

1. Add the game in Heroic (or use the existing entry), then open its
   **Settings → Wine / "Other"** panel.
2. Set the environment override so Proton loads the native `ddraw.dll`:

   ```
   WINEDLLOVERRIDES = "ddraw=n,b"
   ```

   (Heroic exposes this under the game's **"Environment Variables"** field —
   one `NAME = VALUE` pair per line.)
3. **Proton's own ddraw can fight the wrapper.** Proton ships its own DirectDraw
   translation; without the override, Proton's built-in is used and cnc-ddraw's
   windowed/upscaled presentation never engages. With the override set *and*
   `ddraw.dll` staged next to `Disciple.exe`, the native DLL wins. If the game
   still opens in Proton's own mode, confirm the override is spelled exactly
   `ddraw=n,b` and that `ddraw.dll` really sits in `Exe\`. (Unverified: no run
   so far has shown the staged DLL being loaded — module dumps name
   `system32\ddraw.dll` and `wined3d.dll` every time. Treat the override as an
   experiment, not a requirement to start.)
4. DPI: leave at 96 (same reasoning as §1c). The pack's launcher always execs a
   single `wine` binary — it has no Proton/`STEAM_COMPAT_*` path, so it cannot
   launch under the Heroic Proton prefix you just configured (its own route is
   the plain-Wine virtual desktop). Use the pack for the INI rewrite, then launch
   from Heroic itself:

   ```bash
   disciples-play --game-dir "/path/to/Disciples Gold" --no-launch
   # expected: "rewrote 21 installation keys …" (no launch).
   ```

   then press **Play** in Heroic. (To drive Proton directly from a shell instead,
   set `STEAM_COMPAT_DATA_PATH`, `STEAM_COMPAT_CLIENT_INSTALL_PATH` and
   `WINEDLLOVERRIDES=ddraw=n,b` and run `proton run Exe/Disciple.exe` — that is
   the Proton equivalent of the launcher's wine exec; the pack does not do it
   for you today.)

---

## If the screen is black

A black screen or a window that never appears is a *presentation* problem and is
not the start-up crash above. For any recipe, in this order:

0. **Black *around* the game in a virtual desktop.** If you launched without
   `--no-virtual-desktop`, the game's 640×480 surface sits in the top-left corner
   of a black desktop — measured on the maintainer's desktop (2026-11-22), cause
   unknown. The game itself is fine (the menu responds); this is cosmetic and is
   listed as an open limitation in [`verification.md`](verification.md). Nothing
   in this pack positions or scales that surface yet.
1. **Game fullscreen, wrapper windowed.** cnc-ddraw expects the *game* to be
   fullscreen (`InWindow=0`); windowing comes from the wrapper. A game that is
   itself windowed fights cnc-ddraw. Confirm `InWindow=0` in `Exe\DISCIPLE.INI`
   (the launcher does not change it; `doctor`'s `ini-window` line reports it).
   If the game dies at start-up with `C0000005` at `0059559E` instead, you have
   the display-mode crash above: use the launcher's default virtual desktop, or
   give the display a 640x480 mode.
2. **Override in effect.** `disciples-play doctor --game-dir …` → the
   `ddraw-override` line must be PASS. If not, set `WINEDLLOVERRIDES=ddraw=n,b`
   (or the winecfg/Bottles/Heroic equivalent above).
3. **Fall back renderer.** cnc-ddraw reads `ddraw.ini` from next to the game
   executable; edit it to set `renderer=gdi` (the software fallback — the most
   compatible renderer when OpenGL/Direct3D9 misbehave under a driver or
   Proton). See [`wrapper.md`](wrapper.md) for the key.
4. **Intro hangs.** Smacker cutscenes can hang under a wrapper; set `Intro=0`
   in the game's INI (or in the wrapper preset) and retry — that is risk R7 in
   the plan, not a blocker.

## Producing cnc-ddraw's debug log

The released `ddraw.dll` (v7.1.0.0 — the one these recipes install) writes **no
log**: upstream gates `dbg_init()` behind `#ifdef _DEBUG`, so a black-screen
triage with the release build finds no `cnc-ddraw-*.log` at all. To collect a
log, swap in the debug build for one run only:

1. Download `cnc-ddraw-experimental-debuglog.zip` from upstream's releases and
   copy *its* `ddraw.dll` over the one in `Exe\` (back up the release DLL
   first).
2. Reproduce the black screen, then restore the release DLL.
3. The log is written next to the executable:

   ```
   <install>/Exe/cnc-ddraw-Disciple-1.log   (rotates to -2 / -3; a .dmp on crash)
   ```

Attach `cnc-ddraw-Disciple-1.log` **and** the `.dmp` (if present) to the
upstream issue — the README and
[issue #44](https://github.com/FunkyFr3sh/cnc-ddraw/issues/44) ask for
`cnc-ddraw-*.log` and `cnc-ddraw-*.dmp` together. The debug build is for triage
only: it is slower and noisier, so do not leave it installed. Before posting,
re-check the cheap fixes above; most "black screen" reports are the override or
the fullscreen/windowed mismatch.
