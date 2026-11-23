# Verification — what a human must run before v0.1.0 is real

**Status: every item below is UNVERIFIED** — with partial results recorded under
item 1. No agent in this project has a display, so nothing here has been
observed in-game by an agent. The test suite proves the
INI rewrite, the CLI contract, the doctor's checks and the data scanner against
synthetic fixtures (269 tests here; 271 with the two permission tests this
container cannot run, see the command block below) plus a read-only pass over
the retail install
(2 tests); it cannot prove the game *plays*.

**Partial result (maintainer, 2026-11-21):** the main menu **was** reached and
the game played under **Heroic + Proton-GE** — by pressing Play in Heroic, with
the install's **original `X:\…` INI** and, in a later run, with **the pack's
rewritten `Z:\…` values** put in place by `disciples-play --no-launch`.

**Partial result (maintainer, 2026-11-22, system Wine 11.21):** the command the
launcher now runs by default reached the main menu — `wine explorer
/desktop=Disciples,640x480 Disciple.exe` with `InWindow=0`, typed at the shell
from the install's `Exe/` on a 2560×1440 screen, not through `disciples-play`
itself (the launcher emits that same argv). The menu responds and the mouse
cursor lines up with the drawn menu (the pointer sat on QUIT in the screenshot),
so input is 1:1. Observed appearance: the game's 640×480 surface sits in the
**top-left corner**, the rest of the desktop is black, no title bar and no
border; the cause is unknown (the session is KDE Plasma on Wayland — reported the
same day — and `[H]` that Xwayland/KDE treat the fullscreen request differently
from an ordinary window; not measured). Only
the 640x480 default has been tried on this machine.

Item 1 still stays unticked: a human has to run it and tick it. Plain `wine`
crashed at `0059559E` on the maintainer's machine (the
2026-11-21 run); the launcher's virtual desktop is the pack's workaround, and the
headless rig reproduced both sides (card `t_2504e165`, R1–R7). The recipes are in
[`wine-recipe.md`](wine-recipe.md) "Start here".

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

**Items 2–5 are blocked on something else, not on a setting.** The wrapper can
only present a window if the game loads it, and the renderer does not: it asks COM
for DirectDraw and COM resolves `system32\ddraw.dll` (measured — see
[`wine-recipe.md`](wine-recipe.md) "Known crash at start-up"). So no value of
`InWindow` makes items 2–5 pass today; they wait on the COM redirect, not on a
precondition a reader can set.

`doctor` reports the key as its **`ini-window`** line: `PASS` for
`InWindow=0`, `WARN` for `InWindow=1` in every case, and `WARN` for a missing
key. With a verified wrapper it says the title's renderer never loads it; without one it
says windowed presentation is not delivered by this pack. Either way the key is
your own display choice. That WARN is a configuration
guard only — it is neither a ticked box nor a claim about the start-up crash.

