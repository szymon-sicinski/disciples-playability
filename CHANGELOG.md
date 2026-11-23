# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased until human verification — v0.1.0

The code, the docs and the test suite are complete for v0.1.0. The tag is
**deliberately not pushed**: no agent here has run the game, and every claim
that the pack makes the game playable is a human check listed in
[`docs/verification.md`](docs/verification.md) and marked **UNVERIFIED**. The
maintainer's first in-game run (2026-11-21) produced one partial result and one
hard limitation — see *Known limitations* below. Tag and release only after
those eleven items are ticked.

### Added

- **Path-portable launcher** — `disciples-play --game-dir DIR` resolves the
  install (including a nested retail drop and `DISCIPLE.ini` case variants),
  rewrites the 21 absolute `[Installation]`/`[InstallationClient]` values on
  every start, keeps a one-time `<ini name>.orig` (`DISCIPLE.ini.orig` on a lowercase install), and starts the game
  in a 640×480 Wine virtual desktop (`wine explorer /desktop=Disciples,640x480
  Exe/Disciple.exe`) with the working directory set to `Exe` — plain Wine needs
  such a display mode to get past the `0059559E` start-up crash.
  `--virtual-desktop WxH` changes the size (validated strictly; a bad value exits
  `2` with one line) and `--no-virtual-desktop` execs `wine Exe/Disciple.exe`
  directly. `--dry-run` prints the diff, command and cwd without writing;
  `--print-command` prints the command alone; `--path-style`, `--ini-mode`,
  `--wine`, `--no-launch` are documented in [`docs/cli.md`](docs/cli.md).
- **`doctor` subcommand** — ten `PASS`/`FAIL`/`WARN` checks (install, INI
  writability, installation paths, wine, `ddraw` override, wrapper, `InWindow`,
  music, video, display) with a fix hint per line and a stable `--json` schema.
  A fourth status, `INFO`, reports a setting worth knowing that cannot be acted
  on; it never changes the exit code.
  It is read-only, never prints a game hash, and never rewrites the display key.
- **`ini-window` guard** — `doctor` warns whenever `[Disciple] InWindow=1`, with
  or without a wrapper. The wording follows the `wrapper` check's verdict
  ("installed and verified, but this title's renderer never loads it" vs "no verified
  cnc-ddraw: windowed presentation is not delivered by this pack for this
  title"), passes only on `InWindow=0`, and warns when the key is absent (retail
  default unknown). Configuration only: the start-up crash at `0059559E` also
  happens with `InWindow=0`.
- **`data` subcommand** — read-only structural report of the installation:
  directory inventory, dBase III geometry with closing header arithmetic, `MQDB`
  chunk offsets/sizes with competing hypotheses scored, ID cross-reference
  counts, plain-text digests. Structure only: no pixels, no palettes, no hashes.
- **`cnc-ddraw` wrapper module** — `build_preset()` (documented keys only,
  including `hook=4`), `fetch_wrapper()` (pinned tag `v7.1.0.0`, size and
  SHA-256, path-traversal and symlink entries refused, two-pass extract), and
  `install_wrapper()` (explicit, overwrite-protected). Upstream's MIT licence
  text ships verbatim; the binary is fetched, never vendored.
- **Reproducible prefix recipes** — plain `wine`, Bottles and Heroic/Proton in
  [`docs/wine-recipe.md`](docs/wine-recipe.md), plus `scripts/probe-matrix.sh`
  for the `DDraw × PaletteAnim` matrix.
- **Data-layout document** — [`docs/data-layout.md`](docs/data-layout.md):
  every claim graded **D**/**H**/**V** with the command beside it, and an
  open-questions table with a falsifier per row.
- **Release documentation** — [`docs/quickstart.md`](docs/quickstart.md),
  [`docs/verification.md`](docs/verification.md) (the eleven human checks), and
  this changelog.
- **CI** — pytest + `ruff check` on ubuntu-latest and windows-latest, Python
  3.10–3.13, plus a `disciples-play --help` smoke test per cell.

### Changed

- `README.md` is the release README: scope table with what the pack does **not**
  do (no widescreen, no engine, no game data), a screenshot-free feature list,
  and an explicit *Verified / Not verified* section.
- `docs/development.md` now states the INI is rewritten in place with a one-time
  `.orig` backup by default, rather than describing an always-copy behaviour
  that the launcher does not have.
- `doctor`'s `wine` line says what was measured when wine is found: plain Wine
  crashed this title at start-up on the maintainer's machine (the 640x480 8 bpp
  mode change was refused), the same command in a Wine virtual desktop reached
  the menu there, the launcher starts the game in one (`--no-virtual-desktop`
  opts out), and a Proton runner also worked for the maintainer. A fixed string
  — no Proton detection, no behaviour or exit-code change.

### Fixed

- `wrapper.install_wrapper()` no longer writes into whatever path it is given.
  The destination is resolved to the directory holding `Disciple.exe` — the
  install root is accepted and resolved to its `Exe/`, a path with no
  `Disciple.exe` under it raises `WrapperInstallError` instead of silently
  leaving a `ddraw.dll` where neither the launcher nor `doctor` looks, and a
  tree holding `Disciple.exe` in **both** the root and `Exe/` is refused the
  same way, naming both paths — guessing would install the wrapper where the
  launcher never loads from.
- CLI tests no longer read the developer's exported `$DISCIPLES_GAME_DIR` or
  per-user config; every test runs against a throwaway home.
