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
| Heroic + Proton-GE, its own prefix, the original `X:\…` INI | **plays** ✅ |
| Heroic + Proton-GE, its own prefix, **the pack's rewritten INI (21 keys → `Z:\…`)** | **plays** ✅ (re-run 2026-11-21 with the rewrite in place; the install holds a single, unmodified `Exe/Disciple.exe`, the same path the crash dumps name) |

The crash is `mov ecx,[eax] ; call [ecx+0x58]` with `EAX=0` — a virtual call
through a null object. **What precedes it is measured** (see "What the runs on
plain `wine` showed"): COM does return an interface, `Initialize` and
`SetCooperativeLevel` succeed, and the game's `SetDisplayMode(640, 480, 8)` is
refused (`NtUserChangeDisplaySettings` returns `-2`) with the mode left at
1280x1024x32. **Nothing in this pack fixes that, and nothing here claims it
does:** it is a limitation of plain `wine` as a launch environment, not a pack
defect and not an INI problem.

The pack's launcher execs a **single `wine` binary** (override with `--wine`)
and has no Proton / `STEAM_COMPAT_*` path, so it cannot start the game inside a
Heroic or Lutris Proton prefix. The supported sequence is therefore: let the
pack rewrite the INI, then start the game from your runner.

```bash
disciples-play --no-launch --game-dir "<install>"   # rewrites the 21 keys only
# then press Play in Heroic / Lutris with a Proton runner
```

One fact to keep straight, because it changes what the pack is for: both INIs
play under that Proton runner — the install's **original `X:\…` values** and the
pack's **rewritten `Z:\…` values**. The rewrite is not what makes the game run;
the Proton runner is. What the rewrite buys is that the game boots with the
values the pack wrote where the pack wrote them; whether a *moved* folder still
finds its data is item 8 of the checklist, still unticked. §3 records both runs,
including the earlier one that was mis-recorded as using the rewrite when it was
not.

**cnc-ddraw was not in the picture in any of those runs.** Every plain-Wine
crash dump lists `C:\windows\system32\ddraw.dll` and
`wined3d.dll`; the `ddraw.dll` staged in `Exe\` was never loaded. That does not
prove the wrapper is useless — it proves none of the results above depend on
it. Do not credit it with the working run.

---

Three ways to get a prefix. Each one ends with the `disciples-play` launcher
doing the INI rewrite. Each also mentions the `ddraw` override, because that was
the design — but for this title the override is **inert** (next paragraph), so
treat it as a step to skip, not a step that makes anything work. Only the Proton
path (§3) has actually started this title so far.

The one thing every recipe shares is the **override**. `Disciple.exe` does not
import DirectDraw, and no module `LoadLibrary`s `ddraw.dll` by name — the game
acquires DirectDraw through **`CoCreateInstance(CLSID_DirectDraw)`**, which
resolves to the prefix's `system32\ddraw.dll` via the COM registry entry (see
"Known crash at start-up" below). A `ddraw.dll` dropped next to `Disciple.exe`
plus a `ddraw=n,b` override is therefore **not** able to take over the graphics
layer for this title — the native DLL is never loaded. `n` = native (load our
DLL), `b` = builtin fallback; for this title the override can only ever fall back
to `b`. See [`wrapper.md`](wrapper.md) and the `doctor` subcommand for checking
that the override is at least in effect:

```bash
disciples-play doctor --game-dir "/path/to/Disciples Gold"
```

---

## Known crash at start-up: `0059559E` (unresolved on plain `wine`)

As of **2026-11-21** this title does not reach the main menu from this pack's
launcher on plain Wine (wine-11.21 Staging, wow64), in **either** display mode.
It is not a configuration fault that a recipe below can undo: the way round it is
a different launch environment — the supported sequence at the top of this file,
not a Wine setting. The cause is now understood (the game acquires DirectDraw
through `CoCreateInstance(CLSID_DirectDraw)`; see "What the crash is" below), and
the one candidate Wine-side fix — register cnc-ddraw as that COM server — is
untested.

What the runs on plain `wine` showed:

```
Disciple.log   "Midgard (v.2000, 6, 22, 1) started on Sat Nov 21 19:13:04 2026"
               -> the game's own startup code runs, then it dies
crash          Unhandled page fault on read access to 00000000, EIP 0059559E, EAX=0
               mov eax,[esi+8] ; mov eax,[eax+8] ; push edx ; push eax
               mov ecx,[eax]   ; call [ecx+0x58]
               -> [this+8] is a valid object whose own +8 member is null, and the
                  game calls a virtual method through it with no null check
               -> +0x58 is GetSurfaceDesc on a surface and WaitForVerticalBlank on
                  IDirectDraw4, and two arguments are pushed: the object's type is
                  not established by the crash alone [H]
               -> the faulting access is a READ through a null eax; the Windows
                  crash dialog labels the same fault "write to location 00000000"
imports        Disciple.exe imports no ddraw/dsound/dinput; it acquires DirectDraw
               via CoCreateInstance(CLSID_DirectDraw) through ole32 — the renderer
               lives in Disciple.exe (CPrimaryDisplayDDraw / CPrimaryDisplayDIB).
               SHW32.dll is SmartHeap (the memory manager), not the graphics layer
launcher       all 21 installation keys rewritten, DISCIPLE.ini.orig written --
               the rewrite itself is fine
wrapper        a cnc-ddraw ddraw.dll staged in Exe\ is never loaded — the game's
               COM path resolves system32\ddraw.dll, not the app directory — so it
               faults identically with or without the wrapper (see "What the crash
               is" below)
```

Measured headlessly in the retrolab rig (wine-staging **11.21**, wow64-only,
llvmpipe software GL, no audio, baked prefix) on **2026-11-22**, one variable per
run. Legend: `[V]` = measured in that run, `[H]` = hypothesis, `[U]` = untested
in this rig (needs the maintainer's machine or a different Wine build).

| Experiment | Result |
|---|---|
| **B** — `WINEDLLOVERRIDES=ddraw=b` (builtin ddraw, baseline) | **[V] crashes at `0059559E`, deterministically.** `Disciple.log` = "Midgard started" (dies before sound init); frame = the crash dialog (mean 241, 74 colours); windows = game + "Wine Debugger" + "Program Error". |
| **E5** — `WINEDLLOVERRIDES=ddraw=n` (native cnc-ddraw, **no** `,b` fallback) | **[V] same `0059559E` crash**, and Wine reports the native DLL is *never loaded*: `err:ole:apartment_add_dll couldn't load in-process dll C:\windows\system32\ddraw.dll`, then `class {D7B70EE0-4340-11CF-B063-0020AFC2CD35} not registered`. The staged `Exe\ddraw.dll` is not in that path, so `n` always falls back to builtin — exactly why the pack's `n,b` never helped. |
| **E7** — `[Disciple] DDraw=0` (GDI fallback) | **[V] does not crash** — process alive at the 25 s kill. Frame near-black (mean 1→10, 33→52 colours); `Disciple.log` = "Midgard started" + "Sound system could not be initialized" (no audio device in the rig). Confirms "GDI starts, black screen". |
| **E3** — `WINEDLLOVERRIDES=msvcrt=n` (force the bundled 1999 `MSVCRT.DLL`) | **[V] not a fix and not the same crash.** Wine's own DLL chain breaks — `err:module:import_dll Library msvcrt.dll (needed by advapi32/rpcrt4/user32/gdi32/shell32) not found`, `STATUS_DLL_NOT_FOUND c0000135`. The game process starts ("Midgard started") but the loader never reaches DirectDraw, so the CRT is not the cause. |
| **E4** — `WINEARCH=win32` prefix (non-wow64) | **[U] cannot be run in this rig** — this Wine build is wow64-only: `wine: WINEARCH is set to 'win32' but this is not supported in wow64 mode.` Needs a 32-bit-capable Wine build on the maintainer's machine. |
| **E1** — Windows version gate (`winecfg` → 98/XP) | **[U]** — the prefix reports Windows 10 Pro (build 19045); not changed here. Proton reports Win7/WinXP to old titles, so this is still a plausible differential and a ~10-second maintainer test. |
| **E2** — virtual desktop 800×600 | **[U]** — `winecfg` display change not applied in the rig. |
| **E6** — X11 vs Wayland display path | **[U]** — the rig is X11-only (Xvfb); needs the maintainer's display. |
| Wine version ≠ 11.21 | **[U]** — only 11.21 is available in the rig (pinned by SHA-256); no other build can be added without changing the image. |

**What the crash is (resolved, `[V]`).** The investigation's open question — how
`Disciple.exe` obtains `IDirectDraw` — is now answered: the game calls
**`CoCreateInstance(CLSID_DirectDraw)`** (`{D7B70EE0-4340-11CF-B063-0020AFC2CD35}`),
which resolves through the prefix registry's
`HKCR\CLSID\{…}\InprocServer32 = C:\windows\system32\ddraw.dll` — the COM server
path, **not** the application-directory DLL search. Two failure modes land on the
same null dereference at `0059559E`:

- **builtin ddraw** (`ddraw=b`, `[V]`): COM returns a builtin `IDirectDraw` and
  the game gets as far as `SetCooperativeLevel(DDSCL_FULLSCREEN|DDSCL_EXCLUSIVE)`
  and `SetDisplayMode(640, 480, 8)`. The mode change is **refused** —
  `err:system:NtUserChangeDisplaySettings ... returned -2` — and the following
  `GetDisplayMode` still reports 1280x1024x32. The game then dereferences a null
  object whose type the crash alone does not establish (`+0x58` is
  `IDirectDrawSurface::GetSurfaceDesc` *and* `IDirectDraw4::WaitForVerticalBlank`,
  and the code pushes two arguments). **`[H]`:** no `CreateSurface` call appears
  anywhere in the `WINEDEBUG=+ddraw` trace, so "the primary surface stayed null"
  is a hypothesis, not an observation — what is measured is that the 8-bit mode
  is not applied and the fault follows.
- **native ddraw** (`ddraw=n`): the COM server load itself fails (`class not
  registered`), so there is no `IDirectDraw` at all.

**Consequence for the pack.** A cnc-ddraw `ddraw.dll` staged next to
`Disciple.exe` is **never loaded** by this title, because its DDraw acquisition is
COM-based and `InprocServer32` points at `system32`. The `ddraw=n,b` override can
therefore only ever fall back to `b`. To make cnc-ddraw take over, its `ddraw.dll`
would have to be **registered as the COM server for `CLSID_DirectDraw`**
(`regsvr32 ddraw.dll` in the prefix) or dropped into the prefix's `system32` —
neither the launcher does today, and neither is tested here.

`doctor`'s `ini-window` line is a **configuration guard, not a crash fix**: it
warns on every `[Disciple] InWindow=1` (cnc-ddraw needs the game fullscreen,
so a window the game makes itself is never the supported setup), and passes only
on `InWindow=0`. Neither verdict says
anything about whether the game starts.

Root-cause work on `0059559E` continues outside this card. Do not add a
workaround that silently rewrites `DDraw`, `InWindow` or the Wine binary — a
silent change would hide the setting from whoever debugs it next.

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

> **For this title the override cannot engage, and this is measured.** The game
> acquires DirectDraw through `CoCreateInstance(CLSID_DirectDraw)`, which COM
> resolves to the prefix's `system32\ddraw.dll` — a registry path, not the
> app-directory search an override redirects (see "Known crash at start-up").
> Steps 1b and 1d below are therefore the recipe as designed, not a working
> path for Disciples: staging the DLL and setting the override changes nothing
> here.

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
#           This is inert for Disciples either way (see the caveat above and
#           "Known crash at start-up"); the launcher would also set
#           WINEDLLOVERRIDES=ddraw=n,b itself once a ddraw.dll is staged.
```

**1c. DPI.** Leave Wine's DPI at the default 96 — cnc-ddraw owns the scaling,
and a high DPI can blur the game's fixed 640×480 menus. In `winecfg` →
Graphics, "Screen resolution" should read **96 dpi**. (Unverified: the safe
default is documented, not a measured requirement.)

**1d. Stage cnc-ddraw, then launch.** In the recipe as designed cnc-ddraw must
sit next to `Disciple.exe` before the override does anything — for this title it
is never loaded either way (see the caveat above). The pack's `disciples_play.wrapper` module
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
   **"Native, then Builtin"**. This is the `ddraw=n,b` equivalent — inert for
   this title for the reason in the §1 caveat, so do not read it as the fix.
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
> Proton-GE runner reaches the main menu and plays — both with the install's
> **original `X:\…` INI** and with **the pack's rewritten `Z:\…` values**
> (`disciples-play --no-launch`, then Play in Heroic; the rewritten file was left
> untouched by the run). No wrapper was staged in either run, so nothing here
> credits cnc-ddraw with it.
>
> One correction worth keeping visible: an earlier run was recorded as using the
> rewritten INI when the file in place still held the original `X:\…` values
> (`DISCIPLE.ini.rewritten` turned out to contain `X:\Games\Heroic\…`). The
> rewrite was re-tested deliberately afterwards and plays — so this claim rests
> on a real run rather than on a file-copy assumption. **What that run shows is
> that the game boots with the rewritten values where the pack wrote them**; that
> a *moved* folder still finds its data is item 8 of the checklist and is
> still unticked.

The existing prefix named in `Exe\Disciple.log` (`X:\Games\Heroic\…`) came from
a Heroic install, so this is the path that reproduces what the maintainer
already has.

1. Add the game in Heroic (or use the existing entry), then open its
   **Settings → Wine / "Other"** panel.
2. **No `WINEDLLOVERRIDES` is needed, and setting one changes nothing here.** The
   game's COM path ignores the app-directory DLL search that an override would
   redirect (step 3). If your Heroic entry already carries
   `WINEDLLOVERRIDES = "ddraw=n,b"` from an earlier attempt, it is harmless —
   leave it or remove it, the measured result is the same.
3. **The game's DirectDraw acquisition is COM-based, so a staged wrapper is never
   loaded.** `Disciple.exe` obtains DirectDraw through
   `CoCreateInstance(CLSID_DirectDraw)`, which resolves to the prefix's
   registered `system32\ddraw.dll` — measured on plain Wine (see "Known crash at
   start-up" above). **`[U]` what Proton resolves that COM path to has not been
   measured.** It is *not* DXVK: DXVK implements Direct3D 8/9/10/11, and nothing
   in it provides `IDirectDraw`; Proton's `ddraw.dll` is Wine's own,
   wined3d-backed one — the same DLL measured failing above. Why the same title
   starts under Proton and dies under plain Wine is therefore **open**, and the
   candidates are the Proton Wine version and its patches, the prefix's Windows
   version, and the display path — not a different ddraw implementation.
4. DPI: leave at 96 (same reasoning as §1c). The pack's launcher always execs a
   single `wine` binary — it has no Proton/`STEAM_COMPAT_*` path — so it cannot
   launch under the Heroic Proton prefix you just configured. Use the pack for
   the INI rewrite, then launch from Heroic itself:

   ```bash
   disciples-play --game-dir "/path/to/Disciples Gold" --no-launch
   # expected: "rewrote 21 installation keys …" (no launch).
   ```

   then press **Play** in Heroic. (To drive Proton directly from a shell instead,
   set `STEAM_COMPAT_DATA_PATH` and `STEAM_COMPAT_CLIENT_INSTALL_PATH` and run
   `proton run Exe/Disciple.exe` — that is the Proton equivalent of the
   launcher's wine exec, and no `WINEDLLOVERRIDES` is involved: step 2 explains
   why an override changes nothing here. The pack does not do this for you
   today.)

---

## If the screen is black

A black screen or a window that never appears is a *presentation* problem and is
not the start-up crash above. For any recipe, in this order:

1. **Game fullscreen, wrapper windowed.** cnc-ddraw expects the *game* to be
   fullscreen (`InWindow=0`); windowing comes from the wrapper. A game that is
   itself windowed fights cnc-ddraw. Confirm `InWindow=0` in `Exe\DISCIPLE.INI`
   (the launcher does not change it; `doctor`'s `ini-window` line reports it).
   If the game dies at start-up with `C0000005` at `0059559E` instead, you have
   the unresolved crash above, not a black-screen cause.
2. **Override in effect (for titles that load cnc-ddraw).** `disciples-play
   doctor --game-dir …` → the `ddraw-override` line. For this title that line
   always WARNs — the game acquires DirectDraw via
   `CoCreateInstance(CLSID_DirectDraw)` (COM), so the override and a staged
   `ddraw.dll` are inert and cannot be the cause of a black screen. It only
   matters for titles that `LoadLibrary("ddraw.dll")` by name.
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
