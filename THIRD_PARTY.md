# THIRD_PARTY.md

Every external component this project knows about, what its licence actually is
(checked, not assumed), why it is cited, and what — if anything — may be
shipped from it.

Facts below were read from the GitHub API on **2026-11-20**; the command beside
each claim is the way to re-check it. This project ships **no game bytes**: see
the guard in `docs/plans/00-playability-plan.md` §8 item 11.

| Component | Upstream | Licence | Status | Why it is cited | What may be shipped |
|---|---|---|---|---|---|
| **cnc-ddraw** | [`FunkyFr3sh/cnc-ddraw`](https://github.com/FunkyFr3sh/cnc-ddraw), release tag **`v7.1.0.0`** | **MIT** — `GET /repos/FunkyFr3sh/cnc-ddraw` → `license.spdx_id: "MIT"` | Intended dependency | The DirectDraw replacement that provides windowed/borderless mode, shader upscaling, VSync, FPS limiting and saved window geometry for exactly this class of game; documents Wine and lists *Disciples* among supported games | The **binary is fetched at install time** from the pinned tag and verified against a SHA-256 pin (measured digest in the note below), never committed to this repository. Upstream's MIT `LICENSE` text ships at `third_party/cnc-ddraw-LICENSE.txt`; tag/URL/size/digest are recorded in `third_party/cnc-ddraw-PROVENANCE.md`. **Not vendored.** |
| **DisciplesGL** | [`rootext/disciples-gl-builds`](https://github.com/rootext/disciples-gl-builds) | **None.** `GET /repos/rootext/disciples-gl-builds` → `license: null`. No licence file ⇒ **all rights reserved** | Prior art, facts only | Shows an OpenGL wrapper for this title is feasible and lists the upscale filters and quicksave/archive QoL users expect | **Nothing.** No code, no binary, no asset is copied or bundled, and none is reverse-engineered from its builds. Cite it, do not depend on it. |
| **Disciples HD mod** | Verok's HD mod (community, last updated 2023, marked abandoned) | Not established — treat as **all rights reserved** | Prior art, facts only | Context on what the community already did with art scaling, and why a wrapper is a different product | **Nothing.** Facts only, same rule as DisciplesGL. |
| **The game** — *Disciples: Sacred Lands Gold* (Strategy First, 1999; GOG build v1.1) | Commercial product | Proprietary | Required at runtime; **not** a dependency of this repo | The wrapper operates on a user's own installation | **Never redistributed**, in whole or in part: no `Disciple.exe`, no `.DBF`/`.dbi`/`.dlg`, no `.smk`/`.wav`, no art, no save files. Tests use synthetic fixtures only. `--game-dir` points at the user's copy. |

## Verification commands

```bash
# cnc-ddraw licence + release tag
curl -s https://api.github.com/repos/FunkyFr3sh/cnc-ddraw | grep -A3 '"license"'
curl -s https://api.github.com/repos/FunkyFr3sh/cnc-ddraw/releases/tags/v7.1.0.0

# DisciplesGL: no licence file -> "license": null
curl -s https://api.github.com/repos/rootext/disciples-gl-builds | grep -A3 '"license"'
```

## Notes

- **cnc-ddraw is MIT, so it could legally be bundled.** It is still fetched
  rather than vendored, for two reasons: the repository stays small and free of
  third-party binaries, and the release artifact is pinned by digest so a
  re-tagged release upstream cannot silently change what users run. Licensing
  permission is not the same as a good reason to commit a binary.
- **Pinned third_party archive digest** (allowed — not a game hash): cnc-ddraw
  `v7.1.0.0` `cnc-ddraw.zip` (2,688,079 bytes), SHA-256 measured 2026-11-21 and
  recorded once in `third_party/cnc-ddraw-PROVENANCE.md`; the same constant is
  the pin in `src/disciples_play/wrapper.py` (`CNC_DDRAW_SHA256`). Those two
  places are the only third-party digests in the repository, and neither is a
  hash of a game file.
- **`cnc-ddraw` requires the game to be fullscreen** (`InWindow=0`); windowed
  presentation comes from cnc-ddraw, not from the game's own windowed mode. That
  ordering is documented wherever the preset is (milestone M3).
- Runtime dependencies of this package are **none** (`dependencies = []` in
  `pyproject.toml`). Development-only tools — `pytest`, `ruff` — are installed
  through the `dev` extra and are not shipped to users.
