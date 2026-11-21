# docs

| Path | Contents | Milestone |
|---|---|---|
| [`plans/00-playability-plan.md`](plans/00-playability-plan.md) | The specification: measured facts, scope, card graph, budget, risks, and the human verification checklist. Committed verbatim. | M0 |
| [`development.md`](development.md) | Commit signing (and the one unsigned commit), the local check loop, the rules that bite. | M0 |
| [`cli.md`](cli.md) | The launcher CLI and the `doctor` subcommand: usage, install resolution, the rewrite modes, the launch environment and the exit-code contract. | M2, M4 |
| [`wrapper.md`](wrapper.md) | The cnc-ddraw wrapper: the preset, the pinned fetch, install-time overwrite protection, the Wine override and the debug-log path. | M3 |
| `quickstart.md` | Three commands: install, `doctor`, play. | M6 |
| `wine-recipe.md` | Reproducible prefix recipes — plain `wine`, Bottles, Heroic/Proton. | M4 |
| `data-layout.md` | dBase III tables and `MQDB` containers, every claim graded D/H/V. | M5 |
| `verification.md` | The human checklist from the plan §8, every item *unverified* until run. | M6 |

Rule that applies to every document here: a claim without the command that
produced it is a guess, and is labelled as one.
