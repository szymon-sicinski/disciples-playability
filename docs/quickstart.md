# Quick start — three commands

A clean machine with Python ≥ 3.10 and Wine installed is enough. The pack has
**no runtime dependencies** and needs no network access at run time.

```bash
# 1. install (from a clone of this repository)
pipx install .            # if pipx is missing (Debian/Ubuntu: sudo apt install pipx; else
                          #   python3 -m pip install --user pipx && ~/.local/bin/pipx ensurepath,
                          #   then open a NEW shell so PATH picks it up)
                          # any other installer works too, e.g. python3 -m pip install --user .
# 2. check the install, the Wine side and the data files — one line per check
disciples-play doctor --game-dir "$HOME/Games/Disciples Gold"
# 3. rewrite the INI paths and play
disciples-play --game-dir "$HOME/Games/Disciples Gold"
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
`wine` present, `ddraw` override, wrapper staged, music count, video count,
display — with a one-line fix hint on every non-PASS line. Exit `0` means no
check failed (warnings do not fail it); `1` means something blocks play; `2` is
a bad command line. It is read-only.

**`disciples-play --game-dir …`** resolves the install (a parent folder is
fine), rewrites the 21 stale `[Installation]`/`[InstallationClient]` values to
this install's real paths, and runs `wine Exe/Disciple.exe` with the working
directory set to `Exe`. Use `--dry-run` to see the diff and the exact command
without writing or launching, and `--print-command` to get the shell-quoted
command alone.

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
own window mode, so `doctor` warns when `InWindow=1` has no wrapper staged), and
run the launcher — it sets `WINEDLLOVERRIDES=ddraw=n,b`
automatically once it finds the DLL. [`wrapper.md`](wrapper.md) documents the
preset and the digest pin.

> **Known: the game dies at start-up under plain Wine.** `Exception C0000005` at
> `0059559E`, the same with `InWindow=0` and `InWindow=1`; see
> [`wine-recipe.md`](wine-recipe.md#known-crash-at-start-up-0059559e-unresolved-affects-every-recipe)
> for the evidence and the untested candidates. This is unresolved in v0.1.0.

## If something does not work

- The window is black or never appears → [`wine-recipe.md`](wine-recipe.md) "If the screen is black".
- The game dies at start-up with `C0000005` at `0059559E` → known and **unresolved**; [`wine-recipe.md`](wine-recipe.md#known-crash-at-start-up-0059559e-unresolved-affects-every-recipe) lists what was tested and what was not.
- A `FAIL` from `doctor` names its own fix on the same line.
- `disciples-play data --game-dir …` prints a read-only structural report of the
  data files (documented in [`data-layout.md`](data-layout.md)).

## What is not verified yet

Everything that needs a human on a machine with a display and Wine — the game
reaching its main menu, the 3× window, palette animation, mouse targeting,
music without the CD, portability after moving the folder, a second prefix — is
**UNVERIFIED** in [`verification.md`](verification.md). Read that file before
believing any claim in this repository about the game *playing*.
