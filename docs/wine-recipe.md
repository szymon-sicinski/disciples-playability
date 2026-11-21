# Reproducible Wine/Proton recipes

> **Status: one path is verified, the rest are not.** The maintainer ran §3
> (Heroic + Proton-GE) on the real GOG install on 2026-11-21 and the game
> reached its main menu and played; that run is recorded in
> [`docs/verification.md`](verification.md). Everything else below is still a
> copy-paste start point a second machine should be able to follow — the
> "expected output" blocks describe what a correct run *would* show, not what
> has been observed. Plain `wine` has now been observed **not** to start this
> title: read the section below before trying it.

---

## Start here: plain Wine crashes at start-up — use a Proton runner

**If `Disciple.exe` dies with an access violation at `0059559E`, the launch
environment is the problem, not your INI.** Measured by the maintainer on
2026-11-21, real GOG install, `wine-staging` 11.21, default `~/.wine` prefix:

| Attempt | Result |
|---|---|
| plain `wine`, wrapper staged, `WINEDLLOVERRIDES=ddraw=n,b` | `C0000005` at `0059559E` |
| plain `wine`, no wrapper, `InWindow=0` / `InWindow=1` | same crash at `0059559E` |
| plain `wine`, `DDraw=0` (GDI fallback) | starts, sound, **black screen** |
| Heroic + Proton-GE, its own prefix, the pack's rewritten INI (21 keys → `Z:\…`) | **plays** ✅ |
| Heroic + Proton-GE, its own prefix, the original `X:\…` INI | **plays** ✅ |

The crash is `mov ecx,[eax] ; call [ecx+0x58]` with `EAX=0` — a null object
handed back by the graphics layer, i.e. Wine's own `ddraw` never returns a
usable interface for this title under that prefix. **Nothing in this pack fixes
that, and nothing here claims it does:** it is a limitation of plain `wine` as
a launch environment, not a pack defect and not an INI problem.

The pack's launcher execs a **single `wine` binary** (override with `--wine`)
and has no Proton / `STEAM_COMPAT_*` path, so it cannot start the game inside a
Heroic or Lutris Proton prefix. The supported sequence is therefore: let the
pack rewrite the INI, then start the game from your runner.

```bash
disciples-play --no-launch --game-dir "<install>"   # rewrites the 21 keys only
# then press Play in Heroic / Lutris with a Proton runner
```

One fact to keep straight, because it changes what the pack is for: that same
Proton prefix plays **with the original `X:\…` values too**. The rewrite is not
what makes the game run — the Proton runner is. The rewrite is what makes the
install *portable*: a folder you move still finds its data, in either runner.

**cnc-ddraw was not in the picture in any of those runs.** Module dumps from
every attempt (failing and working) list `C:\windows\system32\ddraw.dll` and
`wined3d.dll`; the `ddraw.dll` staged in `Exe\` was never loaded. That does not
prove the wrapper is useless — it proves none of the results above depend on
it. Do not credit it with the working run.

---

Three ways to get a prefix. Each one ends with the `disciples-play` launcher
doing the INI rewrite, and — under plain Wine and Bottles — with a `ddraw`
override that routes DirectDraw to the staged `cnc-ddraw` DLL. Only the Proton
path (§3) has actually started this title so far.

The one thing every recipe shares is the **override**. `Disciple.exe` does not
import DirectDraw — `HA312W32.DLL` loads `ddraw.dll` by name — so a
`ddraw.dll` dropped next to `Disciple.exe` plus a `ddraw=n,b` override is
*meant* to take over the whole graphics layer. `n` = native (load our DLL),
`b` = builtin fallback. Treat that as the pack's intended presentation path,
not as a measured result for this title (see the caveat above and
[`verification.md`](verification.md) items 2–5, all still unticked). See
[`wrapper.md`](wrapper.md) for why, and the `doctor` subcommand for checking
that the override is at least in effect:

```bash
disciples-play doctor --game-dir "/path/to/Disciples Gold"
```

---

## 1. Plain Wine

> **Observed not to start this title** (maintainer, 2026-11-21): plain `wine`
> crashes at `0059559E` with or without the wrapper staged — see
> [Start here](#start-here-plain-wine-crashes-at-start-up--use-a-proton-runner).
> The recipe is kept because a different Wine build or prefix may behave
> differently, and because `DDraw=0` at least starts the game (black screen).

The simplest path: one prefix, one override, done. The override can be set two
ways — per-run via `WINEDLLOVERRIDES` (the launcher does this automatically
once the wrapper is staged), or permanently via `winecfg`.

**1a. Create the prefix and boot it once** (this installs the Wine runtime into
the prefix; it must run once before the game):

```bash
WINEPREFIX=~/.local/share/wineprefixes/disciples wineboot -u
# expected: wineboot prints its normal boot messages and exits 0; a fresh
#           prefix takes ~10-30 s the first time.
```

**1b. Set the `ddraw` override permanently** (alternative to per-run env):

```bash
WINEPREFIX=~/.local/share/wineprefixes/disciples winecfg
# expected: the winecfg window opens. In the Libraries tab, "New override for
#           library" -> type "ddraw" -> Add -> Edit -> "Native then Builtin".
#           (Or skip this: the launcher sets WINEDLLOVERRIDES=ddraw=n,b itself
#           whenever it finds ddraw.dll staged.)
```

**1c. DPI.** Leave Wine's DPI at the default 96 — cnc-ddraw owns the scaling,
and a high DPI can blur the game's fixed 640×480 menus. In `winecfg` →
Graphics, "Screen resolution" should read **96 dpi**. (Unverified: the safe
default is documented, not a measured requirement.)

**1d. Stage cnc-ddraw, then launch.** cnc-ddraw must sit next to `Disciple.exe`
before the override does anything. The pack's `disciples_play.wrapper` module
fetches the pinned release and installs it (see
[`wrapper.md`](wrapper.md)); until that is wired to a one-line command, do the
same by hand: download cnc-ddraw `v7.1.0.0` and copy `ddraw.dll` (and
`ddraw.ini`) into `Exe\` next to `Disciple.exe`.

```bash
disciples-play --game-dir "/path/to/Disciples Gold" --dry-run
# expected: prints the INI diff (21 keys) and the exact wine command, without
#           writing or launching.

