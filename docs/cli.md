# `disciples-play` — command-line interface

One command, two jobs: make a Disciples install portable and start it (the
launcher), and print a read-only structural report of its data files
(`disciples-play data`).

The launcher resolves the install, re-points `Exe\DISCIPLE.INI` at that
install's real location (rewriting the 21 stale `X:\…` paths in `[Installation]`
and `[InstallationClient]`), and launches `wine Exe/Disciple.exe`. All of it
runs against a game folder **you already own**; this repository ships no game
data.

## Usage

```
disciples-play [--game-dir DIR] [--dry-run | --print-command] [--wine PATH]
               [--path-style wine|relative]
               [--ini-mode backup|inplace|copy-tree]
               [--no-launch] [-v | -q]
disciples-play doctor [--game-dir DIR] [--json]
disciples-play data [--game-dir DIR] [--json]
disciples-play --version
```

| Flag | Meaning |
|---|---|
| `--game-dir DIR` | The install directory, or a parent of it. Highest-priority source. |
| `--dry-run` | Compute the INI rewrite and print the diff + the exact command line + cwd, **without writing or launching**. |
| `--print-command` | Print the shell-quoted launch command and exit. No writes, no launch. |
| `--wine PATH` | The wine binary (bare name is looked up on `PATH`). Default: `wine`. |
| `--path-style {wine,relative}` | How installation paths are written. Default `wine` (absolute Windows paths — the proven-working form). `relative` (bare folder names) is kept for the portability experiment and is currently **falsified** in game; see the plan §7 R1 / §9 Q1. |
| `--ini-mode {backup,inplace,copy-tree}` | How `DISCIPLE.INI` is updated. Default `backup`. |
| `--no-launch` | Rewrite the INI but do not start the game. |
| `-v, --verbose` | Keep wine's debug output and log more. |
| `-q, --quiet` | Suppress the rewrite summary line. |

## Where the install comes from (priority order)

1. `--game-dir`
2. `$DISCIPLES_GAME_DIR`
3. a config file: `<config>/disciples-play/config.ini` with a `game_dir = …` key
   (and an optional `wine = …`). `<config>` is `$XDG_CONFIG_HOME` (default
   `~/.config`) on Linux, `%APPDATA%` on Windows.

If none resolves, the command exits `2` and says what to do.

## Install resolution (the "copied retail folder" case)

The exe always lives at `<install>/Exe/Disciple.exe` and the INI at
`<install>/Exe/DISCIPLE.INI` (matched **case-insensitively** — a retail install
may carry `DISCIPLE.ini`; if several case-variants exist the canonical
`DISCIPLE.INI` is preferred and a warning is logged). Users copy the retail
folder *as a folder*, so a `--game-dir` that does not itself hold the exe is
searched one and two levels down — the `find <dir> -maxdepth 2 -name
Disciple.exe` shape — and the **containing root** (the directory that holds
`Exe/` **and** the `Globals/`, `Imgs1/`, … data folders) is used:

```
<dir>/Exe/Disciple.exe            -> root = <dir>
<dir>/<sub>/Exe/Disciple.exe      -> root = <dir>/<sub>
<dir>/<sub>/<sub>/Exe/Disciple.exe -> root = <dir>/<sub>/<sub>
```

Exactly one match is required. Zero matches, or more than one, exits `2` with
the candidates listed. A missing `DISCIPLE.INI` in the resolved root also exits
`2`. "Missing" is never reported because of a nesting level the user did not
account for.

## The rewrite

Driven by `disciples_play.ini` (M1). Only the two installation sections are
touched; every other line — comments, blanks, other sections, CRLF endings —
survives byte-for-byte. On success a single summary line is printed, e.g.:

```
rewrote 21 installation keys (backup at …/Exe/DISCIPLE.INI.orig)
```

A re-run that finds the values already correct is a byte-wise no-op: it prints
`already up to date; no rewrite needed`, does not touch the file (mtime
unchanged), and never overwrites an existing `.orig`.

The three modes:

* **`backup` (default)** — write `Exe/DISCIPLE.INI` in place, saving
  `<the existing INI's name>.orig` exactly once and never overwriting it
  afterwards (`DISCIPLE.INI.orig` for the canonical spelling, `DISCIPLE.ini.orig`
  when the install carries the lowercase one the game writes back). This is
  the "re-apply on every launch" mode: `Config.exe` may rewrite the INI, so the
  launcher re-applies it each start.
