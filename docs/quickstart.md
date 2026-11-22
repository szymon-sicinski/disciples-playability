# Quick start — three commands

A clean machine with Python ≥ 3.10 and a Wine-compatible runner is enough. For
this title that runner has to be **Proton** (Heroic, Lutris) — plain `wine`
crashes at start-up, see [`wine-recipe.md`](wine-recipe.md) "Start here". The
pack has **no runtime dependencies** and needs no network access at run time.

```bash
# 1. install (from a clone of this repository)
pipx install .            # if pipx is missing (Debian/Ubuntu: sudo apt install pipx; else
                          #   python3 -m pip install --user pipx && ~/.local/bin/pipx ensurepath,
                          #   then open a NEW shell so PATH picks it up)
                          # any other installer works too, e.g. python3 -m pip install --user .
# 2. check the install, the Wine side and the data files — one line per check
disciples-play doctor --game-dir "$HOME/Games/Disciples Gold"
# 3. rewrite the INI paths, then start the game from your PROTON runner
disciples-play --no-launch --game-dir "$HOME/Games/Disciples Gold"
# then press Play in Heroic / Lutris. (Plain `wine` dies at 0059559E on start-up
# with or without the wrapper staged; see wine-recipe.md "Start here".)
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
this install's real paths, and runs `wine Exe/Disciple.exe` with the working
directory set to `Exe`. Use `--dry-run` to see the diff and the exact command
without writing or launching, and `--print-command` to get the shell-quoted
command alone.

Exit codes: `0` success, `2` bad/missing install, `3` the INI could not be
written, `4` Wine not found. The full contract is in
[`cli.md`](cli.md).

## Getting the window (cnc-ddraw)

Windowed, integer-scaled presentation was planned to come from
[cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw) (MIT), not from the game.
**Measured 2026-11-22: this does not work for Disciples.** The game acquires
DirectDraw through `CoCreateInstance(CLSID_DirectDraw)` → `system32\ddraw.dll`
(COM), so a `ddraw.dll` staged in `Exe/` is **never loaded**, and the
`WINEDLLOVERRIDES=ddraw=n,b` the launcher sets once it finds the DLL is inert —
it can only fall back to builtin. The override remains valid for titles that
`LoadLibrary("ddraw.dll")` by name, but for Disciples it is not a fix, and
windowed/upscaled presentation is therefore **not delivered by this pack**
today. **Why the same title starts under a Proton runner is not measured** —
and it is not a different ddraw implementation (DXVK provides Direct3D, not
`IDirectDraw`); see [`wine-recipe.md`](wine-recipe.md) "Start here" for what is
known and what is open.
[`wrapper.md`](wrapper.md) documents the preset and the digest pin.

> **Known: the game dies at start-up under plain Wine.** `Exception C0000005` at
> `0059559E`, the same with `InWindow=0` and `InWindow=1`; see
> [`wine-recipe.md`](wine-recipe.md#known-crash-at-start-up-0059559e-unresolved-on-plain-wine)
> for the evidence and the candidates. This is unresolved in v0.1.0.

## If something does not work

- The game **crashes at start-up** (`0059559E`, access violation) under plain `wine` → it is the launch environment, not your INI: rewrite with `disciples-play --no-launch --game-dir …` and press Play in Heroic/Lutris with a Proton runner ([`wine-recipe.md`](wine-recipe.md) "Start here").
- The window is black or the game does not start → [`wine-recipe.md`](wine-recipe.md) "If the screen is black".
- A `FAIL` from `doctor` names its own fix on the same line.
- `disciples-play data --game-dir …` prints a read-only structural report of the
  data files (documented in [`data-layout.md`](data-layout.md)).

## What is not verified yet

Everything that needs a human on a machine with a display and Wine is
**UNVERIFIED** in [`verification.md`](verification.md) — with one partial result
recorded there: the game *does* reach its main menu, launched by pressing Play in
Heroic with a Proton-GE runner. Lutris follows the same recipe but has not been
run. What remains unproven is the pack's own command — `disciples-play
--game-dir …` crashes under plain `wine` — and, among the rest, the 3× window,
palette animation, mouse targeting, music without the CD, portability after
moving the folder, and a second prefix. Read that file before believing any
claim in this repository about the game *playing*.
