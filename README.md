# disciples-playability

A **wrapper** that makes *Disciples: Sacred Lands Gold* (Strategy First, 1999 —
the GOG build, v1.1) comfortable and portable on a modern Linux desktop, without
changing a single byte of the game.

This repository ships **no game data and never will**: no `Disciple.exe`, no
`.DBF`/`.dbi` tables, no art, audio, video or save files. It is software that
operates on an installation **you already own**.

> **Status: launcher implemented (M1–M2).** The INI rewriter (`disciples_play.ini`)
> and the launcher CLI (`disciples-play --game-dir …`) are implemented and tested
> on synthetic fixtures. The cnc-ddraw preset (M3) and the `doctor` subcommand
> (M4) are next. No agent here can launch the game, so every "it plays" claim
> remains a human check — see the plan in
> [`docs/plans/00-playability-plan.md`](docs/plans/00-playability-plan.md).

## What the pack is

`Disciples: Sacred Lands Gold` already runs under Wine, so this is not a
compatibility rescue — it is a comfort and reproducibility problem. Upstream
`cnc-ddraw` (MIT) already provides the windowing, scaling and VSync. What is
missing, and what this pack adds, is:

| # | Problem | What the pack does |
|---|---|---|
| 1 | `Exe\DISCIPLE.INI` hardcodes 21 absolute `X:\…` paths; move the folder and the game cannot find its data | Rewrites `[Installation]` / `[InstallationClient]` to the real install path on every start |
| 2 | cnc-ddraw is a zip you unpack and configure by hand per install | A curated `ddraw.ini` preset plus an explicit, pinned install step |
| 3 | The Wine prefix is hand-made, so a second machine is a second adventure | A `doctor` subcommand and copy-paste prefix recipes |
| 4 | The data layer (52 dBase III tables, `MQDB` containers) is undocumented | A published, fact-graded data-layout document |

The pack is a **launcher and a configuration layer**. It computes paths, writes
one INI file, installs the wrapper DLL on request and reports what it finds. It
does not patch, unpack or redistribute the game.

## What it does **not** solve

**Widescreen.** The UI geometry is hardcoded to 640×480 inside the game's own
plain-text dialog scripts (`DIALOG DLG_CHOOSE_LORD,0,0,640,480,…`), so real
widescreen means relocating every screen — an engine project, not a wrapper.
The pack scales the existing 640×480 pixels (integer scale, so 1920×1440 at 3×)
but does not add screen real estate, and does not make the UI wider.

It also does not claim that the game *plays well*: no agent can launch it here.
Every "it plays" statement is a human check, listed in
[`docs/plans/00-playability-plan.md`](docs/plans/00-playability-plan.md) §8.

Windows is not a supported target yet. It stays honest rather than claimed: the
code is platform-neutral and CI runs the suite on `windows-latest` so the
Windows path cannot rot, but support is only claimed after a human runs it.

## Quick start

Requires Python ≥ 3.10. No runtime dependencies.

```bash
git clone https://github.com/szymon-sicinski/disciples-playability
cd disciples-playability
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
disciples-play --help
```

The commands that matter, implemented today (M1–M2):

```bash
disciples-play --game-dir "/path/to/Disciples Gold" --dry-run   # show the rewrite + command
disciples-play --game-dir "/path/to/Disciples Gold"             # fix the INI and launch
disciples-play --game-dir "/path/to/Disciples Gold" --print-command
```

Still to come: the cnc-ddraw preset (`--install-wrapper`, M3) and `doctor`
(M4). See [`docs/cli.md`](docs/cli.md) for the full CLI and exit-code contract.

## Repository layout

```
docs/plans/00-playability-plan.md   the spec: scope, card graph, budget, risks
docs/                               data layout, Wine recipe, verification (M4/M5)
scripts/                            probe/automation scripts
src/disciples_play/                 the package (INI model, launcher, wrapper)
tests/                              unit tests on synthetic fixtures, never game bytes
THIRD_PARTY.md                      every dependency, its licence and what may ship
```

## Third-party components

See [`THIRD_PARTY.md`](THIRD_PARTY.md). In short: `cnc-ddraw` (MIT) is the one
code dependency and is **fetched at install time** and pinned by digest, never
vendored. DisciplesGL and the Disciples HD mod are cited as prior art **only** —
DisciplesGL has no licence file, so no code from it is used or bundled. The game
itself is never redistributed.

## Licence

MIT — see [`LICENSE`](LICENSE). The licence covers this repository's code only,
not the game, which you must own separately.