* **`inplace`** — write in place, never back up.
* **`copy-tree`** — copy the whole install to a sibling `<install>.copy` and
  rewrite *that* copy's INI (no `.orig` — the pristine original is the backup),
  then run from the copy. The original GOG folder is never written. Costs a
  full copy (~645 MB). Refuses (`3`) if `<install>.copy` already exists.

## Launch

The argv is `wine <install>/Exe/Disciple.exe`, run with working directory
`<install>/Exe` (the known-good baseline: `Exe/` cwd **plus** absolute INI
paths). Environment for the child:

* `WINEDLLOVERRIDES=ddraw=n,b` — set only when `ddraw.dll` sits next to the exe
  (the cnc-ddraw wrapper staged by M3). An existing `WINEDLLOVERRIDES` that
  does not already route `ddraw` to native (`ddraw=n…`) is preserved and
  appended to.
* `WINEDEBUG=-all` — set unless `-v`.

The launcher waits for the game and returns its exit code.

## The `doctor` subcommand

```bash
disciples-play doctor --game-dir "/path/to/Disciples Gold" [--json]
```

Reports one line per check — `PASS`/`FAIL`/`WARN` with a one-line fix hint —
instead of prose, so a second machine is a set of checkable lines rather than a
hand-made prefix. The checks, in order:

| Check | What it verifies |
|---|---|
| `install` | the install resolves to exactly one `Exe/Disciple.exe` (reports the exe dir) |
| `ini` | `Exe/DISCIPLE.INI` present and writable |
| `ini-paths` | all 15 `[Installation]` + 6 `[InstallationClient]` keys are present and each holds an absolute Windows path that resolves to this install, matched **case-insensitively** (the INI's `globals` vs the install's `Globals` is expected). Relative/empty values are a **FAIL** — bare relative names fail in-game with "unable to load fonts" (plan R1/Q1) — as are missing keys and stale paths; extra/unknown keys are a WARN. |
| `wine` | `wine` present and reports a `--version`. **FAIL** on POSIX when absent (the launcher cannot run without it); PASS "not needed" on Windows. |
| `ddraw-override` | `WINEDLLOVERRIDES` routes `ddraw` to native (`ddraw=n…` — a bare `ddraw=b`/`ddraw=d`/`ddraw=` does **not** count), or the wrapper is staged next to the exe (which the launcher overrides automatically) |
| `wrapper` | cnc-ddraw's `ddraw.dll` staged with a marker file matching its digest (mismatch → WARN "not ours, leaving it alone") |
| `ini-window` | `[Disciple] InWindow`, the game's **own** display mode. `InWindow=0` PASS (the fullscreen baseline; windowed presentation comes from cnc-ddraw). `InWindow=1` **always WARNs**, because cnc-ddraw needs the game itself fullscreen (`InWindow=0` is the precondition in `docs/verification.md`). The wording follows the `wrapper` line's own verdict: when `wrapper` PASSes (installed, digest matches the marker) it says cnc-ddraw is installed and verified but needs the game fullscreen, so set `InWindow=0`; otherwise (no DLL, foreign DLL, bad marker or digest, or only a `WINEDLLOVERRIDES` override) it says there is no verified cnc-ddraw — "windowed presentation needs cnc-ddraw; the launcher does not write this key" — and names the order that works: set `InWindow=0`, then stage cnc-ddraw next to `Disciple.exe` if you want a window (staging alone does not clear the warning; cnc-ddraw presents the window and the game stays fullscreen). A missing key is a WARN (the retail default is unknown). The doctor never writes this key: it is the user's display choice, and the launcher rewrites only the 21 installation paths. This is a configuration guard only — it makes no claim about the start-up crash at `0059559E`, which also happens with `InWindow=0`. |
| `music` | 25 `.wav` files in `Music/` (count and size only) |
| `video` | 41 `.smk` cutscenes — 6 in `Video/` + 35 in `Briefing/` (count and size only) |
| `display` | an X display is available (WARN "no X display: cannot verify windowing" when `DISPLAY` is unset) |

