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
| `fetch_wrapper(dest, tag="v7.1.0.0", expected_sha256=..., offline_zip=None)` | Downloads (or reads `offline_zip=`) the pinned release, verifies its SHA-256, extracts only `ddraw.dll`, `ddraw.ini` and LICENSE-ish files. |
| `install_wrapper(game_dir, staging)` | Copies `ddraw.dll` and writes the preset into the game directory, with overwrite protection. |

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
hook=1
renderer=auto
```

Every key above is one `src/config.c` actually reads (verified against tag
`v7.1.0.0`); nothing else is written. `windowed=1` + `maintas=1` give the
windowed, aspect-preserving presentation the pack wants; the window opens at
the game's native 640×480 and is resized to taste (the preset's comment block
records the 3× target, 1920×1440).

Notes on two keys a human may want to tune after the first run:

- **`hook=1`** hooks only the *main executable's* import table. cnc-ddraw's
  default is `hook=4`, which also enumerates and hooks the game's helper DLLs
  (`SHW32.DLL` etc. — where this game's drawing lives). If the image is
  missing, black or won't scale, try `hook=4` first.
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

The release is pinned by tag **and** SHA-256, so a re-tagged or replaced asset
upstream cannot silently change what users run. To move to a new release:

1. Download the new `cnc-ddraw.zip` by hand and run `sha256sum` on it — never
   trust a digest in prose, and never let the code accept an unmeasured one.
2. Bump `CNC_DDRAW_TAG`, `CNC_DDRAW_SIZE` and `CNC_DDRAW_SHA256` in
   `src/disciples_play/wrapper.py`.
3. Update the digest, size and URL in `third_party/cnc-ddraw-PROVENANCE.md` and
   `THIRD_PARTY.md`.

If the digest is stale, `fetch_wrapper` refuses the download on mismatch —
that refusal is the safety feature working, not a bug.

## Black screen / won't start

cnc-ddraw writes a debug log unconditionally next to the game executable:
`Exe\cnc-ddraw-Disciple-1.log` (rotating to `-2`/`-3`, and a
`cnc-ddraw-Disciple-1.dmp` crash dump on an unhandled exception). Attach that
log when reporting an issue upstream
([issue #44](https://github.com/FunkyFr3sh/cnc-ddraw/issues/44)). Before
reporting, try the cheap fixes in order: confirm the game is fullscreen
(`InWindow=0`), confirm `WINEDLLOVERRIDES="ddraw=n,b"` is in effect, and try
`hook=4` and/or `renderer=gdi` (the fallback renderer).

## Licence

cnc-ddraw is MIT. The binary is **fetched, never vendored**: it is downloaded
from the pinned tag and checked against the measured SHA-256 recorded in
`third_party/cnc-ddraw-PROVENANCE.md`. The upstream `LICENSE` text ships
verbatim as `third_party/cnc-ddraw-LICENSE.txt`.
