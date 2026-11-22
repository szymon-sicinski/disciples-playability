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
`-2`) while the display has no 640x480 mode — the mode stays 32 bpp
(1280x1024x32 on the maintainer's trace). Whether `-2` is
`DISP_CHANGE_BADMODE` — a missing **resolution** rather than an 8 bpp limit — is
a hypothesis `[H]`; the rig did not dump the mode list, because it has no
`xrandr`/`xdpyinfo`. The intervention is verified in two independent places: the
maintainer's desktop above, and the rig runs below.

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
black. Why is not known: the session is KDE Plasma on **Wayland** (reported by
the maintainer the same day), and `[H]` Xwayland/KDE handle the fullscreen mode
request differently from an ordinary window — not measured. The pack does not
scale anything (the `gamescope` recipe below was measured once); the game's own
windowed mode (`InWindow=1`) remains unsupported. Only the 640x480 default
was tried on a real desktop; the other sizes above were exercised in the rig
only.

### Bigger window: a gamescope recipe, not something the launcher does

The launcher only chooses the virtual-desktop size; it does not scale anything.
To get a larger, centred window, wrap the whole command in `gamescope`, from the
install's `Exe/` directory:

```bash
gamescope -w 640 -h 480 -W 1920 -H 1440 -S integer -- \
    wine explorer /desktop=Disciples,640x480 Disciple.exe
```

Measured on the maintainer's machine (2026-11-22: KDE Plasma on **Wayland**,
Nobara 44, 2560×1440 monitor, AMD RX 580, system Wine 11.21, `InWindow=0`):

| Observation | Result |
|---|---|
| the window | a **1920×1440** window, centred on the screen, and the game picture **fills** it — 1920×1440 is exactly 3× the game's 640×480 [V] |
| input | clicking menu items hits the item under the cursor: mouse targeting at 3× works [V] |
| the menu | appears and responds [V] |

**Not assessed:** whether the pixels are sharp (gamescope's default upscaling
filter is not nearest; `-F nearest` was not tried), audio, a full play session,
Alt+Tab or Alt+Enter inside gamescope. **Not tried:** `-f` (fullscreen), a 2×
scale, an X11 session; the `gamescope` version is not recorded. The launcher
gains **no** gamescope flag: this is a recipe you type.

Two neighbouring observations from the same session: `wine explorer
/desktop=Disciples,1280x960` opens its own **1280×960 window** with the
**unscaled** 640×480 game surface in one corner of it — the game does not scale
itself — while the plain 640×480 virtual desktop appeared full screen with the
picture in the top-left corner, as above. `[H]` that Xwayland/KDE treat the
fullscreen mode request differently from an ordinary window, which would explain
both; it was not measured.

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
`wined3d.dll`; the `ddraw.dll` staged in `Exe\` never appears in them. That does not
prove the wrapper is useless — it proves none of the results above depend on
it. Do not credit it with the working run.

---

Three ways to get a prefix. Each one ends with the `disciples-play` launcher
doing the INI rewrite. Each also mentions the `ddraw` override, because that was
the design — but for the renderer the override is **inert** (next paragraph), so
treat it as a step to skip, not a step that makes anything work. Two paths have
actually started this title: a Proton runner (§3) and plain Wine in the
launcher's virtual desktop (the section above).

The one thing every recipe used to share is the **override**. `Disciple.exe` does not
import DirectDraw, and its renderer does not `LoadLibrary` `ddraw.dll` by name
(`SMACKW32.DLL`, the video player, does — an unexercised path, see
[`wrapper.md`](wrapper.md)) — the renderer acquires DirectDraw through **`CoCreateInstance(CLSID_DirectDraw)`**, which
resolves to the prefix's `system32\ddraw.dll` via the COM registry entry (see
"Known crash at start-up" below). A `ddraw.dll` dropped next to `Disciple.exe`
plus a `ddraw=n,b` override is therefore **not** able to take over the renderer's
graphics layer — the renderer never loads the native DLL. `n` = native (load our
DLL), `b` = builtin fallback; for the renderer the override can only ever fall
back to `b`. See [`wrapper.md`](wrapper.md) and the `doctor` subcommand for checking
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
this; the display the game is allowed to switch to is. The game acquires
DirectDraw through `CoCreateInstance(CLSID_DirectDraw)` (see "What the crash
is" below), and the one candidate Wine-side fix — register cnc-ddraw as that
COM server — is untested.

What the runs on plain `wine` showed (no virtual desktop, no 640x480 mode):

```
Disciple.log   "Midgard (v.2000, 6, 22, 1) started on Sat Nov 21 19:13:04 2026"
               -> the game's own startup code runs, then it dies
