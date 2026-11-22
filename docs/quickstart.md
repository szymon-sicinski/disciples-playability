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

## Getting the window (cnc-ddraw)

Windowed, integer-scaled presentation comes from
[cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw) (MIT), not from the game.
Today the pack contains the pinned fetch and preset as the
`disciples_play.wrapper` module, but **the one-line install command is not
wired yet**: copy `ddraw.dll` and `ddraw.ini` from the pinned `v7.1.0.0`
release into the game's `Exe/` folder next to `Disciple.exe` (recipe:
[`wine-recipe.md`](wine-recipe.md) §1d), keep the game itself fullscreen
(`InWindow=0` — windowed presentation comes from cnc-ddraw, not from the game's
own window mode, so `doctor` warns on `InWindow=1` in every case, a wrapper
staged or not), and
run the launcher — it sets `WINEDLLOVERRIDES=ddraw=n,b`
automatically once it finds the DLL. [`wrapper.md`](wrapper.md) documents the
preset and the digest pin.

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
What remains unproven among the rest: the 3× window, palette animation, mouse
targeting at scale, music without the CD, portability after moving the folder,
and a second prefix. Read that file before believing any claim in this
repository about the game *playing*.
