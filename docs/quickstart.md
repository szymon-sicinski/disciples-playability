# Quick start — three commands

A clean machine with Python ≥ 3.10 and a Wine-compatible runner is enough. Plain
`wine` works: the launcher starts the game in a 640×480 Wine virtual desktop,
which is what reaches the menu. A **Proton** runner (Heroic, Lutris) is the other
verified route — see [`wine-recipe.md`](wine-recipe.md) "Start here". The pack
has **no runtime dependencies** and needs no network access at run time.

```bash
# 1. install (from a clone of this repository)
pipx install .            # if pipx is missing (Debian/Ubuntu: sudo apt install pipx; else
                          #   python3 -m pip install --user pipx && ~/.local/bin/pipx ensurepath,
                          #   then open a NEW shell so PATH picks it up)
                          # any other installer works too, e.g. python3 -m pip install --user .
# 2. check the install, the Wine side and the data files — one line per check
disciples-play doctor --game-dir "$HOME/Games/Disciples Gold"
# 3. rewrite the INI paths and start the game in a 640x480 Wine virtual desktop
disciples-play --game-dir "$HOME/Games/Disciples Gold"
# (a Proton runner instead: `--no-launch`, then press Play in Heroic / Lutris;
#  your display already offers 640x480: add --no-virtual-desktop)
```

**Your files stay yours.** The pack only reads your installation, rewrites
`Exe/DISCIPLE.INI` once (keeping a backup under the *existing* file's name plus
`.orig` — `DISCIPLE.ini.orig` if your install carries the lowercase spelling),
and starts the game you already own; it ships no game data, sends nothing
anywhere, and never modifies anything outside that one INI unless you pass
`--ini-mode copy-tree`, which works on a sibling copy of the whole install.

## What each command does

**`disciples-play doctor --game-dir …`** prints one `PASS`/`FAIL`/`WARN` line
per check — install resolves, INI writable, installation paths absolute,
`wine` present, `ddraw` override, wrapper staged, the INI's own `InWindow`
window mode, music count, video count, display — with a one-line fix hint on
every non-PASS line. Exit `0` means no
check failed (warnings do not fail it); `1` means something blocks play; `2` is
a bad command line. It is read-only.

**`disciples-play --game-dir …`** resolves the install (a parent folder is
fine), rewrites the 21 stale `[Installation]`/`[InstallationClient]` values to
this install's real paths, and runs `wine explorer
/desktop=Disciples,640x480 Exe/Disciple.exe` with the working directory set to
`Exe` — a 640×480 Wine virtual desktop is what plain Wine needs to start this
title. `--virtual-desktop WxH` picks another size (`800x600`), and
`--no-virtual-desktop` execs `wine Exe/Disciple.exe` directly. Use `--dry-run`
to see the diff and the exact command without writing or launching, and
`--print-command` to get the shell-quoted command alone.

Exit codes: `0` success, `2` bad/missing install, `3` the INI could not be
written, `4` Wine not found. The full contract is in
[`cli.md`](cli.md).

**Bigger window, centred — a recipe, not a launcher flag.** Wrap the whole
command in `gamescope`, from the install's `Exe/`:

```bash
gamescope -w 640 -h 480 -W 1920 -H 1440 -S integer -- \
    wine explorer /desktop=Disciples,640x480 Disciple.exe
```

Measured 2026-11-22 (KDE Plasma on Wayland, 2560×1440 monitor, system Wine
11.21, `InWindow=0`): a **1920×1440** window, centred, with the game picture
filling it — exactly 3× — and clicking menu items hits the item under the
cursor (gamescope 3.16.23.2+). Adding `-F nearest` made the pixel edges more
visible; the maintainer did not find it better looking, so the recipe keeps the
default filter. Audio, a full session and Alt+Tab inside gamescope were **not**
assessed. Details and the not-tried list:
[`wine-recipe.md`](wine-recipe.md#bigger-window-a-gamescope-recipe-not-something-the-launcher-does).
There is no `--gamescope` flag; the launcher only chooses the virtual-desktop
size.

## Getting the window (cnc-ddraw)

Windowed, integer-scaled presentation was planned to come from
[cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw) (MIT), not from the game.
**Measured 2026-11-22: this does not work for Disciples.** The game acquires
DirectDraw through `CoCreateInstance(CLSID_DirectDraw)` → `system32\ddraw.dll`
(COM), so the renderer does not load a `ddraw.dll` staged in `Exe/`, and the
`WINEDLLOVERRIDES=ddraw=n,b` the launcher sets once it finds the DLL is inert —
it can only fall back to builtin. The override remains valid for titles that
`LoadLibrary("ddraw.dll")` by name, but for Disciples' renderer it is not a fix, and
windowed/upscaled presentation is therefore **not delivered by this pack**
today. **Why the same title starts under a Proton runner is not measured** —
and it is not a different ddraw implementation (DXVK provides Direct3D, not
`IDirectDraw`); see [`wine-recipe.md`](wine-recipe.md) "Start here" for what is
known and what is open.
[`wrapper.md`](wrapper.md) documents the preset and the digest pin.

> **Known: plain Wine needs a 640x480 display mode.** Without one the game dies
> at start-up with `Exception C0000005` at `0059559E`, the same with `InWindow=0`
> and `InWindow=1`; the launcher now starts it in a 640×480 virtual desktop,
> which is what reached the maintainer's main menu on 2026-11-22. Inside that
> desktop the picture sits in the top-left corner on a black background — open,
> cosmetic, cause unknown. See
> [`wine-recipe.md`](wine-recipe.md#known-crash-at-start-up-0059559e-without-a-640x480-mode)
> for the evidence.

## If something does not work

- The game **crashes at start-up** (`0059559E`, access violation) → the display has no 640x480 mode: run the launcher without `--no-virtual-desktop` (the default starts a 640×480 Wine virtual desktop), or with a Proton runner via `--no-launch` + Play in Heroic/Lutris ([`wine-recipe.md`](wine-recipe.md) "Start here").
- The window is black or the game does not start → [`wine-recipe.md`](wine-recipe.md) "If the screen is black".
- A `FAIL` from `doctor` names its own fix on the same line.
- `disciples-play data --game-dir …` prints a read-only structural report of the
  data files (documented in [`data-layout.md`](data-layout.md)).

## What is not verified yet

Everything that needs a human on a machine with a display and Wine is
**UNVERIFIED** in [`verification.md`](verification.md) — with two partial results
recorded there: the game *does* reach its main menu, launched by pressing Play in
Heroic with a Proton-GE runner, and on 2026-11-22 by plain `wine` 11.21 in a
640×480 Wine virtual desktop. Lutris follows the same recipe but has not been
run, and the virtual-desktop route has not been re-run with the wrapper staged.
The 3× window and mouse targeting at 3× each have **one observation** now
(gamescope, 2026-11-22: a 1920×1440 window, clicks landing on the item under the
cursor) but no ticked box — nobody has checked pixel sharpness. Still unproven
among the rest: palette animation, music without the CD, portability after
moving the folder, and a second prefix. Read that file before believing any
claim in this repository about the game *playing*.
