# disciples-playability

A **wrapper** that makes *Disciples: Sacred Lands Gold* (Strategy First, 1999;
GOG build v1.1) comfortable and portable on a modern Linux desktop, without
changing a single byte of the game.

This repository ships **no game data and never will**: no `Disciple.exe`, no
`.DBF`/`.dbi` tables, no art, audio, video or save files. It is software that
operates on an installation **you already own**.

> **Status: v0.1.0 release candidate — not yet verified in game.** The INI
> rewriter, the launcher, the cnc-ddraw preset and pinned fetch, the `doctor`
> subcommand, the Wine recipes and the read-only `data` scanner are
> implemented and tested on synthetic fixtures, and the scanner was run
> read-only against a retail install. No agent here has a display or Wine, so
> every "it plays" claim is a human check:
> [`docs/verification.md`](docs/verification.md), all eleven items
> **UNVERIFIED**.

## What the pack is

The game already runs under Wine; this is not a compatibility rescue, it is a
portability and reproducibility problem. Upstream [`cnc-ddraw`](https://github.com/FunkyFr3sh/cnc-ddraw)
(MIT) already provides windowing, scaling and VSync and lists *Disciples*
among its supported games. What is missing, and what this pack adds:

| # | Problem | What the pack does |
|---|---|---|
| 1 | `Exe\DISCIPLE.INI` hardcodes 21 absolute `X:\…` paths; move the folder and the game cannot find its data | Rewrites `[Installation]` / `[InstallationClient]` to the real install on every start, with a one-time `DISCIPLE.INI.orig` backup; a second run is a byte-wise no-op |
| 2 | cnc-ddraw is a zip you unpack and configure by hand per install | A curated `ddraw.ini` preset and a pinned (tag + size + SHA-256) fetch, shipped as a module; the one-line install command is **not wired yet** |
| 3 | The Wine prefix is hand-made, so a second machine is a second adventure | A `doctor` subcommand with nine checkable lines, plus copy-paste prefix recipes (plain `wine`, Bottles, Heroic/Proton) |
| 4 | The data layer (131 dBase III tables, 19 `MQDB` containers) is undocumented | A fact-graded data-layout document and a read-only `data` subcommand |

The pack is a **launcher and a configuration layer**. It resolves the install,
computes paths, rewrites one INI, stages nothing it does not own, and reports
what it finds. It does not patch, unpack, copy or redistribute the game.

## Scope: what it fixes, and what it does not

| Fixed in v0.1 | **Not** in v0.1, with the reason |
|---|---|
| Stale absolute INI paths (the highest-pain defect; nothing else solves it) | **Widescreen / higher internal resolution.** The UI geometry is hardcoded `640×480` in the game's own plain-text dialog scripts (`DIALOG DLG_CHOOSE_LORD,0,0,640,480,…`); real widescreen means relocating every screen — an engine project. The pack scales 640×480 pixels; it does not add screen real estate. |
| A checkable setup (`doctor`) instead of prose | **An engine.** No clean-room reimplementation, no DisciplesGL code, no HD art. |
| A reproducible prefix recipe (three variants) | **Any game data.** No `Disciple.exe`, tables, art, audio, video or saves, ever, in any artifact. |
| A verified data-layout document + read-only scanner | **A claimed Windows target.** CI runs on `windows-latest`; no human has played it there. |
| Deterministic launch command (`--dry-run`, `--print-command`, documented exit codes) | **Packaging** (PyInstaller/AppImage/wheel) — deferred to v0.2, after a human signs off that a binary runs. |
| cnc-ddraw preset + pinned fetch (module) | **A one-line wrapper install.** `install_wrapper()` exists; the CLI subcommand that calls it does not. Copy the DLL by hand today ([quickstart](docs/quickstart.md)). |

## Features (no screenshots, because nothing agent-side can take one)

- **Path-portable launcher** — `disciples-play --game-dir DIR`; resolves a
  nested retail drop, tolerates `DISCIPLE.ini` case variants, rewrites the 21
  installation keys, re-applies on every start.
- **Inspect before touching** — `--dry-run` prints the INI diff, the exact
  command line and the working directory; `--print-command` prints the command
  alone. Neither writes.
- **Three INI modes** — `backup` (default: in place + `.orig` once), `inplace`,
  `copy-tree` (leaves the GOG folder pristine at the cost of a 645 MB copy).
- **`doctor`** — nine `PASS`/`FAIL`/`WARN` lines (install, INI, installation
  paths, wine, ddraw override, wrapper, music, video, display), a one-line fix
  hint on every non-PASS line, and a stable `--json` schema. Read-only, and it
  never prints a game hash.
- **`data`** — a read-only structural inventory of the install: per-table dBase
  III geometry with closing header arithmetic, `MQDB` chunk offsets/sizes with
  competing hypotheses scored, ID cross-reference counts, plain-text digests.
  No pixels, no palettes, no hashes.
- **cnc-ddraw preset** — `windowed=1`, `maintas=1`, `maxfps=60`, `vsync=1`,
  `adjmouse=1`, `hook=4` (mode 4 patches the module that actually loads
  DirectDraw), with a pinned `v7.1.0.0` fetch and MIT licence text.
- **Recipes and probe** — [`docs/wine-recipe.md`](docs/wine-recipe.md) covers
  plain `wine`, Bottles and Heroic/Proton; `scripts/probe-matrix.sh` runs the
  `DDraw × PaletteAnim` matrix and writes a paste-back report.
- **No runtime dependencies** — a bare CPython ≥ 3.10 is enough; CI runs
  pytest + ruff on ubuntu and windows-latest, Python 3.10–3.13.

## Quick start

Requires Python ≥ 3.10 and Wine to play. No runtime dependencies.

```bash
pipx install .            # from a clone; or: pip install -e .
disciples-play doctor --game-dir "$HOME/Games/Disciples Gold"
disciples-play --game-dir "$HOME/Games/Disciples Gold"
```

**Your files stay yours.** The pack reads your install, rewrites one INI
(keeping `DISCIPLE.INI.orig`), and starts the game you own; nothing is uploaded
and no game data is shipped. Full walk-through:
[`docs/quickstart.md`](docs/quickstart.md).

## Documentation

| Document | What it answers |
|---|---|
| [`docs/quickstart.md`](docs/quickstart.md) | Three commands from a clean machine to a game in a window |
| [`docs/cli.md`](docs/cli.md) | The CLI: flags, install resolution, rewrite modes, exit codes, doctor and data contracts |
| [`docs/wine-recipe.md`](docs/wine-recipe.md) | Reproducible prefixes: plain `wine`, Bottles, Heroic/Proton |
| [`docs/wrapper.md`](docs/wrapper.md) | The cnc-ddraw preset, why `hook=4`, the pinned fetch, the `ddraw=n,b` override, black-screen triage |
| [`docs/data-layout.md`](docs/data-layout.md) | dBase III tables and `MQDB` containers, every claim graded **D**/**H**/**V**, open questions with falsifiers |
| [`docs/verification.md`](docs/verification.md) | The eleven human checks that gate the tag — all **UNVERIFIED** |
| [`docs/plans/00-playability-plan.md`](docs/plans/00-playability-plan.md) | The spec: measured facts, scope, card graph, budget, risks |
| [`THIRD_PARTY.md`](THIRD_PARTY.md) | Every component, its measured licence, and what may be shipped |

## Verified / Not verified

**Verified here** (commands in [`docs/verification.md`](docs/verification.md#what-the-agents-did-verify-for-contrast)):

- 216 synthetic-fixture tests pass; 2 read-only tests pass against a retail
  install; `ruff check` and `ruff format --check` are clean.
- CI: pytest + ruff on ubuntu-latest and windows-latest, Python 3.10, 3.11,
  3.12, 3.13, plus a `disciples-play --help` smoke test per cell.
- The INI rewrite is lossless outside the two installation sections, idempotent,
  and refuses cleanly when the file cannot be written.
- `disciples-play data` runs read-only over the retail install (314 files, 131
  tables, 19 containers) and touches nothing.
- No game-derived file is tracked, and the game folder is outside every git
  work tree.

**Not verified — and this list is the honest boundary:**

- The game reaching its main menu, the 3× window, Alt+Enter/Alt+Tab, mouse
  targeting, palette animation, music without the CD, save/load, moving the
  install, `Config.exe` behaviour, a second prefix: all eleven items in
  [`docs/verification.md`](docs/verification.md) are **UNVERIFIED**.
- Windows as a target: CI green is not a play test.
- The wrapper's one-line install: the module works, the CLI command does not
  exist yet.
- Format *semantics* in `docs/data-layout.md` marked **H** (chunk-id roles,
  header fields, the `.wdb` codec) — the geometry is measured, the meaning is
  not.

## Third-party components

See [`THIRD_PARTY.md`](THIRD_PARTY.md). In short: `cnc-ddraw` (MIT) is the one
code dependency and is **fetched at install time**, pinned by tag, size and
SHA-256, never vendored. DisciplesGL and the Disciples HD mod are cited as prior
art **only** — DisciplesGL has no licence file, so no code from it is used or
bundled. The game itself is never redistributed.

## Repository layout

```
docs/plans/00-playability-plan.md   the spec: scope, card graph, budget, risks
docs/                               quickstart, CLI, Wine recipe, wrapper, data layout, verification
scripts/                            probe and automation scripts
src/disciples_play/                 the package (INI model, launcher, wrapper, doctor, data scanner)
tests/                              unit tests on synthetic fixtures, never game bytes
third_party/                        cnc-ddraw's MIT licence text + the pinned provenance record
THIRD_PARTY.md                      every dependency, its licence and what may ship
```

## Licence

MIT — see [`LICENSE`](LICENSE). The licence covers this repository's code only,
not the game, which you must own separately.
