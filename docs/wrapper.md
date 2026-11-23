# The cnc-ddraw wrapper (`disciples_play.wrapper`)

`Disciple.exe` is a PE32 i386 binary that does **not** import DirectDraw. Its
renderer does not `LoadLibrary` `ddraw.dll` by name either; one other module in
the install does — `SMACKW32.DLL` (the Smacker video player) calls
`LoadLibraryA("DDRAW.DLL")` and `GetProcAddress("DirectDrawCreate")` (static:
strings and import-table resolution, not an observed load; that path has not
been exercised). Measured headlessly (2026-11-22, see
[`wine-recipe.md`](wine-recipe.md) "Known crash at start-up"): the renderer
acquires DirectDraw through **`CoCreateInstance(CLSID_DirectDraw)`**
(`{D7B70EE0-4340-11CF-B063-0020AFC2CD35}`), resolved via the prefix registry's
`HKCR\CLSID\{…}\InprocServer32 = C:\windows\system32\ddraw.dll` — the COM
server path, **not** the application-directory DLL search. A `ddraw.dll` dropped
next to `Disciple.exe` is therefore **not what the renderer loads**, and a
`WINEDLLOVERRIDES=ddraw=n,b` override cannot redirect the renderer — it can
only fall back to builtin there. Whether the video player's by-name load picks
the staged DLL up is untested.

[cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw) (MIT) supplies that DLL for
the *general* mechanism — for titles that `LoadLibrary("ddraw.dll")` by name, a
`ddraw.dll` next to the executable plus a `ddraw=n,b` override takes over the
graphics layer. cnc-ddraw lists *Disciples* among its supported games, but that
listing does not survive the measured COM path above. This module turns
cnc-ddraw's "unzip by hand and configure per install" into three reproducible
functions:

> **Status for the renderer:** it never loads the staged `ddraw.dll`, so the
> wrapper is not credited with any working run and does not fix the plain-Wine
> start-up crash (`0059559E`) — the cause of that crash was not isolated here; see
> [`wine-recipe.md`](wine-recipe.md) "Start here". The preset and fetch below
> remain correct for the wrapper they configure; they just cannot take over
> the renderer's graphics layer, because the COM path bypasses them (the video
> player's by-name load is untested).

