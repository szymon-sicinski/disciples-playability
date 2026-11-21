# The cnc-ddraw wrapper (`disciples_play.wrapper`)

`Disciple.exe` is a PE32 i386 binary that does **not** import DirectDraw —
`HA312W32.DLL` and `SHW32.DLL` call `LoadLibrary("ddraw.dll")` by name. So a
`ddraw.dll` dropped next to `Disciple.exe`, plus a Wine override that routes
`ddraw` to that file, takes over the whole graphics layer.
[cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw) (MIT) is that DLL, and it
already lists *Disciples* among its supported games. This module turns
cnc-ddraw's "unzip by hand and configure per install" into three reproducible
functions:

| Function | What it does |
|---|---|
| `build_preset(scale=3, maxfps=60, vsync=True, adjmouse=True, renderer="auto")` | Returns the text of the `ddraw.ini` preset. |
| `fetch_wrapper(dest, tag="v7.1.0.0", expected_sha256=..., expected_size=..., offline_zip=None)` | Downloads (or reads `offline_zip=`) the pinned release, verifies its size and SHA-256, extracts only `ddraw.dll`, `ddraw.ini` and LICENSE-ish files (path-traversal and symlink entries refused). |
| `install_wrapper(game_dir, staging, preset=None)` | Copies `ddraw.dll` and writes the preset (or your `preset=` text) into the game directory, with overwrite protection. |

## The preset

```
[ddraw]
windowed=1
maintas=1
maxfps=60
vsync=1
adjmouse=1
savesettings=1
nonexclusive=1
hook=4
renderer=auto
```

Every key above is one `src/config.c` actually reads (verified against tag
`v7.1.0.0`); nothing else is written. `windowed=1` + `maintas=1` give the
windowed, aspect-preserving presentation the pack wants; the window opens at
the game's native 640×480 and is resized to taste (the preset's comment block
records the 3× target, 1920×1440).

Notes on two keys a human may want to tune after the first run:

- **`hook=4`** (upstream's own default) is pinned, not `hook=1`, because of how
  this game is built. `Disciple.exe` does **not** import `ddraw.dll` —
  `HA312W32.DLL` loads it by name and owns the window. `hook=1` patches only
  the main executable's import table, so it would patch nothing that draws and
  `adjmouse`, cursor clipping and the `PeekMessage` filter would silently do
  nothing. Mode 4 enumerates the loaded modules and patches every *local* one,
  which is what reaches `HA312W32.DLL`. (cnc-ddraw deliberately skips modules
  named `Shw32`/`SH33W32` — the "don't hook reshade/swiftshader/mesa" guard —
  so `SHW32.DLL` is not patched either way.)
- **Crisp integer pixels** (`boxing=true`, "windowboxing / integer scaling") or
  `shader=Nearest neighbor` are the knobs for "integer-scaled, not blurry"
  (§8 item 2 of the plan). They are deliberately *not* in the preset so the
  default stays minimal; both are within the allowed key set.

## Why the game must stay fullscreen

cnc-ddraw's README is explicit: **the game must be set to fullscreen**
(`InWindow=0`), and windowed presentation comes from cnc-ddraw, not from the
game. Running the game's *own* windowed mode alongside cnc-ddraw's windowed
mode fights it (the game and the wrapper both try to own the window). Keep the
game fullscreen and let `windowed=1` do the windowing. cnc-ddraw also requires
a DirectDraw (software) renderer, which this game is.

## The Wine override

For cnc-ddraw to be loaded instead of Wine's built-in `ddraw`, the prefix must
override it. On the command line:

```bash
WINEDLLOVERRIDES="ddraw=n,b" wine Disciple.exe
```

`n` = native (load our `ddraw.dll` from the game folder), `b` = builtin
fallback. The DLL must sit next to `Disciple.exe` (in `Exe\` for the GOG
layout) — that is where the game's `LoadLibrary("ddraw.dll")` resolves it.

## Updating the pin

The release is pinned by tag, byte size **and** SHA-256, so a re-tagged or
replaced asset upstream cannot silently change what users run. `fetch_wrapper`
checks the size first (a truncated download gets a clear size error) and then
the digest. To move to a new release:

1. Download the new `cnc-ddraw.zip` by hand and run `sha256sum` on it — never
   trust a digest in prose, and never let the code accept an unmeasured one.
2. Bump `CNC_DDRAW_TAG`, `CNC_DDRAW_SIZE` and `CNC_DDRAW_SHA256` in
   `src/disciples_play/wrapper.py`.
3. Update the digest, size and URL in `third_party/cnc-ddraw-PROVENANCE.md` and
   `THIRD_PARTY.md`.

If the digest is stale, `fetch_wrapper` refuses the download on mismatch —
that refusal is the safety feature working, not a bug.

## Black screen / won't start

The released `ddraw.dll` (v7.1.0.0) writes **no** debug log — upstream gates
`dbg_init()` behind `#ifdef _DEBUG`, so the file below only exists when the
`experimental-debuglog` build's DLL is installed. For triage, swap that build
in for one run (see the "Producing cnc-ddraw's debug log" section of
[`wine-recipe.md`](wine-recipe.md)), then collect
`Exe\cnc-ddraw-Disciple-1.log` (rotating to `-2`/`-3`, and a
`cnc-ddraw-Disciple-1.dmp` crash dump on an unhandled exception). Attach both
the log and the `.dmp` when reporting an issue upstream
([issue #44](https://github.com/FunkyFr3sh/cnc-ddraw/issues/44)). Before
reporting, try the cheap fixes in order: confirm the game is fullscreen
(`InWindow=0`), confirm `WINEDLLOVERRIDES="ddraw=n,b"` is in effect, confirm
`hook=4` is in effect (the preset default), and try `renderer=gdi` (the
fallback renderer — install it via `install_wrapper(..., preset=build_preset(renderer="gdi"))`).

## Licence

cnc-ddraw is MIT. The binary is **never vendored**: `disciples_play.wrapper`
exposes a fetch that downloads it from the pinned tag and checks the measured
SHA-256 recorded in `third_party/cnc-ddraw-PROVENANCE.md` (no CLI command calls
that fetch in v0.1 — the DLL is copied in by hand). The upstream `LICENSE` text ships
verbatim as `third_party/cnc-ddraw-LICENSE.txt`.
