# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased until human verification — v0.1.0

The code, the docs and the test suite are complete for v0.1.0. The tag is
**deliberately not pushed**: the first real in-game runs (2026-11-21) reached the
game's start-up and died there — `Exception C0000005` at `0059559E`, identically
with `[Disciple] InWindow=1` and `InWindow=0`, so the cause is **unresolved** and
is not display mode. Every claim that the pack makes the game playable is
therefore still a human check listed in
[`docs/verification.md`](docs/verification.md) and marked **UNVERIFIED**. Tag and
release only after those eleven items are ticked.

### Added

- **Path-portable launcher** — `disciples-play --game-dir DIR` resolves the
  install (including a nested retail drop and `DISCIPLE.ini` case variants),
  rewrites the 21 absolute `[Installation]`/`[InstallationClient]` values on
  every start, keeps a one-time `<ini name>.orig` (`DISCIPLE.ini.orig` on a lowercase install), and launches
  `wine Exe/Disciple.exe` with the working directory set to `Exe`.
  `--dry-run` prints the diff, command and cwd without writing; `--print-command`
  prints the command alone; `--path-style`, `--ini-mode`, `--wine`, `--no-launch`
  are documented in [`docs/cli.md`](docs/cli.md).
- **`doctor` subcommand** — ten `PASS`/`FAIL`/`WARN` checks (install, INI
  writability, installation paths, wine, `ddraw` override, wrapper, `InWindow`,
  music, video, display) with a fix hint per line and a stable `--json` schema.
  It is read-only, never prints a game hash, and never rewrites the display key.
- **`ini-window` guard** — `doctor` warns when `[Disciple] InWindow=1` asks the
  game for its own window with no cnc-ddraw staged ("windowed presentation needs
  cnc-ddraw; the launcher does not write this key"), passes on `InWindow=0`, and
  warns when the key is absent (retail default unknown). Configuration only: the
  start-up crash at `0059559E` also happens with `InWindow=0`.
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

### Fixed

- CLI tests no longer read the developer's exported `$DISCIPLES_GAME_DIR` or
  per-user config; every test runs against a throwaway home.
- A top-level `--game-dir` now reaches the `data` subcommand, and `doctor` and
  `data` are registered under one subparser group.
- `doctor` evaluates each installation path instead of only counting keys, so a
  relative or stale value is a FAIL naming the key.

### Verified

- 224 synthetic-fixture tests pass; 2 read-only tests pass against a retail
  installation; `ruff check` and `ruff format --check` are clean.
- `disciples-play data` runs read-only over a retail install: 314 files, 131
  dBase III tables (header arithmetic closes on all), 19 `MQDB` containers.
- `disciples-play doctor` runs read-only over the retail install, and its
  `ini-window` line follows that copy's own state: `WARN` while no cnc-ddraw was
  staged next to `Disciple.exe`, `PASS` once one was. A configuration guard in
  both directions — it is not a crash fix.
- No game-derived file is tracked; the game folder is outside every git tree.

### Not verified

- Every in-game claim: main menu, 3× window, Alt+Enter/Alt+Tab, mouse
  targeting, palette animation, music without the CD, save/load, moving the
  install, `Config.exe`, a second prefix — see
  [`docs/verification.md`](docs/verification.md).
- Windows as a supported target (CI green is not a play test).
- A one-line wrapper install: the functions exist, the CLI subcommand does not.
- That `InWindow=0` plus cnc-ddraw gets the game past start-up: it does not, as
  far as anyone here can tell — the crash happens with either `InWindow` value
  and its cause is unresolved.
- The `MQDB`/`.wdb` semantics still marked **H** in
  [`docs/data-layout.md`](docs/data-layout.md#open-questions).

[Unreleased]: https://github.com/szymon-sicinski/disciples-playability/compare/df4c9f97...main