**The start-up crash is a display-mode crash.** On 2026-11-21 the game died with
`Exception C0000005` at `0059559E` after its own start-up log line — with
`InWindow=0` **and** `InWindow=1`, so the `InWindow` *setting* is ruled out. What
the trace shows is a `SetDisplayMode(640, 480, 8)` request refused immediately
before the fault. On 2026-11-22 the same build started inside a 640×480 Wine
virtual desktop, and the headless rig showed the same split (refused without such
a mode, accepted with one; card `t_2504e165`). The evidence is in
[`wine-recipe.md`](wine-recipe.md#known-crash-at-start-up-0059559e-on-plain-wine-without-a-virtual-desktop).
Item 1 cannot be ticked until a human runs the pack's own command and records
the result (see item 1's note) — the 2026-11-22 run is that observation, not the
tick.

---

## The eleven checks

- [ ] **UNVERIFIED** — **1. Main menu.** `Disciple.exe` reaches the main menu: no black screen, no error dialog.
  Command: `disciples-play --game-dir "$GAME"`. Record: what appeared, and the last 20 lines of terminal output if it did not.
  Note (2026-11-22): the command this pack's launcher now runs by default **did** reach the menu — `wine explorer /desktop=Disciples,640x480 Disciple.exe` with `InWindow=0` on the maintainer's 2560×1440 desktop (system Wine 11.21), typed at the shell rather than through `disciples-play` itself. The menu responds; the pointer lines up with it, so input is 1:1. The picture occupies the top-left corner and the rest of the desktop is black (cosmetic, cause unknown). The box stays unticked: this is the observation a human must confirm and tick, and only the 640x480 default was tried. Earlier note (2026-11-21): the menu was also reached by pressing Play in **Heroic + Proton-GE** — once with the install's original `X:\…` INI and once with the pack's rewritten `Z:\…` values.
- [ ] **UNVERIFIED** — **2. Window size.** The wrapper presents the game in a **640×480** window (the pack's base size, not a recorded video mode) and you resize it; record the size you settled on (1920×1440 = exactly 3×, 1280×960 = 2×) and whether the pixels stayed sharp.
  Note: the preset sets no window-size, `boxing` or `shader` key — it writes nine `[ddraw]` keys (`windowed`, `maintas`, `maxfps`, `vsync`, `adjmouse`, `savesettings`, `nonexclusive`, `hook`, `renderer`) and nothing else. Sharp integer scaling needs `boxing=true` or `shader=Nearest neighbor` added to `ddraw.ini` by hand (see [`wrapper.md`](wrapper.md)); record which one you used, because neither is the default.
  Note (2026-11-22): a cnc-ddraw-resized window was **not** observed — for this title's renderer the wrapper does not load (see the known gaps). The measured path to a bigger window is `gamescope -w 640 -h 480 -W 1920 -H 1440 -S integer -- wine explorer /desktop=Disciples,640x480 Disciple.exe` (maintainer, KDE Plasma on Wayland, 2560×1440, system Wine 11.21, `InWindow=0`): a 1920×1440 window, centred, with the game picture filling it — exactly 3× the game's 640×480. Whether the pixels stayed **sharp** was not assessed (gamescope's default upscaling filter is not nearest), so that half of this item is still open. Recipe: [`wine-recipe.md`](wine-recipe.md#bigger-window-a-gamescope-recipe-not-something-the-launcher-does). This path replaces the item's cnc-ddraw assumption; the box stays unticked for a human.
- [ ] **UNVERIFIED** — **3. Alt+Enter and Alt+Tab.** Alt+Enter toggles windowed/fullscreen; Alt+Tab away and back does not corrupt the display.
  Record: both transitions, and whether colours/size survive the round trip.
- [ ] **UNVERIFIED** — **4. Mouse targeting at 3×.** Clicking a map tile and a menu button hits what is under the cursor at 3× scale; the cursor does not escape to the second monitor.
  Record: the scale you tested at, and whether `adjmouse` / `Ctrl+Tab` unlock changed anything.
  Note (2026-11-22): at 3× under gamescope (`gamescope -w 640 -h 480 -W 1920 -H 1440 -S integer -- wine explorer /desktop=Disciples,640x480 Disciple.exe`, maintainer's KDE Plasma/Wayland machine, 2560×1440) **clicking menu items hits the item under the cursor** — mouse targeting at 3× works on that path. Not tested: whether the cursor can escape to a second monitor, and `adjmouse`/`Ctrl+Tab` behaviour (cnc-ddraw does not load for this renderer). The box stays unticked for a human.
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
| **Picture sits in the top-left corner of the virtual desktop.** [V] 2026-11-22, maintainer's desktop (system Wine 11.21, `wine explorer /desktop=Disciples,640x480 Disciple.exe`, `InWindow=0`, 2560×1440 screen, KDE Plasma on Wayland): the game's 640×480 surface occupies the top-left corner, the rest of the desktop is black, there is no title bar or border, and input is 1:1 (the pointer lines up with the drawn menu). | Cosmetic, every plain-Wine launch: the game is playable but the window looks unfinished. | Cause **unknown** — not investigated; `[H]` that Xwayland/KDE treat the fullscreen mode request differently from an ordinary window (not measured). A `gamescope` recipe that does fill a centred 1920×1440 window was measured once the same day ([`wine-recipe.md`](wine-recipe.md#bigger-window-a-gamescope-recipe-not-something-the-launcher-does)) but nothing in the pack positions or scales this surface. |
| **Plain-Wine start-up crash (`0059559E`) without a virtual desktop.** `Disciple.exe` dies with `C0000005` — a null object from the graphics layer — under plain `wine` (wine-staging 11.21, default prefix) on the maintainer's machine: with the wrapper staged and `WINEDLLOVERRIDES=ddraw=n,b`, with no wrapper, and with `InWindow=0` or `InWindow=1`. The rig reproduced both sides (refused `SetDisplayMode(640,480,8)` on a 1920x1440 Xvfb, accepted once a 640x480 resolution existed; card `t_2504e165`). | `--no-virtual-desktop` on the maintainer's display: an access violation instead of a game. | **Worked around by the launcher**: it now starts the game in a 640x480 Wine virtual desktop by default (verified on the maintainer's desktop 2026-11-22; rig R5–R7). The mechanism behind the refusal is still `[H]`. `DDraw=0` still starts to a black screen. |
| **The renderer does not load the staged cnc-ddraw.** The game acquires DirectDraw through `CoCreateInstance(CLSID_DirectDraw)`, and COM resolves `HKCR\CLSID\{D7B70EE0-…}\InprocServer32` → `system32\ddraw.dll`; a DLL in `Exe\` is not on that path. Measured. (`SMACKW32.DLL`'s by-name video path is static evidence only and untested.) (The `InprocServer32` redirect named in this row's last column is **untested** — no experiment in the tree attempts it, so nothing here should be read as a ruled-out path.) | Every windowing/scaling claim, and items 2–5 entirely. | Register the DLL as `CLSID_DirectDraw`'s `InprocServer32` in the prefix (the only remaining Wine-side candidate) and re-run; or drop the wrapper from v0.2's claims. |
| **No one-line wrapper install.** `disciples_play.wrapper` fetches the pinned `cnc-ddraw` release and writes the preset, but no CLI subcommand calls it yet. | Copying `ddraw.dll`/`ddraw.ini` into `Exe/` by hand is the only way to stage it — and for the renderer that changes nothing, because it never loads it (row above; the video player's by-name load is untested). The missing command is a packaging gap, not a path to a window. | A `disciples-play wrapper --install` card (needs `--game-dir`, the digest pin, the licence text, an overwrite guard — all already implemented as functions) — worth doing for the titles that *do* load ddraw by name. |
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
python -m pytest -q                    # 269 passed, 2 skipped (realgame) in a root/container
                                       # shell; 271 passed where chmod binds (CI)
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
