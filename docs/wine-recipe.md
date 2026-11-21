# Reproducible Wine/Proton recipes

> **Unverified until the maintainer runs them.** No agent here can launch the
> game, so nothing below claims to *work*. Every recipe is a copy-paste start
> point that a second machine should be able to follow; the "expected output"
> blocks describe what a correct run *would* show, not what has been observed.
> When a recipe has been run end-to-end on a real machine, flip its section to
> *verified* and record the machine/date in
> [`docs/verification.md`](verification.md) (created in M6).

Three ways to get the same prefix. All three end at the same place: a Wine
prefix, a `ddraw` override that routes DirectDraw to the staged `cnc-ddraw`
DLL, and the `disciples-play` launcher (which re-points the INI and launches).

The one thing every recipe shares is the **override**. `Disciple.exe` does not
import DirectDraw — `HA312W32.DLL` loads `ddraw.dll` by name — so a
`ddraw.dll` dropped next to `Disciple.exe` plus a `ddraw=n,b` override takes
over the whole graphics layer. `n` = native (load our DLL), `b` = builtin
fallback. See [`wrapper.md`](wrapper.md) for why, and the `doctor` subcommand
for checking that it is actually in effect:

```bash
disciples-play doctor --game-dir "/path/to/Disciples Gold"
```

---

## Known crash at start-up: `0059559E` (unresolved, affects every recipe)

As of **2026-11-21** this title does not reach the main menu from this pack's
launcher on plain Wine (wine-11.21 Staging, wow64), in **either** display mode.
It is not a configuration fault that a recipe below can undo, and v0.1 has no
workaround for it.

What the two real runs showed:

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
wrapper        no ddraw.dll staged in the copy that crashed
```

Tested and **ruled out**:

| Candidate | Result |
|---|---|
| `[Disciple] InWindow=1` (the game's own window mode) | **crashes at `0059559E`** |
| `[Disciple] InWindow=0` (fullscreen, the retail baseline) | **crashes at `0059559E`** — same fault |

Display mode is therefore not the cause, and the retail fullscreen baseline is
not the fix. Candidates **not yet ruled out**, roughly in the order the crash
analysis suggests: staged cnc-ddraw (`ddraw.dll` + `ddraw.ini`), a non-`wow64`
Wine build, a different Windows version in the prefix (`winecfg` → Windows
version), and the engine's own GDI path (`DDraw=0`).

`doctor`'s `ini-window` line is a **configuration guard, not a crash fix**: it
warns when `[Disciple] InWindow=1` asks the game for a window that nothing
implements without cnc-ddraw, and passes on `InWindow=0`. Neither verdict says
anything about whether the game starts.

Root-cause work on `0059559E` continues outside this card. Do not add a
workaround that silently rewrites `DDraw`, `InWindow` or the Wine binary — a
silent change would hide the setting from whoever debugs it next.

---

## 1. Plain Wine

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
#           then the game window opens at 640×480, resizable/scaled by cnc-ddraw.
```

---

## 2. Bottles

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
   # expected: same as §1d — the INI rewrite summary, then the game window.
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
   `ddraw=n,b` and that `ddraw.dll` really sits in `Exe\`.
4. DPI: leave at 96 (same reasoning as §1c). The pack's launcher always execs a
   single `wine` binary — it has no Proton/`STEAM_COMPAT_*` path — so it cannot
   launch under the Heroic Proton prefix you just configured. Use the pack for
   the INI rewrite, then launch from Heroic itself:

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

1. **Game fullscreen, wrapper windowed.** cnc-ddraw expects the *game* to be
   fullscreen (`InWindow=0`); windowing comes from the wrapper. A game that is
   itself windowed fights cnc-ddraw. Confirm `InWindow=0` in `Exe\DISCIPLE.INI`
   (the launcher does not change it; `doctor`'s `ini-window` line reports it).
   If the game dies at start-up with `C0000005` at `0059559E` instead, you have
   the unresolved crash above, not a black-screen cause.
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