| Function | What it does |
|---|---|
| `build_preset(scale=3, maxfps=60, vsync=True, adjmouse=True, renderer="auto")` | Returns the text of the `ddraw.ini` preset. |
| `fetch_wrapper(dest, tag="v7.1.0.0", expected_sha256=..., expected_size=..., offline_zip=None)` | Downloads (or reads `offline_zip=`) the pinned release, verifies its size and SHA-256, extracts only `ddraw.dll`, `ddraw.ini` and LICENSE-ish files (path-traversal and symlink entries refused). |
| `install_wrapper(game_dir, staging, preset=None)` | Resolves `game_dir` to the directory holding `Disciple.exe` (the install root or `Exe/` itself — see [where the two files go](#where-the-two-files-go)), then copies `ddraw.dll` and writes the preset (or your `preset=` text) *there* and nowhere else, with overwrite protection. A path with no `Disciple.exe` under it raises `WrapperInstallError`; so does an **ambiguous** tree — a stray `Disciple.exe` in the install root as well as in `Exe/` — naming both paths. |

## Where the two files go

`ddraw.dll` and `ddraw.ini` go in the directory that holds `Disciple.exe` —
`Exe/` in the GOG layout — never in the install root that also holds
`Globals/` and `Imgs1/`. That is where `doctor` and the launcher look for a
staged wrapper, and where a `LoadLibrary("ddraw.dll")`-based title would resolve
it; a wrapper anywhere else is silently inert. **For this title the renderer
does not load the staged DLL, wherever it sits** — it acquires DirectDraw via
`CoCreateInstance(CLSID_DirectDraw)` → `system32\ddraw.dll` (COM), not by name
(the video player's by-name path is untested) —
so "next to the exe" is the staging convention, not a working takeover.

`install_wrapper()` takes either path and resolves it with
`wrapper.resolve_exe_dir()`, so both calls below write the same three files
(`ddraw.dll`, `ddraw.ini` and the `.disciples-play-wrapper.json` marker) into
`Exe/`:

```python
wrapper.install_wrapper("<install>", staging)  # install root  -> <install>/Exe/
wrapper.install_wrapper("<install>/Exe", staging)  # exe directory  -> same place
```

An **ambiguous** tree — a `Disciple.exe` in the install root *and* in `Exe/` —
is refused too: a silent preference would install the wrapper in a directory the
launcher never loads from. The error names both paths; pass `<install>/Exe`, or
remove the stray copy.

A path with no `Disciple.exe` under it — neither at the path itself nor in
`Exe/` — raises `WrapperInstallError` and writes nothing, instead of leaving a
wrapper the launcher will never load.

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

- **`hook=4`** (upstream's own default) is pinned, not `hook=1`, because
  `Disciple.exe` does **not** import `ddraw.dll` — it acquires DirectDraw via
  `CoCreateInstance(CLSID_DirectDraw)`. `hook=1` patches only the main
  executable's import table, so it would patch nothing that draws and
  `adjmouse`, cursor clipping and the `PeekMessage` filter would silently do
  nothing. Mode 4 enumerates the loaded modules and patches every *local* one.
  (cnc-ddraw deliberately skips modules named `Shw32`/`SH33W32` — the
  "don't hook reshade/swiftshader/mesa" guard — so `SHW32.DLL` is not patched
  either way.) This rationale is moot for the renderer, which never loads the
  wrapper (COM path).
- **Crisp integer pixels** (`boxing=true`, "windowboxing / integer scaling") or
  `shader=Nearest neighbor` are the knobs for "integer-scaled, not blurry"
  (§8 item 2 of the plan). They are deliberately *not* in the preset so the
  default stays minimal; both are within the allowed key set.

## Why the game must stay fullscreen (for a title that loads `ddraw.dll` by name)

cnc-ddraw's README is explicit: **the game must be set to fullscreen**
(`InWindow=0`), and windowed presentation comes from cnc-ddraw, not from the
game. Running the game's *own* windowed mode alongside cnc-ddraw's windowed
mode fights it (the game and the wrapper both try to own the window).

**For a title that loads `ddraw.dll` by name**, keep the game fullscreen and let
`windowed=1` do the windowing. **Disciples does not** — it asks COM for
`CLSID_DirectDraw`, so this section is background for the preset, not an
instruction that changes anything here (see the opening of this file).

## The Wine override

For a title that `LoadLibrary`s `ddraw.dll` by name, cnc-ddraw is loaded instead
of Wine's built-in `ddraw` by overriding it in the prefix. On the command line:

```bash
WINEDLLOVERRIDES="ddraw=n,b" wine Disciple.exe
```

`n` = native (load the `ddraw.dll` from the game folder), `b` = builtin
fallback. The DLL must sit next to `Disciple.exe` — `Exe\` in the GOG layout,
see [where the two files go](#where-the-two-files-go).

> **For Disciples this override is inert.** The game acquires DirectDraw through
> `CoCreateInstance(CLSID_DirectDraw)` → `system32\ddraw.dll`, so `n` is never
> reached *by the renderer* and the override falls back to `b` (builtin) there.
> It does no harm and is still what the launcher sets when it finds a staged
> DLL, but it does not make the staged `ddraw.dll` take over the renderer. (The
> video player's by-name load is untested.) See
> [`wine-recipe.md`](wine-recipe.md) "Known crash at start-up".

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

> **This section assumes the wrapper is loaded.** For Disciples it is **not**:
> the game acquires DirectDraw via `CoCreateInstance(CLSID_DirectDraw)` →
> `system32\ddraw.dll`, so the renderer never loads a staged `ddraw.dll` and none of the
> `ddraw.ini`/`hook`/`renderer` knobs below take effect for it. The
> start-up crash (`0059559E`) was seen without the wrapper too (the cause was not isolated) — see
> [`wine-recipe.md`](wine-recipe.md) "Start here". The triage steps below stay
> correct for titles that load cnc-ddraw.

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
