# Verification — what a human must run before v0.1.0 is real

**Status: every item below is UNVERIFIED** — with one partial result recorded
under item 1. No agent in this project has a display or a Wine runtime, so
nothing here has been observed in-game by an agent. The test suite proves the
INI rewrite, the CLI contract, the doctor's checks and the data scanner against
synthetic fixtures (226 tests) plus a read-only pass over the retail install
(2 tests); it cannot prove the game *plays*.

**Partial result (maintainer, 2026-11-21):** the main menu **was** reached and
the game played under **Heroic + Proton-GE** — by pressing Play in Heroic, with
the install's **original `X:\…` INI** and, in a later run, with **the pack's
rewritten `Z:\…` values** put in place by `disciples-play --no-launch`. What has
not worked is the pack's own launch (`disciples-play --game-dir …`) under plain
`wine`, which crashes at `0059559E`.
Item 1 stays unticked for that reason. Plain `wine` crashes at start-up for
this title (`0059559E`, null pointer in the graphics layer); the supported
sequence is in [`wine-recipe.md`](wine-recipe.md) "Start here".

This file is the release's honest boundary. Tick a box **only** after running
that item on a real machine with the game, and record the machine, the date and
what you saw on the line. Items are the plan's §8 list, verbatim in meaning:
[`plans/00-playability-plan.md` §8](plans/00-playability-plan.md#8-what-must-be-verified-on-the-maintainers-machine).

Setup for every item:

```bash
pip install -e .                                  # or: pipx install .
export GAME="$HOME/Development/RetroLab/Game files/Disciples Gold"   # your path
disciples-play doctor --game-dir "$GAME"
```

**Items 2–5 precondition:** the wrapper only presents a window when the *game*
is fullscreen, i.e. `InWindow=0` in `Exe/DISCIPLE.ini`. The launcher never writes
that key (the 21 installation paths are the only thing it rewrites) and a retail
install may ship `InWindow=1`, so set it before running items 2–5 — otherwise
you will record a windowing failure that is a setting, not a defect.

`doctor` reports the key as its **`ini-window`** line: `PASS` for
`InWindow=0`, `WARN` for `InWindow=1` in every case (with a verified cnc-ddraw
it says the wrapper needs the game fullscreen; without one, that windowed
presentation needs it), `WARN` for a missing key. That WARN is a configuration
guard only — it is neither a ticked box nor a claim about the start-up crash.

**The start-up crash is separate and unresolved.** On 2026-11-21 the game died
with `Exception C0000005` at `0059559E` after its own
start-up log line — with `InWindow=0` **and** `InWindow=1`. The `InWindow`
*setting* is ruled out; the 640x480x8 mode request that the trace shows being
refused immediately before the fault is a separate, open question. The evidence
and the open candidates are in
[`wine-recipe.md`](wine-recipe.md#known-crash-at-start-up-0059559e-unresolved-on-plain-wine).
Item 1 cannot be ticked until the pack's own command is what reaches the menu
(see item 1's note); a Proton-aware launch path would satisfy that without
resolving `0059559E`.

---

## The eleven checks

- [ ] **UNVERIFIED** — **1. Main menu.** `Disciple.exe` reaches the main menu: no black screen, no error dialog.
  Command: `disciples-play --game-dir "$GAME"`. Record: what appeared, and the last 20 lines of terminal output if it did not.
  Note (2026-11-21): the menu **was** reached, but by pressing Play in **Heroic + Proton-GE** — once with the install's original `X:\…` INI and once with the pack's rewritten `Z:\…` values in place. Not by the command above: under plain `wine` that command crashes at `0059559E` (`C0000005`, null pointer in the graphics layer), with or without the wrapper staged; see [`wine-recipe.md`](wine-recipe.md) "Start here". The box stays unticked until the pack's own command is what reaches the menu on some Wine build or prefix.
- [ ] **UNVERIFIED** — **2. Window size.** The wrapper presents the game in a **640×480** window (the pack's base size, not a recorded video mode) and you resize it; record the size you settled on (1920×1440 = exactly 3×, 1280×960 = 2×) and whether the pixels stayed sharp.
  Note: the preset sets no window-size, `boxing` or `shader` key — it writes nine `[ddraw]` keys (`windowed`, `maintas`, `maxfps`, `vsync`, `adjmouse`, `savesettings`, `nonexclusive`, `hook`, `renderer`) and nothing else. Sharp integer scaling needs `boxing=true` or `shader=Nearest neighbor` added to `ddraw.ini` by hand (see [`wrapper.md`](wrapper.md)); record which one you used, because neither is the default.
- [ ] **UNVERIFIED** — **3. Alt+Enter and Alt+Tab.** Alt+Enter toggles windowed/fullscreen; Alt+Tab away and back does not corrupt the display.
  Record: both transitions, and whether colours/size survive the round trip.
- [ ] **UNVERIFIED** — **4. Mouse targeting at 3×.** Clicking a map tile and a menu button hits what is under the cursor at 3× scale; the cursor does not escape to the second monitor.
  Record: the scale you tested at, and whether `adjmouse` / `Ctrl+Tab` unlock changed anything.
- [ ] **UNVERIFIED** — **5. Palette animation.** Water, fire and the animated cursor animate without stripes or stuck colours (the `PaletteAnim=1` claim).
  This is plan risk **R2**. If it fails, the fallback is `PaletteAnim=0` plus the documented tradeoff, not a code fix.
- [ ] **UNVERIFIED** — **6. Music and SFX without the CD.** Music plays in-game from the 25 local `Music/*.wav` files with the CD absent; SFX are audible; both volume sliders behave.
  `doctor` reports the file count and size (25 `.wav`), never the audio itself.
- [ ] **UNVERIFIED** — **7. Save / load.** Load `Savegame\AutoSave.sg`, play 10 turns, save, reload: no path errors.
- [ ] **UNVERIFIED** — **8. Portability (the core claim).** Move the install folder to a new path, run `disciples-play --game-dir <new path>`, and it boots without hand-editing the INI. Then move it back.
  This is the one claim that distinguishes the pack from "install cnc-ddraw by hand"; if it fails, v0.1.0 has no reason to exist.
- [ ] **UNVERIFIED** — **9. `Config.exe`.** `Config.exe` still opens and saves; record whether it clobbers the rewritten INI (plan risk **R5**). The launcher re-applies the rewrite on every start either way.
- [ ] **UNVERIFIED** — **10. A second prefix.** A second prefix built from the [`wine-recipe.md`](wine-recipe.md) recipe (Bottles or plain `wine`) reproduces items 1–3.
  Record which recipe, the Wine/Proton version, and anything you had to change.
- [ ] **UNVERIFIED** — **11. Cleanliness.** `git -C "/game-files/Disciples Gold" rev-parse` fails, and `git ls-files` in this repository contains no `*.EXE`, `*.DBF`, `*.dbi`, `*.smk`, `*.sg` — i.e. no game bytes were published.
  The maintainer re-runs this against the repository they are about to tag; the agents' own run of the same commands is recorded in the M6 pull request.

---

## Known gaps carried into v0.1.0

These are things the cards did **not** deliver or could not verify. They are
listed here rather than smoothed over; each one is visible to a user.

| Gap | Where it bites | What would close it |
|---|---|---|
| **Plain-Wine start-up crash (`0059559E`).** `Disciple.exe` dies with `C0000005` — a null object from the graphics layer — under plain `wine` (wine-staging 11.21, default prefix): with the wrapper staged and `WINEDLLOVERRIDES=ddraw=n,b`, with no wrapper, and with `InWindow=0` or `InWindow=1`. `DDraw=0` starts with sound but a black screen. Heroic + Proton-GE plays. The pack's launcher execs a single `wine` binary and cannot drive Proton. | Following the launcher's own launch on a plain-Wine box (`disciples-play --game-dir …`, no `--no-launch`): an access violation instead of a game. | Nothing in this pack — a Wine-side fix, or a Proton-aware launch path after v0.1.0. Documented workaround: `disciples-play --no-launch`, then Play in Heroic/Lutris ([`wine-recipe.md`](wine-recipe.md) "Start here"). |
| **The staged cnc-ddraw was never loaded.** Every plain-Wine crash dump so far lists `system32\ddraw.dll` and `wined3d.dll`; the `ddraw.dll` in `Exe\` never appears, so items 2–5 have no evidence that the wrapper engages at all. | Any windowing/scaling claim: the preset may be inert on this title. | A run whose module list names the staged DLL; if none exists, a loader/hook investigation (upstream `hook` modes) before v0.2 claims windowing. |
| **No one-line wrapper install.** `disciples_play.wrapper` fetches the pinned `cnc-ddraw` release and writes the preset, but no CLI subcommand calls it yet. | A new user must copy `ddraw.dll`/`ddraw.ini` into `Exe/` by hand (quickstart §"Getting the window"). Without that, `windowed=1` never engages and items 2–5 cannot pass. | A small `disciples-play wrapper --install` card (needs `--game-dir`, the digest pin, the licence text, an overwrite guard — all already implemented as functions). |
| **Windows is unclaimed.** CI runs the suite on `windows-latest` 3.10–3.13, but no human has launched the game on Windows. | Any "works on Windows" reading of a green CI badge. | One run on a Windows machine; then update this file and the README. |
| **cnc-ddraw's release build writes no debug log.** `dbg_init()` is behind `#ifdef _DEBUG`, so a black screen leaves no `cnc-ddraw-*.log`. | Triage of a failed item 1. | Use the `experimental-debuglog` build for one run, as [`wine-recipe.md`](wine-recipe.md) says. |
| **`doctor` on a read-only install reports `FAIL ini`.** In the sandbox the retail copy is a read-only bind mount, so "INI not writable" is a true FAIL there; the maintainer's own copy is writable. `ini-paths` also FAILs on the retail INI's relative values until the launcher has rewritten them once. | Reading a `doctor` transcript from someone else's machine as if it were yours. | Run `doctor` on your own machine before and after one launch; the second run should show `ini-paths` PASS. |
| **Format semantics still hypotheses.** `MQDB` header `0x18`, the `MQRC` chunk field at `+0x0C`, chunk-id roles beyond 1/2/3, name-table trailing `u32`s, the `.wdb` codec and Smacker decode are **H**, with the falsifier named in [`data-layout.md`](data-layout.md#open-questions). | Anyone writing a mod against `docs/data-layout.md` — the geometry is V, the semantics are not. | The falsifiers listed per row (trace the reader in `C4DLL-R.DLL`, decode one payload, diff against a retail decode). |
| **Case-sensitivity is a separate defect.** The install holds both `DISCIPLE.INI` and `DISCIPLE.ini`, and `..\interf\Tapp.dbf` vs `Interf/TApp.dbf` is a data-layer case mismatch the INI cannot fix. | A launch that still fails after a clean `doctor` on a case-sensitive filesystem. | A later case-shim card; recorded in plan §7 R1 / §9 Q1 and [`cli.md`](cli.md) "Deliberate decisions". |
| **Relative INI paths are falsified in game.** `--path-style relative` exists but the game cannot load its data from bare folder names (plan R1), so the default is `wine` and `doctor` FAILs relative values. | Experimenting with `--path-style relative` and concluding the pack is broken. | Nothing to do; the option is documented as falsified, not offered as a choice. |
| **No packaging (PyInstaller/AppImage/wheel).** `pipx install .` / `pip install -e .` from a clone is the only install path. | A user expecting a binary. | Plan §2 defers packaging to v0.2, after a human signs off that the binary runs. |
| **Budget was never measured in tokens.** Profile logs are not mounted in the agent sandbox, so token spend is not measurable from the board; only per-card wall-clock was recorded (M6 card comment). | Any statement that the plan's token forecast was met or missed. | A `token_cost_report.py` run where the profile logs live (`~/.hermes/profiles/<profile>/`), or provider billing. |

---

## What the agents *did* verify (for contrast)

Run at the M6 head on Linux, Python 3.14 (the maintainer's Python 3.10–3.13 is
covered by CI):

```bash
python -m pytest -q                    # 226 passed, 2 skipped (realgame)
DISCIPLES_GAME_DIR="/game-files/Disciples Gold" python -m pytest -q tests/test_realgame.py
                                       # 2 passed, read-only against the retail copy
ruff check . && ruff format --check .  # clean
disciples-play data --game-dir "/game-files/Disciples Gold" --json   # exit 0, 314 files
disciples-play doctor --game-dir "/game-files/Disciples Gold"
                                       # exit 1 (the read-only mount: FAIL ini/ini-paths);
                                       # ini-window follows that copy's own InWindow:
                                       # WARN while 1 (wrapper or not), PASS at 0
                                       # (a configuration guard, not a crash fix)
```

That proves the code does what it says on the data it was given. It does not
prove the game runs, and no line above should be read as "it plays".

## Recording a result

Tick the box, replace **UNVERIFIED** with the date and machine, and put the
actual observation next to it. If an item fails, leave the box unticked, write
what you saw, and open an issue with the transcript — a failed item is a
finding, not a reason to delete the line.
