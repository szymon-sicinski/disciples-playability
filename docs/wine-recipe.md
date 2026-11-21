# Reproducible Wine/Proton recipes

> **Unverified until the maintainer runs them.** No agent here can launch the
> game, so nothing below claims to *work*. Every recipe is a copy-paste start
> point that a second machine should be able to follow; the "expected output"
> blocks describe what a correct run *would* show, not what has been observed.
> When a recipe has been run end-to-end on a real machine, flip its section to
> *verified* and record the machine/date in
> [`docs/verification.md`](verification.md).

Three ways to get the same prefix. All three end at the same place: a Wine
prefix, a `ddraw` override that routes DirectDraw to the staged `cnc-ddraw`
DLL, and the `disciples-play` launcher (which re-points the INI and launches).

The one thing every recipe shares is the **override**. `Disciple.exe` does not
import DirectDraw — `HA312W32.DLL` loads `ddraw.dll` by name — so a
`ddraw.dll` dropped next to `Disciple.exe` plus a `ddraw=n,b` override takes
over the whole graphics layer. `n` = native (load our DLL), `b` = builtin
fallback. See [`wrapper.md`](wrapper.md) for why, and the `doctor` subcommand
for checking that it is actually in effect:

```bash
disciples-play doctor --game-dir "/path/to/Disciples Gold"
```

---

## 1. Plain Wine

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
#           then the game window opens at 640×480, resizable/scaled by cnc-ddraw.
```

---

## 2. Bottles

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
4. In the bottle's **"Run Executable"** (or "Open terminal"), run the pack's
   launcher so the INI rewrite and launch happen inside the bottle's prefix:

   ```bash
   disciples-play --game-dir "/path/to/Disciples Gold"
   # expected: same as §1d — the INI rewrite summary, then the game window.
   ```

> Bottles field names shift between versions; the invariants are the bottle
> (any), the `ddraw` override (native,builtin) and DPI 96. If a field is
> missing, do the same thing in plain `winecfg` (see §1) against the bottle's
> prefix, which lives under `~/.local/share/bottles/bottles/<name>`.

---

## 3. Heroic / Proton

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
   `ddraw=n,b` and that `ddraw.dll` really sits in `Exe\`.
4. DPI: leave at 96 (same reasoning as §1c). Launch via the pack:

   ```bash
   disciples-play --game-dir "/path/to/Disciples Gold"
   # expected: the INI rewrite summary, then the game window under Proton.
   ```

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

When a run fails and you want to report upstream, cnc-ddraw writes a debug log
**unconditionally** next to the game executable:

```
<install>/Exe/cnc-ddraw-Disciple-1.log   (rotates to -2 / -3; a .dmp on crash)
```

Attach `cnc-ddraw-Disciple-1.log` (and the `.dmp` if present) to the upstream
issue — the maintainers' issue template asks for exactly this file. Before
posting, re-check the three cheap fixes above; most "black screen" reports are
the override or the fullscreen/windowed mismatch.
