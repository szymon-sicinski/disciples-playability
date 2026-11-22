# Disciples: Sacred Lands Gold — playability pack plan

Status: **proposal, for maintainer review.** Nothing here is implemented yet.
Unit of measure: the `retrolab` board's measured per-card costs (see
[§6](#6-budget-tokens-and-money)).

## 0. Verdict first

Half of the ask is **already solved by someone else**, and saying so changes the
project: `cnc-ddraw` (MIT, 3,594 stars, latest release `v7.1.0.0` 2024-12-28)
reimplements DirectDraw for exactly this class of game, supports Wine, and **lists
Disciples in its supported-games list**. Windowed/borderless, Alt+Enter,
integer-ish upscaling via shaders, FPS limiter, VSync, saved window geometry,
optional mouse scaling and cursor-unlock hotkeys all ship there today.

So the pack is not "make it windowed". It is the three things cnc-ddraw does not
do, and one thing no one has published:

1. **Portable paths** — `Exe\DISCIPLE.INI` hardcodes 21 absolute `X:\…` paths in
   two sections; cnc-ddraw does not touch them and the game will not find its
   data if the folder moves. (This is the most-reported breakage for the title.)
2. **One command that sets all of it up and launches it** — cnc-ddraw is a zip
   you unzip into the game folder and then configure by hand per install.
3. **A reproducible prefix recipe** — the current prefix is hand-made, so a
   second machine is a second adventure.
4. **A published, verified data-layout document** — 52 dBase III tables and
   `MQDB` containers, which is unusually modder-friendly and undocumented.

Fixed 640×480 (#1 of the five defects) is **out of scope** as a real fix: the UI
geometry is hardcoded to 640×480 inside the plain-text dialog scripts
(`DIALOG DLG_CHOOSE_LORD,0,0,640,480,…`), so genuine widescreen means relocating
every screen — an engine project, not a wrapper. See [§2](#2-scope).

## 1. Measured facts this plan is built on

Everything below was measured in this session against the GOG install; commands
are given so each number is checkable.

| Fact | Evidence | Grade |
|---|---|---|
| `Disciple.exe` is PE32 i386 with **no** `ddraw`/`dsound` import; direct imports are `SHW32.dll, C4dll-R.dll, mss32.dll, smackw32.dll, WINMM, KERNEL32, USER32, GDI32, ole32, MSVCRT` | PE import-table walk over the install | **V** |
| `HA312W32.DLL` and `SHW32.DLL` import only `KERNEL32/USER32/GDI32/ADVAPI32` and contain the literal string `ddraw.dll` | PE import-table walk + string scan | **V** |
| ~~⇒ a `ddraw.dll` dropped next to the exe plus `WINEDLLOVERRIDES="ddraw=n,b"` intercepts the graphics layer~~ — **retracted, measured false** (2026-11-22): `Disciple.exe` acquires DirectDraw via `CoCreateInstance(CLSID_DirectDraw)` → `system32\ddraw.dll` (COM), so the renderer does not load the staged DLL and the override only ever falls back to builtin | headless rig (E5: `ddraw=n` → "class not registered"; the string scan found a by-name `ddraw.dll` string but attributed it to the wrong module — it is in `SMACKW32.DLL`'s `.text` (video; static evidence only, untested) — and the "takes over" inference was not right) | **V** (falsified) |
| `Config.exe` imports `KERNEL32, USER32, COMCTL32, VERSION` only — **no ADVAPI32**, so **no registry**: settings are INI-only | PE import walk | **V** |
| `DISCIPLE.INI`: 4 sections, 41 keys — `[Disciple]` 19, `[CDROM]` 1, `[Installation]` 15, `[InstallationClient]` 6; 21 of them are absolute path values; CRLF line endings | parse + count | **V** |
| Install ≈ 645 MB (615 MiB): `Video` 240 MB + `Briefing` 238 MB of `.smk`, `Music` 46 MB of **25 `.wav` files** ⇒ music does not need the CD | `du -sb` per dir | **V** |
| The game **writes into the install**: `Exe\Disciple.log`, `Savegame\AutoSave.sg`, `Savegame/Début Saga.sg` | file listing + the log itself | **V** |
| The INI names directories in lowercase (`globals`) while the install has them capitalised (`Globals`) — it works today, so Wine/path resolution is case-insensitive here | name comparison, both directions | **H** (works, mechanism unverified) |
| Data layer: 52 `.DBF` in `Globals\` are real dBase III (magic `0x03`), and the header arithmetic closes — `hdrlen + records×reclen + 1 == filesize` for `GACTION.DBF`, `GRACE.DBF`, `GBUILD.DBF` | dBase header decode | **V** |
| `.dbi` containers are a custom `MQDB` v9 format (magic `MQDB`, u32 version at +8); `.dlg` files are **plain text** dialog scripts; `PALANIM.DAT` is **plain text** | header bytes + `head` | **V** (magic) / **H** (layers) |
| cnc-ddraw is MIT, 3,594 stars, `v7.1.0.0` asset `cnc-ddraw.zip` 2.69 MB, pushed 2026-08-30, Disciples in its supported list | GitHub API | **V** |
| DisciplesGL (`rootext/disciples-gl-builds`) has **no licence file** → all rights reserved; 34 stars, last push 2024-12-18 | GitHub API | **V** |
| cnc-ddraw requires the **game** to be fullscreen (`InWindow=0`); windowed mode comes from cnc-ddraw, not the game | upstream README, "Important" block | **D** (upstream) |

Consequence for the design: there is no registry to seed, no DirectX installer to
run, and no CD to fake. The whole playability problem is **one INI file and one
Wine/Proton prefix** — the "one DLL in the game folder" idea (cnc-ddraw) is
retracted above: the game's COM path means that staged DLL is not the one the renderer loads.

## 2. Scope

### In, for v0.1

| Item | Why it is in |
|---|---|
| Path-portable launcher: rewrite `[Installation]`/`[InstallationClient]` to the real install, every start | The defect with the highest user pain and the only one nothing else solves |
| Windows-path emission (`winepath -w` when available, `Z:\` fallback) | The game needs Windows paths even when it lives on Linux |
| `doctor` subcommand: install sanity, wine version, ddraw override, DPI, prefix | Makes "reproducible setup" checkable instead of prose |
| cnc-ddraw preset (`ddraw.ini`) + pinned fetch with SHA-256 + MIT licence text | The preset is the product; the binary is fetched, not vendored |
| Reproducible Wine recipe (plain wine, Bottles, Heroic) | Defect 5; cheap once the preset exists |
| Data-layout document, fact-graded, with a read-only `data` subcommand | Genuinely valuable, legally clean (structure only, no pixels) |
| CI: pytest 3.10–3.13 + ruff on ubuntu **and windows-latest** | Keeps the Windows path from rotting without claiming Windows support |

### Out, with the reason

| Item | Why not now |
|---|---|
| True widescreen / higher internal resolution | UI geometry is hardcoded `640×480` in the `.dlg` scripts; needs UI relocation + unknown screen-relative logic. Engine-scale work (LOMAX's M3+M4 were ~2.6M tokens for a game with a known codebase). Revisit only if the maintainer wants an engine project. |
| **Windows as a first-milestone target** | No Windows machine exists to verify; every "works on Windows" claim would be unverifiable. Decision: code stays platform-neutral, CI runs the suite on `windows-latest`, but Windows support is *claimed* only after a human runs it. |
| Own OpenGL wrapper (DisciplesGL territory) | Unlicensed prior art → facts only; and cnc-ddraw already covers the need |
| Bundling game data, or an "AppImage of the game" | Illegal and impossible; the pack is a wrapper that loads the user's files |
| Quicksave / archive QoL, settings GUI, shader presets | v0.2 material; shader presets are a config-file change away |
| Multiplayer (IPX/TCP), mod compatibility guarantees | Out of the comfort-package remit; also unverifiable from the sandbox |
| PyInstaller/AppImage packaging | v0.2; needs a human on the target machine to sign off that the binary runs |

### One deliberate reinterpretation of the brief

The brief says "the install stays read-only; the launcher writes only its own
output and a copy of `DISCIPLE.INI`". Measured: **the game itself already writes
into the install** (`Exe\Disciple.log`, `Savegame\AutoSave.sg`), so "read-only"
was never literally true, and the game only reads `<install>\EXE\Disciple.ini` —
a copy elsewhere is invisible to it unless we patch the binary.

Decision: `--ini-mode {backup,inplace,copy-tree}`, **default `backup`** — write
`Exe\DISCIPLE.INI` in place, saving `DISCIPLE.INI.orig` once (never overwritten
afterwards), and re-apply on every launch because `Config.exe` rewrites the file.
`copy-tree` exists for users who want the GOG folder pristine and costs 645 MB.
The intent of the constraint (never destroy user state) is met; the letter is not.
If the maintainer disagrees, the default flips to `copy-tree` at no code cost —
it is a flag, which is why it is a flag.

## 3. Where the repository lives

**`/home/nwah/Development/RetroLab/disciples-playability`**, public at
`https://github.com/szymon-sicinski/disciples-playability`, MIT.

Why here:

- Sibling of `lomax-modern` under the directory the worker can see
  (`/home/nwah/Development/RetroLab` is the rw bind mount; inside the sandbox it
  is the same path), so cards can point at it without a worktree landing outside
  the mount.
- Verified outside every git tree for game data: `git -C "/game-files/Disciples
  Gold" rev-parse --show-toplevel` and `git -C …/RetroLab rev-parse` both fail
  (exit 128). Nothing under `Game files/` can be staged by accident.
- The product name states what it is; it is not a fork of anything.

The current install stays where it is (`Game files/Disciples Gold`, exposed to
the sandbox read-only as `/game-files/Disciples Gold`). The launcher takes
`--game-dir` and never assumes a location, so no move is required. If a second
copy ever appears, the slot convention is
`Game files/disciples-playability/<variant>/` — not a parent of the repo.

## 4. Card graph

Board `disciples`. Reviews are a **lane** (`kanban_request_review`), not separate
cards — the retrolab board spent 111 cards on review and duplicated dispatch;
that is the one process change this plan makes. Dependencies are expressed as
`parents`, so nothing dispatches before its input exists.

```
M0 scaffold ──┬── M1 INI core ──┬── M2 launcher ──┐
              │                 └── M3 cnc-ddraw ─┴── M4 doctor+recipe ──┐
              └── M5 data-layout docs ───────────────────────────────────┴── M6 v0.1 RC
```

Card ids as created on the board (2026-11-20): **M0** `t_2c52f2c9`, **M1**
`t_d1284460`, **M2** `t_0ede1a93`, **M3** `t_d2af5d0b`, **M4** `t_eb657f71`,
**M5** `t_bccb64be`, **M6** `t_018b5307`. Only M0 is dispatchable today; the rest
are parent-gated.

| id | Card | Assignee | Skills | Parents | Acceptance criteria (checkable) |
|---|---|---|---|---|---|
| **M0** | Create and scaffold `disciples-playability` | `builder` (flash) | `github` | — | Repo at the path above, `main` pushed; `README`, `LICENSE` (MIT), `pyproject.toml` (src layout, `disciples-play` entry point), `docs/`, `scripts/`, `THIRD_PARTY.md` (cnc-ddraw MIT, DisciplesGL facts-only-and-why), this plan committed verbatim at `docs/plans/00-playability-plan.md`; `.gitignore` covering `*.EXE`, `*.DBF`, `*.dbi`, `*.dlg`, `*.dll`, `*.smk`, `*.wdb`, `*.sg`, `*.bin`, `*.cue`, `*.iso`, `*.img`, `Game files/`, `DISCIPLE.INI`; CI `.github/workflows/tests.yml` running pytest + ruff on ubuntu and windows-latest 3.10–3.13 (green on an empty-ish suite). If `POST /user/repos` returns 403 (fine-grained PAT), commit locally, post the exact repo-create instruction in a comment and continue. Verification block: `git ls-files` shows no forbidden extension, `git -C "/game-files/Disciples Gold" rev-parse` fails, CI green on `main`. |
| **M1** | INI model + rewrite core (`disciples_play/ini.py`) | `specialist` (pro) | `retro-game-modernization` | M0 | Order-, comment- and CRLF-preserving INI reader/writer (round-trip byte-identical on an untouched file); rewrites the 15 `[Installation]` + 6 `[InstallationClient]` keys; unknown keys/sections survive; `.orig` backup created exactly once and never overwritten; idempotent (second run is a no-op byte-wise); Windows-path emission via `winepath -w`, `Z:\` fallback, `--path-style {wine,relative}`; `--ini-mode backup\|inplace\|copy-tree`. Tests: ≥15 synthetic INI fixtures (no game bytes anywhere), including a moved-install fixture that reproduces the `X:\` breakage. Guard: `grep -rniE '[0-9a-f]{64}'` in the diff is empty. |
| **M2** | Launcher CLI (`disciples-play`) | `specialist` (pro) | `retro-game-modernization` | M1 | `disciples-play --game-dir DIR [--dry-run] [--print-command] [--wine PATH]`: validates install (`Disciple.exe` + `Exe/DISCIPLE.INI` present — resolves the *containing* directory, tolerating a nested `LOMAX/`-style drop), rewrites the INI, stages nothing it does not own, prints the exact wine command, and only execs when not `--dry-run`; exit codes documented (2 = bad install, 3 = rewrite refused); stderr clean on success. Tests drive the CLI over a synthetic install tree (fixture `Disciple.exe` is a 2-byte stub — no game bytes) with a fake `wine` shim; no network, no Wine required. |
| **M3** | cnc-ddraw preset + pinned fetch (`disciples_play/wrapper.py`) | `specialist` (pro) | `retro-game-modernization`, `github` | M1 | Preset `ddraw.ini` written with documented keys only (`windowed`, `maintas`, `maxfps`, `vsync`, `adjmouse`, `renderer`, `shader`, `savesettings`, `singlecpu`, `noactivateapp`, `nonexclusive`, `hook` — key names verified against upstream `src/config.c`); fetch `cnc-ddraw.zip` from release tag **`v7.1.0.0`** with a pinned SHA-256, refuse on mismatch/redirect; install into the game dir only on explicit `--install-wrapper`; ship cnc-ddraw's MIT `LICENSE` text and a provenance note (tag, URL, digest). Tests: zip fixture (our own, not upstream's), digest-mismatch abort, ini round-trip. **No game folder is touched by tests.** Documented `WINEDLLOVERRIDES="ddraw=n,b"` and the `InWindow=0` requirement in the same card's docs. |
| **M4** | `doctor` + reproducible Wine recipe | `specialist` (pro) | `retro-game-modernization` | M2, M3 | `disciples-play doctor --game-dir DIR` reports pass/fail lines for: install dir, INI writable, wine present + version, `ddraw=n,b` in the prefix, DPI, cnc-ddraw present, music files present — **sizes and paths only, never hashes or content**; exits 0/1/2 documented. `docs/wine-recipe.md` with three recipes (plain `wine`, Bottles, Heroic/Proton) each as a copy-paste block; `scripts/probe-matrix.sh` that runs the four `DDraw × PaletteAnim` combinations and writes a report the human can paste back. |
| **M5** | Data-layout document + read-only `data` subcommand | `specialist` (pro) | `retro-game-modernization`, `codebase-inspection` | M0 | `docs/data-layout.md`, every claim graded D/H/V with the command beside it: dBase III field tables (verified arithmetic on ≥3 tables), `MQDB` container scanner that prints **chunk offsets and sizes only** (no pixels, no art) with both endiannesses evaluated and scored, `.dlg` text grammar, `PALANIM.DAT` text, `.MFT` fonts, `.wdb` sound, `.smk` video; `disciples-play data --game-dir DIR` prints the same as JSON. Unknowns become explicit open questions, never filled in by plausibility. |
| **M6** | v0.1 release candidate + release notes | `lead` (pro) | `github`, `retro-game-modernization` | M2, M3, M4, M5 | `main` green on ubuntu+windows CI; `docs/quickstart.md` (3 commands: install, doctor, play); `CHANGELOG.md` entry; `docs/verification.md` containing the human checklist from [§8](#8-what-must-be-verified-on-the-maintainers-machine) with every item marked *unverified* until the maintainer runs it; tag **not** pushed by the agent — the card hands the maintainer the tag command; release notes state plainly what is unverified. |

Board mechanics: M0 uses `workspace_kind="dir"`, `workspace_path=/home/nwah/Development/RetroLab`
(the repo does not exist yet). M1–M6 use `workspace_kind="worktree"` with
`workspace_path=` the repo path — explicit, so the worktree lands inside the
bind mount instead of somewhere the worker cannot see. If M0 fails, everything
downstream stays in `todo`, which is the correct failure mode.

## 5. The smallest slice that proves the concept

**M0 → M1 → M2 → M3** (four cards, four reviews): scaffold, INI rewrite, launcher,
cnc-ddraw preset. Expected **772k in / 489k out ≈ $1.9**, ~95 min of agent
wall-clock, and **~35 minutes of the maintainer's time** (four probe runs, ~5 min
each, plus one 20-minute play session).

The gate, exactly: on the maintainer's machine,

```bash
disciples-play doctor --game-dir "$HOME/Development/RetroLab/Game files/Disciples Gold"
disciples-play --game-dir ".../Disciples Gold" --dry-run      # shows the rewrite + command
disciples-play --game-dir ".../Disciples Gold"                # plays, or does not
```

Then answer the eight items in [§8](#8-what-must-be-verified-on-the-maintainers-machine)
that do not need M4/M5. If it does not play, **stop**: ~$1.9 expected / $3.8 at
×2 is the whole sunk cost, and the INI rewriter is reusable regardless.

Cheaper still: fold M1 into M2 (one card, one review) to save ~$0.5 — at the cost
of a 500-line untested-by-itself core. Not recommended; noted so the tradeoff is
the maintainer's, not mine.

## 6. Budget: tokens and money

Unit: the `retrolab` board's measured anchors, from its
`docs/roadmap/40-budget.md` §2 — builder implementation 55k in / 21k out (flash,
$0.09/$1.28 per M), specialist implementation 100k / 55k (pro, $0.45/$3.40 per M),
research investigation 79k / 36k, review pass 40k / 35k, lead synthesis 60k / 40k,
lead planning 95k / 82k. Rework factors follow that document too: 1.5× expected /
2.0× high for normal build work (the board measured a **41.9 % changes-required
rate**, so 1.5× is not pessimism), 2.0× / 3.0× for unfamiliar exploratory work,
1.1× / 1.25× for trivially verifiable work. Review is priced per card.

| Card | low in/out | **expected in/out** | high in/out | $ expected (natural mix) | $ expected (all-pro) | agent minutes |
|---|---|---|---|---|---|---|
| M0 scaffold | 95k / 56k | 142k / 84k | 190k / 112k | $0.25 | $0.35 | 17 |
| M1 INI core | 140k / 90k | 210k / 135k | 280k / 180k | $0.55 | $0.55 | 26 |
| M2 launcher | 140k / 90k | 210k / 135k | 280k / 180k | $0.55 | $0.55 | 26 |
| M3 cnc-ddraw preset | 140k / 90k | 210k / 135k | 280k / 180k | $0.55 | $0.55 | 26 |
| M4 doctor + recipe | 140k / 90k | 210k / 135k | 280k / 180k | $0.55 | $0.55 | 26 |
| M5 data layout | 119k / 71k | 238k / 142k | 357k / 213k | $0.59 | $0.59 | 26 |
| M6 v0.1 RC | 100k / 75k | 110k / 82k | 125k / 94k | $0.33 | $0.33 | 21 |
| **total, 7 cards** | **874k / 562k** | **1,330k / 848k** | **1,792k / 1,139k** | **$3.39** | **$3.48** | **168** |

All-flash variant of the expected column: **$1.21**. This planning card is
already spent: 95k / 82k ≈ **$0.32**.

**Totals including this planning card: ≈1.43M in / 0.93M out, $3.71 off-peak
natural mix.** Agent wall-clock ≈ **2.8 h** clean, 4.1 h at ×1.5, 5.5 h at ×2.

**Uncertainty, stated honestly.** The retrolab board overran its forecasts by
**2–3×**, and its own budget document records that the board database never
recorded token counts — so those forecasts were never reconciled on the token
axis, only on wall-clock. Applying that measured drift to this plan:

| Scenario | input | output | money (off-peak) |
|---|---|---|---|
| expected (1.5×/1.1× rework already applied) | 1.43M | 0.93M | **$3.7** |
| ×2 (retrolab's lower drift) | 2.85M | 1.86M | **$7.4** |
| ×3 (retrolab's upper drift) | 4.28M | 2.79M | **$11.1** |

Peak-hour execution doubles every dollar figure. So: **plan on $4, budget $11,
and stop at the §5 gate if it is not playing.** The stop-cheaply slice (M0–M3)
is **$1.9 expected / $3.8 at ×2**.

Two honest caveats on the model itself: (a) the anchors are per-card averages
from a *different* project whose work was file-format archaeology, and this
project's cards are smaller and more mechanical, so 1.5× may be pessimistic for
M1–M4 — the ×2/×3 band is the counterweight, not a contradiction; (b) human
verification time (~1.5 h across the whole plan) is not in these numbers and
cannot be delegated.

## 7. Risks, each with its cheapest retiring experiment

| # | Risk | Cheapest experiment | Cost | If it fires |
|---|---|---|---|---|
| R1 | The game resolves `[Installation]` values **relative** to its own directory, making the whole absolute-path rewrite unnecessary (or worse, it needs `..\` forms) | **E1**: copy the INI, set `globals=Globals` and friends, launch, load the autosave (3 min, human) | 3 min | M1/M2 shrink to "write a static relative INI"; ~35 % of the slice's tokens saved. **NOT RESOLVED (tested 2026-11-20, falsified)** — E1's first result ("plays alright") was a maintainer misreport. Retests: bare relative names launched from `Exe` fail with "unable to load fonts" (fonts live at the install root); `..\`-prefixed names load fonts but stop on `DB error opening file ..\interf\Tapp.dbf` — a case-sensitivity mismatch (`Interf/TApp.dbf` on disk vs `interf/Tapp.dbf` in the game) that the INI cannot fix. Absolute rewriting stays the baseline. |
| R2 | cnc-ddraw's window path breaks the 8-bit palette animation (palette shimmer, stuck cursor colours) | **E2**: run the 4-way `DDraw × PaletteAnim` matrix via `scripts/probe-matrix.sh` (10 min, human) | 10 min | Ship `PaletteAnim=0` in the preset; document the tradeoff |
| R3 | cnc-ddraw requires the game fullscreen, but the game's own windowed path fights it | **E3**: one run with `InWindow=0` + cnc-ddraw windowed (2 min, human) | 2 min | Preset pins `InWindow=0`; document; if it still refuses, fall back to `InWindow=1` GDI and measure frame drops |
| R4 | Mouse targeting is offset in a scaled window (adjmouse), or the cursor escapes to the second monitor | **E4**: click a unit and a menu button at 3× (5 min, human) | 5 min | Tune `adjmouse` / `Ctrl+Tab` unlock; worst case: windowed at 1× |
| R5 | `Config.exe` rewrites the INI back to absolute paths after the launcher fixes it | **E5**: run `Config.exe`, save, `diff` the INI (2 min, human) | 2 min | Launcher re-applies on every start (already the design); add a warning line |
| R6 | The fine-grained PAT cannot create a repository (`POST /user/repos` 403) | **E6**: M0 attempts it and falls back to "human creates the repo, agent pushes" (built into M0's AC) | 1 min | One manual step for the maintainer, no plan change |
| R7 | Smacker video (478 MB of `.smk`) hangs or crashes under cnc-ddraw | **E7**: let the intro play once (2 min, human) | 2 min | Preset sets `Intro=0`; note it in the recipe |
| R8 | Budget overruns 2–3× as on retrolab | The §5 gate plus per-card spend comments; **no `goal_mode` cards**, no unbounded loops | — | Stop at M3; the rewriter is already useful |
| R9 | No Wine in the agent sandbox: every "it plays" claim is human | Not retirable — mitigated by design: INI fixtures, `--dry-run`, `--print-command`, fake-wine shim in tests | — | Keep it visible: `docs/verification.md` ships with every line *unverified* |
| R10 | Third-party zip changes under us (release re-tagged, asset replaced) | Pinned tag + SHA-256, refuse on mismatch (M3) | — | Update the pin in a PR, with the digest in the diff |

## 8. What must be verified on the maintainer's machine

The sandbox has no Wine and no display; an agent can prove the INI rewrite
arithmetically and nothing else. Every line below is a **human** check, and the
repo's `docs/verification.md` must ship with them all marked *unverified*.

1. `Disciple.exe` reaches the main menu — no black screen, no error dialog.
2. The window opens at **1920×1440** (3× of 640×480) on the 2560×1440 display,
   integer-scaled, not blurry; note the fallback (2× = 1280×960) if it does not.
3. **Alt+Enter** toggles windowed/fullscreen; **Alt+Tab** away and back does not
   corrupt the display.
4. **Mouse**: clicking a map tile and a menu button hits what is under the
   cursor at 3× scale; the cursor does not escape to the second monitor.
5. **Palette animation**: water/fire/the animated cursor animate without stripes
   or stuck colours (this is the `PaletteAnim=1` claim).
6. **Music** plays in-game from the 25 local `.wav` files with the CD absent;
   SFX audible; both volume sliders behave.
7. Load `Savegame\AutoSave.sg`, play 10 turns, save, reload — no path errors.
8. **Portability (the core claim)**: move the install folder to a new path, run
   `disciples-play --game-dir <new path>`, and it boots without hand-editing the
   INI. Then move it back.
9. `Config.exe` still opens and saves; note in the report whether it clobbers
   the rewritten INI (that is E5).
10. A **second prefix** from the `docs/wine-recipe.md` recipe (Bottles or plain
    `wine`) reproduces items 1–3.
11. Cleanliness: `git -C "/game-files/Disciples Gold" rev-parse` fails, and
    `git ls-files` in the repo contains no `*.EXE`, `*.DBF`, `*.dbi`, `*.smk`,
    `*.sg` — i.e. no game bytes were published.

## 9. Open questions

| # | Question | Currently | How it gets answered |
|---|---|---|---|
| Q1 | Does the game accept relative paths in `[Installation]`? | **H** — relative values resolve against the CWD, not the module dir: bare names fail from `Exe` ("unable to load fonts"), `..\`-prefixed names load fonts but stop on `DB error ..\interf\Tapp.dbf` (case mismatch). Absolute rewriting is the baseline | E1 retracted (two in-game failures, see §7 R1); a case-sensitivity shim is the real Linux fix |
| Q2 | Which module creates the DirectDraw object — `HA312W32` or `SHW32`? | **V** — neither via `LoadLibrary`: measured 2026-11-22, `Disciple.exe` itself calls `CoCreateInstance(CLSID_DirectDraw)` through `ole32` (the renderer lives in `Disciple.exe`); `SHW32.DLL` is SmartHeap, not the graphics layer | resolved in the headless rig; see `docs/wine-recipe.md` "Known crash at start-up" |
| Q3 | Does the game read `EXE\Disciple.ini` relative to the module path or the CWD? | **H** (string `EXE\Disciple.ini` present) | M2 test once on the host; launcher must not rely on CWD either way |
| Q4 | Does palette animation survive cnc-ddraw's windowed OpenGL renderer? | **H** | E2 |
| Q5 | `MQDB` layer table layout (per-entry offsets, compression?) | **H** — magic and version only | M5, by chunk scanning with competing hypotheses scored |
| Q6 | Is the case-insensitive directory resolution Wine, or a Win32 API in `C4DLL-R.DLL`? | **H** | Not blocking; note in data-layout doc |

## 10. What this plan deliberately does not claim

- It does not claim the game will **play well** — no agent here can launch it.
- It does not claim Windows works; CI green on `windows-latest` is not a play test.
- It does not promise widescreen. The honest answer on 640×480 is "the UI is
  640×480 in the dialog scripts; this pack scales the pixels, it does not add
  screen real estate".
- It does not reuse DisciplesGL or the HD mod in any form; both are cited as
  facts only, and `THIRD_PARTY.md` says so with the licence check beside it.