crash          Unhandled page fault on read access to 00000000, EIP 0059559E, EAX=0
               mov eax,[esi+8] ; mov eax,[eax+8] ; push edx ; push eax
               mov ecx,[eax]   ; call [ecx+0x58]
               -> [this+8] is a valid object whose own +8 member is null, and the
                  game calls a virtual method through it with no null check
               -> +0x58 is GetSurfaceDesc on a surface and WaitForVerticalBlank on
                  IDirectDraw4, and two arguments are pushed: the object's type is
                  not established by the crash alone [H]
               -> the faulting access is a READ through a null eax; the Windows
                  crash dialog labels the same fault "write to location 00000000"
imports        Disciple.exe imports no ddraw/dsound/dinput; it acquires DirectDraw
               via CoCreateInstance(CLSID_DirectDraw) through ole32 — the renderer
               lives in Disciple.exe (CPrimaryDisplayDDraw / CPrimaryDisplayDIB).
               SHW32.dll is SmartHeap (the memory manager), not the graphics layer
launcher       all 21 installation keys rewritten, DISCIPLE.ini.orig written --
               the rewrite itself is fine
wrapper        a cnc-ddraw ddraw.dll staged in Exe\ is not the renderer's — the game's
               COM path resolves system32\ddraw.dll, not the app directory — so it
               faults identically with or without the wrapper (see "What the crash
               is" below)
```

Measured headlessly in the retrolab rig (wine-staging **11.21**, wow64-only,
llvmpipe software GL, no audio, baked prefix) on **2026-11-22**, one variable per
run. Legend: `[V]` = measured in that run, `[H]` = hypothesis, `[U]` = untested
in this rig (needs the maintainer's machine or a different Wine build). The rows
below are the candidates tested and **ruled out** as the variable, plus what
remains open.

| Experiment | Result |
|---|---|
| `[Disciple] InWindow=1` (the game's own window mode) | **crashes at `0059559E`** without a 640x480 mode |
| `[Disciple] InWindow=0` (fullscreen, the retail baseline) | **crashes at `0059559E`** — same fault without a 640x480 mode |
| **B** — `WINEDLLOVERRIDES=ddraw=b` (builtin ddraw, baseline) | **[V] crashes at `0059559E`, deterministically.** `Disciple.log` = "Midgard started" (dies before sound init); frame = the crash dialog (mean 241, 74 colours); windows = game + "Wine Debugger" + "Program Error". |
| **E5** — `WINEDLLOVERRIDES=ddraw=n` (native cnc-ddraw, **no** `,b` fallback) | **[V] same `0059559E` crash**, and Wine reports the native DLL is *never loaded*: `err:ole:apartment_add_dll couldn't load in-process dll C:\windows\system32\ddraw.dll`, then `class {D7B70EE0-4340-11CF-B063-0020AFC2CD35} not registered`. The staged `Exe\ddraw.dll` is not in that path, so `n` always falls back to builtin — exactly why the pack's `n,b` never helped. |
| **E7** — `[Disciple] DDraw=0` (GDI fallback) | **[V] does not crash** — process alive at the 25 s kill. Frame near-black (mean 1→10, 33→52 colours); `Disciple.log` = "Midgard started" + "Sound system could not be initialized" (no audio device in the rig). Confirms "GDI starts, black screen". |
| **E3** — `WINEDLLOVERRIDES=msvcrt=n` (force the bundled 1999 `MSVCRT.DLL`) | **[V] not a fix and not the same crash.** Wine's own DLL chain breaks — `err:module:import_dll Library msvcrt.dll (needed by advapi32/rpcrt4/user32/gdi32/shell32) not found`, `STATUS_DLL_NOT_FOUND c0000135`. The game process starts ("Midgard started") but the loader never reaches DirectDraw, so the CRT is not the cause. |
| **E4** — `WINEARCH=win32` prefix (non-wow64) | **[U] cannot be run in this rig** — this Wine build is wow64-only: `wine: WINEARCH is set to 'win32' but this is not supported in wow64 mode.` Needs a 32-bit-capable Wine build on the maintainer's machine. |
| **E1** — Windows version gate (`winecfg` → 98/XP) | **[U]** — the prefix reports Windows 10 Pro (build 19045); not changed here. Proton reports Win7/WinXP to old titles, so this is still a plausible differential and a ~10-second maintainer test. |
| **E2** — virtual desktop 800×600 | **[V] superseded — this is the intervention.** The `winecfg` display change was never applied in that run, but the virtual desktop was measured later in the same rig (`wine explorer /desktop=…` in R5, a 1920×1080 desktop in R6, the registry key in R7), and an 8 bpp 640x480 mode was accepted there. See the rig table under "Start here". |
| **E6** — X11 vs Wayland display path | **[U]** — the rig is X11-only (Xvfb); needs the maintainer's display. |
| Wine version ≠ 11.21 | **[V] tested later** — 10.0 Staging wow64 ran in the rig matrix above (R2) and refused the 8-bit mode exactly as 11.21 did (R1), so the version is not the variable; no further builds were added to the image. |

So the crash is not about which of the game's own two display modes is set
(`InWindow`), nor the wrapper, nor the CRT: it is about the display mode the game
can actually switch to (the rig rows above). Still open: a non-`wow64` Wine build,
a different Windows version in the prefix (`winecfg` → Windows version), and the
mechanism behind the refused `SetDisplayMode` `[H]`.

**What the crash is (resolved, `[V]`).** The investigation's open question — how
`Disciple.exe` obtains `IDirectDraw` — is now answered: the game calls
**`CoCreateInstance(CLSID_DirectDraw)`** (`{D7B70EE0-4340-11CF-B063-0020AFC2CD35}`),
which resolves through the prefix registry's
`HKCR\CLSID\{…}\InprocServer32 = C:\windows\system32\ddraw.dll` — the COM server
path, **not** the application-directory DLL search. Two failure modes land on the
same null dereference at `0059559E`:

- **builtin ddraw** (`ddraw=b`, `[V]`): COM returns a builtin `IDirectDraw` and
  the game gets as far as `SetCooperativeLevel(DDSCL_FULLSCREEN|DDSCL_EXCLUSIVE)`
  and `SetDisplayMode(640, 480, 8)`. The mode change is **refused** —
  `err:system:NtUserChangeDisplaySettings ... returned -2` — and the following
  `GetDisplayMode` still reports 1280x1024x32. The game then dereferences a null
  object whose type the crash alone does not establish (`+0x58` is
  `IDirectDrawSurface::GetSurfaceDesc` *and* `IDirectDraw4::WaitForVerticalBlank`,
  and the code pushes two arguments). **`[H]`:** "the primary surface stayed null"
  is a hypothesis, not an observation — the experiment table records no
  `WINEDEBUG=+ddraw` run, so no claim about what such a trace contains is made
  here — what is measured is that the 8-bit mode
  is not applied and the fault follows.
- **native ddraw** (`ddraw=n`): the COM server load itself fails (`class not
  registered`), so there is no `IDirectDraw` at all.

**Consequence for the pack.** A cnc-ddraw `ddraw.dll` staged next to
`Disciple.exe` is **not loaded by this title's renderer**, because its DDraw
acquisition is COM-based and `InprocServer32` points at `system32` (the video
player's by-name `LoadLibraryA("DDRAW.DLL")` is a separate, untested path). The `ddraw=n,b` override can
therefore only ever fall back to `b`. To make cnc-ddraw take over, its `ddraw.dll`
would have to be **registered as the COM server for `CLSID_DirectDraw`**
(`regsvr32 ddraw.dll` in the prefix) or dropped into the prefix's `system32` —
neither the launcher does today, and neither is tested here.

`doctor`'s `ini-window` line is a **configuration guard, not a crash fix**: it
warns on every `[Disciple] InWindow=1` — because this title's renderer never loads a
wrapper, the key cannot buy you a window, so `InWindow=0` stays the documented
baseline — and passes only on `InWindow=0`. Neither verdict says
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

> **For the renderer the override cannot engage.** The game
> acquires DirectDraw through `CoCreateInstance(CLSID_DirectDraw)`, which COM
> resolves to the prefix's `system32\ddraw.dll` — a registry path, not the
> app-directory search an override redirects (see "Known crash at start-up").
> Steps 1b and 1d below are therefore the recipe as designed, not a working
> path for Disciples: staging the DLL and setting the override changes nothing
> for the renderer (the video player's by-name load is untested).

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
#           This is inert for Disciples either way (see the caveat above and
#           "Known crash at start-up"); the launcher would also set
#           WINEDLLOVERRIDES=ddraw=n,b itself once a ddraw.dll is staged.
```

**1c. DPI.** Leave Wine's DPI at the default 96 — a high DPI can blur the
game's fixed 640×480 menus. (The usual reason, "cnc-ddraw owns the scaling",
does not apply here: the renderer never loads the wrapper.) In `winecfg` →
Graphics, "Screen resolution" should read **96 dpi**. (Unverified: the safe
default is documented, not a measured requirement.)

**1d. Stage cnc-ddraw, then launch.** In the recipe as designed cnc-ddraw must
sit next to `Disciple.exe` before the override does anything — but the renderer
does not load it either way (see the caveat above). The pack's `disciples_play.wrapper` module
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
   **"Native, then Builtin"**. This is the `ddraw=n,b` equivalent — inert for
   this title for the reason in the §1 caveat, so do not read it as the fix.
3. **Locale**: set the bottle locale to `en_US.UTF-8` (the GOG build is
   English; a mismatch can show empty text). **DPI**: leave at 96 — a high DPI
   blurs the fixed 640×480 menus (not because cnc-ddraw scales: the renderer never loads it
   here).
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
2. **No `WINEDLLOVERRIDES` is needed, and setting one changes nothing for the renderer.** The
   game's COM path ignores the app-directory DLL search that an override would
   redirect (step 3). If your Heroic entry already carries
   `WINEDLLOVERRIDES = "ddraw=n,b"` from an earlier attempt, it is harmless —
   leave it or remove it, the measured result is the same.
3. **The game's DirectDraw acquisition is COM-based, so the renderer does not
   load a staged wrapper.** `Disciple.exe` obtains DirectDraw through
   `CoCreateInstance(CLSID_DirectDraw)`, which resolves to the prefix's
   registered `system32\ddraw.dll` — measured on plain Wine (see "Known crash at
   start-up" above). **`[U]` what Proton resolves that COM path to has not been
   measured.** It is *not* DXVK: DXVK implements Direct3D 8/9/10/11, and nothing
   in it provides `IDirectDraw`; Proton's `ddraw.dll` is Wine's own,
   wined3d-backed one — the same DLL measured failing above. Why the same title
   starts under Proton and dies under plain Wine is therefore **open**, and the
   candidates are the Proton Wine version and its patches, the prefix's Windows
   version, and the display path — not a different ddraw implementation.
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
   set `STEAM_COMPAT_DATA_PATH` and `STEAM_COMPAT_CLIENT_INSTALL_PATH` and run
   `proton run Exe/Disciple.exe` — that is the Proton equivalent of the
   launcher's wine exec, and no `WINEDLLOVERRIDES` is involved: step 2 explains
   why an override changes nothing for the renderer. The pack does not do this for you
   today.)

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
1. **Is a wrapper claimed here?** cnc-ddraw expects the *game* to be fullscreen
   (`InWindow=0`) and presents the window itself — but **this title's renderer never loads
   it** (see "Known crash at start-up"), so no `InWindow` value and no staged DLL
   can produce a wrapper-presented game window today. If a black screen is your symptom, the black
   screen and the start-up crash are both consequences of that, not of this
   setting; `doctor`'s `ini-window` line reports the key but cannot promise a
   wrapper-presented window. If the game dies at start-up with `C0000005` at
   `0059559E` instead, you have the display-mode crash above: use the launcher's
   default virtual desktop, or give the display a 640x480 mode.
2. **Override in effect (for titles that load cnc-ddraw).** `disciples-play
   doctor --game-dir …` → the `ddraw-override` line. For this title that line is
   always `INFO` — it cannot fail, and it cannot be cleared by any action, so it
   does not count against the exit code — because the game acquires DirectDraw
   via
   `CoCreateInstance(CLSID_DirectDraw)` (COM), so for the renderer the override
   and a staged `ddraw.dll` are inert and are not the cause of a black *game*
   screen. (The video player's by-name `LoadLibraryA("DDRAW.DLL")` is untested,
   so a black screen **during a cutscene** is not ruled out.) It matters for
   titles that `LoadLibrary("ddraw.dll")` by name.
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