disciples-play --game-dir "/path/to/Disciples Gold"
# expected: "rewrote 21 installation keys (backup at …/Exe/DISCIPLE.INI.orig)"
#           then Wine starts the game. Under plain Wine that launch currently
#           ends at 0059559E with the wrapper staged (see "Start here"), so for
#           play use `--no-launch` here and start the game from a Proton runner.
```

---

## 2. Bottles

> **Expected to hit the same start-up crash as §1.** Bottles wraps a `wine`
> runner, so unless you point it at Proton it is plain Wine with a GUI — and
> plain Wine crashes at `0059559E` for this title (see "Start here"). Untested
> with a Proton runner in Bottles.

Bottles wraps the same Wine prefix in a GUI. The parts that matter are the
**bottle template**, the **DLL override field**, and the **locale/DPI**.

1. Create a bottle with the **"Gaming"** template (a "Custom" bottle also
   works — the template only pre-tunes libraries this game does not need).
2. Open the bottle → **Settings → Components / Dependencies** (the name varies
   by Bottles version) → add a **DLL override** for `ddraw` set to
   **"Native, then Builtin"**. This is the `ddraw=n,b` equivalent; it is the
   one override the game needs.
3. **Locale**: set the bottle locale to `en_US.UTF-8` (the GOG build is
   English; a mismatch can show empty text). **DPI**: leave at 96 — cnc-ddraw
   scales, a high DPI blurs the fixed 640×480 menus.
4. From the bottle's **"Run Executable"** (or "Open terminal"), run the pack's
   launcher. That shell already has `wine` pointing at the bottle's runner and
   `WINEPREFIX` set, so the launcher (which execs `wine` from `PATH`) launches
   inside the bottle:

   ```bash
   disciples-play --game-dir "/path/to/Disciples Gold"
   # expected: the INI rewrite summary; then the game starts — expect the §1
   #           start-up crash unless that bottle's runner is Proton.
   ```

   From a *host* shell the launcher would pick the host's plain `wine`, not the
   bottle's runner, so pass the bottle's runner explicitly instead:
   `disciples-play --wine <runner>/bin/wine --game-dir …` (the runner path is
   shown under the bottle's **Settings → Runner**).

> Bottles field names shift between versions; the invariants are the bottle
> (any), the `ddraw` override (native,builtin) and DPI 96. If a field is
> missing, do the same thing in plain `winecfg` (see §1) against the bottle's
> prefix. A Bottles installed via **Flatpak** (the common case) keeps bottles
> under `~/.var/app/com.usebottles.bottles/data/bottles/<name>`; a native
> install uses `~/.local/share/bottles/bottles/<name>`. When in doubt, read the
> prefix path from the bottle's **Settings → Components** (or the details page).

---

## 3. Heroic / Proton

> **This is the verified path** (maintainer, 2026-11-21): Heroic with a
> Proton-GE runner reached the main menu and played, both with the pack's
> rewritten INI and with the original `X:\…` values. No wrapper was staged in
> that run, so nothing here credits cnc-ddraw with it.

The existing prefix named in `Exe\Disciple.log` (`X:\Games\Heroic\…`) came from
a Heroic install, so this is the path that reproduces what the maintainer
already has.

1. Add the game in Heroic (or use the existing entry), then open its
   **Settings → Wine / "Other"** panel.
2. Set the environment override so Proton loads the native `ddraw.dll`:

   ```
   WINEDLLOVERRIDES = "ddraw=n,b"
   ```

   (Heroic exposes this under the game's **"Environment Variables"** field —
   one `NAME = VALUE` pair per line.)
3. **Proton's own ddraw can fight the wrapper.** Proton ships its own DirectDraw
   translation; without the override, Proton's built-in is used and cnc-ddraw's
   windowed/upscaled presentation never engages. With the override set *and*
   `ddraw.dll` staged next to `Disciple.exe`, the native DLL wins. If the game
   still opens in Proton's own mode, confirm the override is spelled exactly
   `ddraw=n,b` and that `ddraw.dll` really sits in `Exe\`. (Unverified: no run
   so far has shown the staged DLL being loaded — module dumps name
   `system32\ddraw.dll` and `wined3d.dll` every time. Treat the override as an
   experiment, not a requirement to start.)
4. DPI: leave at 96 (same reasoning as §1c). The pack's launcher always execs a
   single `wine` binary — it has no Proton/`STEAM_COMPAT_*` path — so it cannot
   launch under the Heroic Proton prefix you just configured. Use the pack for
   the INI rewrite, then launch from Heroic itself:

   ```bash
   disciples-play --game-dir "/path/to/Disciples Gold" --no-launch
   # expected: "rewrote 21 installation keys …" (no launch).
   ```

   then press **Play** in Heroic. (To drive Proton directly from a shell instead,
   set `STEAM_COMPAT_DATA_PATH`, `STEAM_COMPAT_CLIENT_INSTALL_PATH` and
   `WINEDLLOVERRIDES=ddraw=n,b` and run `proton run Exe/Disciple.exe` — that is
   the Proton equivalent of the launcher's wine exec; the pack does not do it
   for you today.)

---

## If the screen is black

For any recipe, in this order:

1. **Game fullscreen, wrapper windowed.** cnc-ddraw requires the *game* to be
   fullscreen (`InWindow=0`); windowing comes from the wrapper. A game that is
   itself windowed fights cnc-ddraw. Confirm `InWindow=0` in `Exe\DISCIPLE.INI`
   (the launcher does not change it).
2. **Override in effect.** `disciples-play doctor --game-dir …` → the
   `ddraw-override` line must be PASS. If not, set `WINEDLLOVERRIDES=ddraw=n,b`
   (or the winecfg/Bottles/Heroic equivalent above).
3. **Fall back renderer.** cnc-ddraw reads `ddraw.ini` from next to the game
   executable; edit it to set `renderer=gdi` (the software fallback — the most
   compatible renderer when OpenGL/Direct3D9 misbehave under a driver or
   Proton). See [`wrapper.md`](wrapper.md) for the key.
4. **Intro hangs.** Smacker cutscenes can hang under a wrapper; set `Intro=0`
   in the game's INI (or in the wrapper preset) and retry — that is risk R7 in
   the plan, not a blocker.

## Producing cnc-ddraw's debug log

The released `ddraw.dll` (v7.1.0.0 — the one these recipes install) writes **no
log**: upstream gates `dbg_init()` behind `#ifdef _DEBUG`, so a black-screen
triage with the release build finds no `cnc-ddraw-*.log` at all. To collect a
log, swap in the debug build for one run only:

1. Download `cnc-ddraw-experimental-debuglog.zip` from upstream's releases and
   copy *its* `ddraw.dll` over the one in `Exe\` (back up the release DLL
   first).
2. Reproduce the black screen, then restore the release DLL.
3. The log is written next to the executable:

   ```
   <install>/Exe/cnc-ddraw-Disciple-1.log   (rotates to -2 / -3; a .dmp on crash)
   ```

Attach `cnc-ddraw-Disciple-1.log` **and** the `.dmp` (if present) to the
upstream issue — the README and
[issue #44](https://github.com/FunkyFr3sh/cnc-ddraw/issues/44) ask for
`cnc-ddraw-*.log` and `cnc-ddraw-*.dmp` together. The debug build is for triage
only: it is slower and noisier, so do not leave it installed. Before posting,
re-check the cheap fixes above; most "black screen" reports are the override or
the fullscreen/windowed mismatch.