**Hard rule:** the doctor reports paths, sizes, counts, versions and existence.
It never prints a hash of a game binary and never dumps content. The one digest
it computes (the staged `ddraw.dll`, compared against the marker file) is
reduced to a matches/does-not-match verdict before it reaches the report, so a
64-hex string can never leak into a transcript.

`--json` emits a stable schema:

```json
{"checks": [{"id": "…", "status": "pass|fail|warn", "detail": "…"}, …], "ok": true}
```

Doctor exit codes: `0` all checks passed, `1` any check failed, `2` bad
arguments. A `WARN` never fails the run, but the checks that block play are
FAILs: a missing `wine` on POSIX is a FAIL (exit `1`), not a WARN, because the
launcher cannot run without it. `--game-dir` may appear before or after the
`doctor` subcommand. The doctor is read-only — it never writes into the
install. `ok` in the JSON output is `true` when no check FAILs (WARNs do not
flip it).

## `data` — read-only structural report

`disciples-play data` walks the install and prints a *structural* report: a
directory inventory, per-table dBase III geometry, per-container `MQDB`
hypothesis votes, ID cross-reference counts, and digests of the plain-text
formats. It opens every file read-only and never decodes an image to pixels,
never dumps palette entries, and never prints file hashes — the whole report is
safe to publish.

```
disciples-play data [--game-dir DIR] [--json]
```

| Flag | Meaning |
|---|---|
| `--game-dir DIR` | The install directory, or a parent of it. Optional: defaults to `$DISCIPLES_GAME_DIR`, then the config file. |
| `--json` | Emit the report as JSON instead of the human text rendering. |

It resolves the install exactly like the launcher (§ "Where the install comes
from" and "Install resolution"): `--game-dir`, then `$DISCIPLES_GAME_DIR`, then
the config file, then the parent-directory search for `Exe/Disciple.exe` — a
parent directory the launcher resolves to one install is resolved identically
here. If at least one file cannot be parsed (a malformed `.DBF`, an unreadable
`.DBI`, …), the report still prints with a per-file `error` entry and the
command exits `1`.

The report layout and every measured number are documented in
`docs/data-layout.md`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (also `--help`/`--version`, `--dry-run`, `--print-command`, `--no-launch`). |
| `1` | `data` only: at least one file could not be parsed. The report still prints, with per-file `error` entries. |
| `2` | Bad command line, or a bad/missing install — the message lists what is missing and the exact search paths tried. |
| `3` | Rewrite refused — the INI is not writable, or the `copy-tree` target already exists / could not be copied. |
| `4` | Wine not found (launch only). |

The `doctor` subcommand overrides this with its own contract: `0` all checks
passed, `1` any check failed, `2` bad arguments (a missing `--game-dir` with no
env/config fallback is `2`; an install that does not resolve is a `FAIL` check,
`1`).

## Deliberate decisions and known limits

* **`DISCIPLE.INI.orig` existing is not a refusal.** The plan §2 makes
  "re-apply on every launch" the design and M1's `write_ini` writes in place
  even when `.orig` already exists (it just never overwrites it). The card's
  exit-3 wording mentioned a `--force-backup` gate on an existing `.orig`;
  that would contradict both, so it is reconciled away here: exit `3` is
  exclusively "the INI cannot be written". There is no `--force-backup` flag.
* **`install_dir` is a POSIX path.** Passing an already-Windows path (e.g.
  `Z:\C:\…`) would double-root it; the value is documented as the POSIX install
  path and converted via `winepath -w` (with a `Z:\` fallback) by M1.
* **Case sensitivity is a separate defect.** The maintainer's install holds both
  `DISCIPLE.INI` and `DISCIPLE.ini`, and the in-game `..\interf\Tapp.dbf` vs
  `Interf/TApp.dbf` failure is a data-layer case mismatch the INI cannot fix.
  It is recorded in the plan (§7 R1 / §9 Q1) and belongs to a later case-shim
  card, not this one.

## Examples

```bash
# see what would change, without touching anything
disciples-play --game-dir "…/Disciples Gold" --dry-run

# the exact command, copy-pasteable
disciples-play --game-dir "…/Disciples Gold" --print-command

# fix the INI and play
disciples-play --game-dir "…/Disciples Gold"

# fix the INI, leave a pristine GOG folder, and play from the copy
disciples-play --game-dir "…/Disciples Gold" --ini-mode copy-tree
```