- A top-level `--game-dir` now reaches the `data` subcommand, and `doctor` and
  `data` are registered under one subparser group.
- `doctor` evaluates each installation path instead of only counting keys, so a
  relative or stale value is a FAIL naming the key.

### Verified

- 269 synthetic-fixture tests pass here (271 with the two permission tests this
  container cannot run: they need a `chmod` that binds); 2 read-only tests pass
  against a retail installation; `ruff check` and `ruff format --check` are
  clean. (The count grows with every change; the current one is in `README.md`.)
- The launched argv is `wine explorer /desktop=Disciples,640x480 <exe>` by
  default, `wine <exe>` with `--no-virtual-desktop`, and a bad `WxH` is exit `2`
  with one line (unit tests; no Wine needed).
- The maintainer's desktop (2026-11-22, system Wine 11.21) reached the main menu
  with that command; the headless rig reached the intro with a 640x480 display
  four different ways and faulted at `0059559E` on a 1920x1440 screen with two
  Wine builds (card `t_2504e165`).
- Wrapped in `gamescope -w 640 -h 480 -W 1920 -H 1440 -S integer`, the same
  command gave a centred 1920×1440 window (exactly 3×) with the picture filling
  it and menu clicks landing on the item under the cursor (maintainer,
  2026-11-22, KDE Plasma on Wayland, gamescope 3.16.23.2+). `-F nearest` made the
  pixel edges more visible and was not judged better looking. Audio and Alt+Tab
  inside gamescope were not assessed. A recipe, not a launcher flag.
- `disciples-play data` runs read-only over a retail install: 314 files, 131
  dBase III tables (header arithmetic closes on all), 19 `MQDB` containers.
- `disciples-play doctor` runs read-only over the retail install, and its
  `ini-window` line follows that copy's own `InWindow` value: `WARN` while it
  is `1` (with or without cnc-ddraw), `PASS` once it is `0`. A configuration
  guard — it is not a crash fix.
- No game-derived file is tracked; the game folder is outside every git tree.

### Not verified

- Every in-game claim: main menu, 3× window, Alt+Enter/Alt+Tab, mouse
  targeting, palette animation, music without the CD, save/load, moving the
  install, `Config.exe`, a second prefix — see
  [`docs/verification.md`](docs/verification.md). (Item 1 is a *partial*: the
  menu was reached under Heroic + Proton-GE on 2026-11-21 and with the command
  the launcher now runs on 2026-11-22, typed at the shell — not through
  `disciples-play` itself, so the box stays unticked.)
- Windows as a supported target (CI green is not a play test).
- A one-line wrapper install: the functions exist, the CLI subcommand does not.
- That `InWindow=0` plus cnc-ddraw alone gets the game past start-up: it does
  not — the crash happened with either `InWindow` value on the maintainer's
  machine, and the launcher's virtual desktop avoided it there.
- The `MQDB`/`.wdb` semantics still marked **H** in
  [`docs/data-layout.md`](docs/data-layout.md#open-questions).

### Known limitations

- **Plain-Wine start-up crash, worked around by the launch command.** On the
  maintainer's install (2026-11-21, GOG build, `wine-staging` 11.21, default
  `~/.wine` prefix) `Disciple.exe` dies with `C0000005` at `0059559E` — a null
  object handed back by the graphics layer — with the cnc-ddraw wrapper staged
  and `WINEDLLOVERRIDES=ddraw=n,b`, with no wrapper at all, and with
  `InWindow=0` or `InWindow=1`, in every run without a virtual desktop.
  `DDraw=0` (GDI fallback) starts and plays sound but leaves the screen black.
  On 2026-11-22 the same build reached the main menu inside a 640×480 Wine
  virtual desktop, which is now the launcher's default; the headless rig
  reproduced both sides (card `t_2504e165`, runs R1–R7). The *mechanism* behind
  the refused `SetDisplayMode(640,480,8)` is still a hypothesis `[H]`.
- **Proton plays, with either INI.** Heroic + Proton-GE, its own prefix, reaches
  the main menu and plays with the install's **original `X:\…` INI** *and* with
  **the pack's rewritten `Z:\…` values** (`--no-launch`, then Play in Heroic).
  The Proton runner is what makes it run; the rewrite is what makes it portable.
- **The pack's launcher does not drive Proton.** It execs a single `wine`
  binary (`--wine` overrides it) and has no `STEAM_COMPAT_*` path, so the
  Proton route is `disciples-play --no-launch --game-dir …` and then
  **Play** in Heroic or Lutris ([`docs/wine-recipe.md`](docs/wine-recipe.md#start-here-plain-wine-crashed-without-a-virtual-desktop--the-launcher-starts-one)).
  Its own launch route is the plain-Wine virtual desktop.
- **The virtual desktop leaves the picture in its top-left corner.** Measured
  2026-11-22 on the maintainer's desktop: the game's 640×480 surface sits in the
  top-left corner, the rest of the desktop is black, no title bar or border,
  input 1:1. Cause unknown; scaling/upscaling and `InWindow=1` remain
  unsupported.
- **cnc-ddraw does not appear in those runs.** Every plain-Wine crash dump names
  `C:\windows\system32\ddraw.dll` and `wined3d.dll`; the `ddraw.dll` staged in
  `Exe\` never appears, so nothing here credits the wrapper with the working
  launch.

[Unreleased]: https://github.com/szymon-sicinski/disciples-playability/compare/df4c9f97...main
