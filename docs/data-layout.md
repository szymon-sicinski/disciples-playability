# Data layout — Disciples: Sacred Lands Gold

A fact-graded, verified description of the game's data layer, produced by a
read-only scanner against the GOG retail install. This document contains
**structure only**: no pixels, no palette entries, no audio samples, no text
bodies, and no file hashes. It is the legally clean half of the project — a
modder-facing reference that can be shipped on its own.

## Legend

Every claim is graded by how it was established:

| Grade | Meaning |
|---|---|
| **D** | Documented upstream (a published spec or tool describes it). |
| **H** | Hypothesis: inferred from structure, not yet confirmed against ground truth. |
| **V** | Verified: produced by a command run against the retail install in this session, quoted beside the number. |

A claim marked **H** is explicitly *not* a fact; the open-questions table at the
end says what would settle each one.

## How the numbers were produced

One command builds the whole report and is the source of every **V** number
below unless a different command is quoted:

```bash
python -m disciples_play data --game-dir "/game-files/Disciples Gold" --json
```

The same report renders as text with `--json` omitted. Field paths in this
document (e.g. `report.dbf[].records`) name where each number comes from in the
JSON output. The scanner opens every file `rb` and never writes, so the install
is untouched. Where a number needs a decode the report does not already do
(dBase field tables, ID cross-reference counts), the field path is still
`report.*` — both are emitted by the command above.

dBase III records begin with a 1-byte **deletion flag** (`0x20` space = live,
`0x2A` `*` = deleted) before the first field. The reader skips deleted records
when it reads a column, so every cross-reference count below is over **live**
(non-deleted) records; the header's record count still includes deleted rows,
and both figures are reported per table (`report.dbf[].records`,
`.live_records`, `.deleted_records`).

---

## 0. Directory inventory

| Claim | Evidence | Grade |
|---|---|---|
| 314 files total across the install | `report.inventory.total_files` | **V** |
| 131 `.DBF` tables: `Globals` 52, `Scens` 54, `Scendata` 6, `ImgData` 16, `Campaign` 2, `Interf` 1 (`TApp.dbf`) | `report.dbf[]` (counted per directory, not `inventory.by_directory`) | **V** |
| 19 `MQDB` containers: 11 `.dbi` + 5 `.ff` + 3 `.wdb` | `report.mqdb[]` | **V** |
| 3 `.dlg` dialog scripts, 6 `.MFT` fonts, 41 `.smk` videos, 25 `.wav` audio | `report.dlg/mft/smk/wav` | **V** |

Note: `inventory.by_directory` counts *every* file in a directory, so e.g.
`Interf` is 14 there (6 `.mft` + 3 `.dlg` + 3 `.dbi` + 1 `.ff` + 1 `.dbf`);
the 131-table figure and the per-directory DBF counts come from `report.dbf[]`,
which only lists tables. The other five directories happen to contain only DBF
files, which is why their numbers coincide. **V** — both are emitted by the
command above.

`.ff` ("full frame"?) and `.wdb` ("wave database") files carry the same `MQDB`
magic as `.dbi` — one container format, three extensions by payload kind
(image vs sound). **V** (verified by the scanner treating all three as `MQDB`
and tiling each to EOF; see §2).

---

## 1. dBase III tables (`.DBF`)

Every table is a genuine dBase III file. Header layout (offsets from file
start, all multi-byte fields little-endian):

| Offset | Size | Field | Observed |
|---|---|---|---|
| 0x00 | 1 | version byte | `0x03` = dBase III, no memo file — **V** |
| 0x01 | 3 | last-update date (YY, MM, DD) | varies — **V** |
| 0x04 | 4 | record count (u32) | — |
| 0x08 | 2 | header length (u16) | — |
| 0x0A | 2 | record length (u16) | — |
| 0x20 | 32×N | field descriptors | see below |
| … | 1 | `0x0D` terminator | — |
| … | … | records, `reclen` bytes each | — |
| EOF | 1 | `0x1A` end marker | — |

Each record begins with a 1-byte **deletion flag** (`0x20` space = live, `0x2A`
`*` = deleted), so `record_len == 1 + sum(field lengths)` (e.g. `GUNITS.DBF`:
247 = 246 + 1). **V** — the field offsets below start at 1, and the deleted
count is reported per table. 1,385 records across 45 of the 131 tables carry the
deletion flag (`report.dbf[].deleted_records`, summed).

Field descriptor (32 bytes each): 11-byte name, 1-byte type (`C` character,
`N` numeric, `L` logical), 1-byte length at descriptor offset 16, 1-byte
decimal count at 17. **V** — the field tables below are the decoded
descriptors, and the type letters are read from descriptor byte 11.

### The identity that proves the geometry

For **all 131 tables**, the header arithmetic closes:

```
header_len + records × record_len + 1 == file_size
```

`report.dbf[]` computes this per file; every `arithmetic_ok` is `true`. **V** —
one command, 131/131 agreeing, so the record grid tiles each file exactly and
the header is self-consistent, not a guess.

### Field tables (decoded, ≥6 tables)

Record counts are `header records (live, deleted)`.

`Globals\GACTION.DBF` — 13 records, header 161 B, record 270 B (closes).
Fields: `CATEGORY N:2`, `CHANCE N:3`, `NAME_TXT C:10`, `DESC_TXT C:254`. **V**

`Globals\GRACE.DBF` — 4 records, header 609 B, record 177 B (closes).
Fields: `RACE_ID C:10`, `GUARDIAN C:10`, `NOBLE C:10`, `LEADER_1..4 C:10`,
`SOLDIER_1..5 C:10`, `SCOUT N:2`, `REGEN_H N:3`, `INCOME C:29`,
`PROTECTION C:10`, `NAME_TXT C:10`, `RACE_TYPE N:2`. **V**

`Globals\GBUILD.DBF` — 68 records, header 577 B, record 125 B (closes).
Fields: `BUILD_ID C:10`, `NAME_TXT C:10`, `DESC_TXT C:10`, `REQUIRED C:10`,
`COST C:29`, `LEVEL N:1`, `CATEGORY N:2`, `BRANCH N:2`, `PIC_1 C:9`,
`FRAME_1 N:3`, `FRAME_2 N:3`, `POS_X/Y/CX/CY/Z N:3`, `COMMENTS C:20`. **V**

`Globals\GUNITS.DBF` — 310 records (308 live, 2 deleted), header 961 B,
record 247 B (closes). Fields: `UNIT_ID C:10`, `UNIT_CAT N:2`, `LEVEL N:2`,
`PREV_ID C:10`, `RACE_ID C:10`, `BRANCH N:2`, `SIZE_SMALL L:1`, `SEX_M L:1`,
`ENROLL_C C:29`, `ENROLL_B C:10`, `NAME_TXT C:10`, `DESC_TXT C:10`,
`ABIL_TXT C:10`, `ATTACK_ID C:10`, `HIT_POINT N:3`, `ARMOR N:3`, `REGEN N:4`,
`REVIVE_C C:29`, `HEAL_C C:29`, `TRAINING_C C:29`, `XP_KILLED N:4`,
`UPGRADE_B C:10`, `XP_NEXT N:4`, `MOVE N:3`, `SCOUT N:2`, `LIFE_TIME N:2`,
`LEADERSHIP N:2`, `NEGOTIATE N:3`, `LEADER_CAT N:2`. **V**

`Globals\GSPELLS.DBF` — 81 records (80 live, 1 deleted), header 545 B,
record 139 B (closes). Fields: `SPELL_ID C:10`, `CATEGORY N:2`, `LEVEL N:2`,
`CASTING_C C:29`, `BUY_C C:29`, `NAME_TXT C:10`, `DESC_TXT C:10`,
`UNIT_ID C:10`, `RESTORE_M N:3`, `AREA N:3`, `MODIF_ID C:10`,
`MODIF_TXT C:10`, `DAMAGE_SRC N:2`, `DAMAGE_QTY N:3`, `HEAL_QTY N:3`,
`AI_CAT N:2`. **V**

`Globals\Tglobal.dbf` — 1624 records (1336 live, 288 deleted), header 225 B,
record 1028 B (closes). Fields: `TXT_ID C:10`, `ENGLISH C:254`,
`FRENCH C:254`, `GERMAN C:254`, `VERIFIED L:1`, `CONTEXT C:254`. This is the
localisation table (three languages, 254-byte strings). **V**

`Scens\SScen.DBF` — 16 records, header 737 B, record 221 B (closes). Fields are
the per-scenario container names (`NO_SCEN`, `MAP`, `ROADS`, `MISSION`, `PLAN`,
`FORTS`, `UNITS`, `STACKS`, `PLAYERS`, `ITEMS`, `BAGS`, `SITES`, `RUINS`,
`TOMBS`, `LMARKS`, `SPELLS`, `CASTS`, `INFO`, `HINTS`, `CRYSTALS`, `RODS`,
`DIPLO` — all `C:10`). **V**

`ImgData\IUNIT.DBF` — 328 records (308 live, 20 deleted), header 385 B,
record 61 B (closes). Fields map a `UNIT_ID C:10` to animation names:
`FACE C:8`, `HIT C:8`, `UNITMOVE C:8`, `UNITFRAME N:3`, `SPELL C:8`,
`SPELLFRAME N:3`, `SPELLDIR L:1`, `INDIVSPELL C:8`, `INDIVFRAME C:2`,
`INDIVDIR L:1`. **V** — of these 8-byte names, only `FACE` matches an `MQDB`
name-table entry (see §2); `HIT` and `UNITMOVE` match nothing.

### Cross-reference convention

IDs are fixed-width strings, base form **10** characters:

```
<prefix> <3-digit pad> <2-letter type> <4-digit index>
   g         000            uu            0000        ->  g000uu0000
```

Observed prefixes/types (all **V**, read from the columns named in §1 field
tables): `g` = a game entity (`uu` unit, `rr` race, `bb` build, `aa`
ability/attack, `sp` spell); `x` = a localisation key (`tg` text-global), which
resolves against `Tglobal.TXT_ID`.

There is **no leading count digit or marker** on a reference. A field that
references one or more IDs holds the plain 10-character ID; multi-ID values are
colon-separated lists such as `g0200:r0000:y0000:e0000:w0000` (a five-resource
cost vector). **V** for the plain-ID form and the colon separation; the
individual `<letter><4-digit>` tokens are **H** (resource quantities, not yet
linked to a table). The `*` byte that *appears* to prefix some `TXT_ID`s is the
record deletion flag at byte 0, not part of the ID — it is skipped by the
reader, never part of a reference.

Tables proven to link (each link is a `report.cross_references` row, counted
over **live** records, **V**):

| From | To | Non-empty refs | Resolved |
|---|---|---|---|
| `GACTION.NAME_TXT` | `Tglobal.TXT_ID` | 13 | 13 |
| `GUNITS.NAME_TXT` | `Tglobal.TXT_ID` | 308 | 308 |
| `GUNITS.DESC_TXT` | `Tglobal.TXT_ID` | 308 | 308 |
| `GBUILD.NAME_TXT` | `Tglobal.TXT_ID` | 68 | 68 |
| `GSPELLS.NAME_TXT` | `Tglobal.TXT_ID` | 80 | 80 |
| `GUNITS.RACE_ID` | `GRACE.RACE_ID` | 223 | 223 |

`Tglobal` holds 1,336 distinct `TXT_ID`s among its live records
(`report.cross_references.text_id_count`); including the 288 deleted records the
distinct count is 1,609 (`report.cross_references.text_id_distinct_all`). Every
`*_TXT` reference in the tables above resolves, case-insensitively — which is
the same case-insensitivity the plan's Q6 asks about, observed here at the
*data* level, not just the path level.

---

## 2. `MQDB` container (`.dbi` / `.ff` / `.wdb`)

### Header (28 bytes)

| Offset | Size | Field | Observed |
|---|---|---|---|
| 0x00 | 4 | magic `MQDB` | **V** |
| 0x04 | 4 | zero | **V** |
| 0x08 | 4 | version (u32) | 9 — **V** (LE; the BE read `150994944` is the wrong-endian decoding) |
| 0x0C | 4 | zero | **V** |
| 0x10 | 4 | zero | **V** |
| 0x14 | 4 | zero | **V** |
| 0x18 | 4 | near-end-of-file hint | **H** — always short of `file_size` by 1024..31042 bytes and never equal; see Q5 |

### `MQRC` chunks (28-byte header each)

| Offset | Size | Field | Observed |
|---|---|---|---|
| 0x00 | 4 | tag `MQRC` | **V** |
| 0x04 | 4 | zero | **V** |
| 0x08 | 4 | chunk id (u32) | small, non-unique, non-monotonic — **V** |
| 0x0C | 4 | second length field | usually equals payload size, `0` for some chunks — **H** (meaning open, Q5) |
| 0x10 | 4 | **payload size (u32, LE)** | the field that tiles — **V** |
| 0x14 | 4 | one (most chunks) / zero | **V** |
| 0x18 | 4 | zero | **V** |
| 0x1C | … | payload | — |

### The scanner's hypothesis vote

Because the layout is recovered by scanning rather than assumed, `scan_mqdb`
evaluates **8 hypotheses** (chunk-table start ∈ {24, 28} × endianness ∈
{little, big} × size-field offset ∈ {+0x0C, +0x10}) and prints the score for
each. The score is `chunks×10000 + tiles×1000 + in_range×100 +
(+10 for size@+0x10)`. For every one of the 19 containers the vote is the
same, and the losing hypotheses are visible in the output:

```
Interf/Interf.dbi: 5405693 bytes
  magic='MQDB' is_mqdb=True version_le=9 version_be=150994944 header@0x18=5397501
  hypotheses (start, endian, size@, chunks, in_range, tiles, leftover, score):
    start= 28 little size@+16 chunks= 477 in_range= True tiles= True leftover= 0 score=4771110
    start= 28 little size@+12 chunks= 477 in_range= True tiles= True leftover= 0 score=4771100
    start= 28    big size@+16 chunks=   0 in_range=False tiles=False leftover=-1 score= 0
    start= 28    big size@+12 chunks=   0 in_range=False tiles=False leftover=-1 score= 0
    start= 24 little size@+16 chunks=   0 in_range= True tiles=False leftover=5405669 score= 0
    ...
  winner: start=28 little-endian size@+16, 477 chunks, tiles=True, ...
```

That output is the **V** evidence for this whole section: run
`python -m disciples_play data --game-dir "/game-files/Disciples Gold"` and the
hypothesis table above appears verbatim for `Interf.dbi`. Key readings:

* The chunk table starts at offset **28** (immediately after the header); at
  24 there is no `MQRC` tag, so both `start=24` hypotheses score 0 chunks. **V**
* The payload size is **little-endian**; the big-endian read overruns on the
  first chunk (`in_range=False`). **V**
* The payload size lives at chunk offset **+0x10**, not +0x0C. For 16 of 19
  files the two fields happen to be equal and either position tiles; for
  `MIDGARD.DBI`, `UNIT.DBI` and `ISO.DBI` only `+0x10` tiles (`+0x0C` is 0 on
  the first chunk of `ISO.DBI`). **V** — this is the *visible wrong-guess* the
  task asked for: a scanner that assumed the size at `+0x0C` would report 3
  files as "does not tile" and silently mislabel them.

All 19 containers tile to EOF with `start=28, LE, size@+0x10` — `report.mqdb[]`
has `winner.tiles_exactly == true` for all 19. **V**

| Container | Size (B) | Chunks |
|---|---|---|
| `Interf/Interf.dbi` | 5,405,693 | 477 |
| `Interf/Menus.dbi` | 1,551,339 | 300 |
| `Interf/ScenEdit.dbi` | 1,776,112 | 496 |
| `Interf/Menus.ff` | 14,367,776 | 58 |
| `Imgs1/BATTLE.DBI` | 598,882 | 36 |
| `Imgs1/CAPITAL.DBI` | 865,171 | 74 |
| `Imgs1/ICONS.DBI` | 684,188 | 241 |
| `Imgs1/MIDGARD.DBI` | 3,801,155 | 217 |
| `Imgs1/PALMAP.DBI` | 83,125 | 31 |
| `Imgs1/TERRAIN.DBI` | 964,027 | 822 |
| `Imgs1/UNIT.DBI` | 788,049 | 164 |
| `Imgs1/SPELL.FF` | 9,397,780 | 51 |
| `Imgs2/BATTLE.FF` | 12,189,116 | 380 |
| `Imgs2/CAPITAL.FF` | 1,093,756 | 49 |
| `Imgs2/ISO.DBI` | 1,435,101 | 941 |
| `Imgs2/ISO.FF` | 8,593,588 | 731 |
| `Sounds1/BATTLE.WDB` | 5,259,132 | 325 |
| `Sounds2/CAPITAL.WDB` | 1,176,338 | 12 |
| `Sounds2/MIDGARD.WDB` | 9,792,758 | 302 |

### Chunk-id roles (observed, **H** for the semantics, **V** for the numbers)

The first three chunks of a `.dbi` image container are, in **8 of 11** files, a
**name table** (chunk id 3), a **palette** (id 2, payload 1024 B = 256 entries
× 4 B), and a **`DBI`** chunk (id 1, payload 32 B = 8-byte name `"DBI"` + 6
u32s). The order is *not* universal: `Imgs1\BATTLE.DBI` and
`Imgs1\CAPITAL.DBI` start `[1, 2, 3]`, and `Imgs2\ISO.DBI` starts `[956, 2, 1]`
(`report.mqdb[].chunks[].chunk_id`). The `.ff` and `.wdb` containers start
differently again (`[1, 2, 3]` for all five `.ff`; `[1, 2, 4]` for the two
`CAPITAL`/`MIDGARD` wave databases). After that, id 4+ chunks are named
image/sprite layers. **V** (the numbers) / **H** (what each id *means*). The
name-table chunk is a 16-byte-entry list: 8-byte null-terminated name + two u32s
(observed `0` and a small increasing integer). For `Interf.dbi` the name table
has 473 entries (7568 B payload ÷ 16). **V** (numbers) / **H** (what the two
trailing u32s mean). The palette bytes themselves are **not decoded** — the
report states `1024` bytes and `256×4`, never the colour values.

The leading 8 bytes of each image chunk's payload are its name (e.g.
`ARMY01C`, `BUILTB01C`, `TRAINER`), null-terminated ASCII. `ImgData\IUNIT.DBF`'s
`FACE` column (148 distinct 8-byte values) matches `Imgs1\UNIT.DBI`'s name
table **148/148, case-insensitively** (`fh001s00` ↔ `FD026S00`); the `HIT` and
`UNITMOVE` columns (145 and 151 distinct values) match **nothing** in any of the
11 name tables. **V**.

---

## 3. Dialog scripts (`.dlg`)

Plain text (CRLF), tab-separated. Grammar: a `DIALOG <name>,x,y,w,h,<flags>,<bg>`
line, then `BEGIN`, then element rows, then `END`. Element rows are
`<TAG>\t<name>,<args…>`. **V**

```text
DIALOG	DLG_CHAT,0,0,640,480,1,CHAT
BEGIN
	BUTTON	BTN_UP,486,61,511,86,OPT05N,OPT05H,OPT05C,OPT05D,,0
	TEXT	TXT_ACTION_RESULT,85,67,335,102,255,255,255,0,0,0,LEFT_ALIGN,VCENTER_ALIGN
END
```

The `DIALOG` header carries its **own** `x,y,w,h`, and the dialogs are usually
*smaller* than the 640×480 frame: `Interf\Interf.dlg` has 90 dialogs across 13
distinct sizes (`177×201` … `640×480`; only 29 of the 90 are `640×480`),
`Menus.dlg` has 15 across 3, and `ScenEdit.dlg` has 48 across 24. **V** — the
geometry is plain editable text placed within the game's 640×480 canvas, but it
is not a single fixed full-screen size per dialog.

Element tags observed across the 3 files (`report.dlg[].element_types`): `IMAGE`,
`BUTTON`, `TEXT`, `TOGGLE`, `EDIT`, `LBOX`, `MCLBOX`, `TLBOX`, `RADIO`,
`SCROLL`, `SPIN`. **V**

| File | DIALOG blocks | Lines |
|---|---|---|
| `Interf/Interf.dlg` | 90 | 1206 |
| `Interf/Menus.dlg` | 15 | 201 |
| `Interf/ScenEdit.dlg` | 48 | 669 |

This is the evidence for the plan's claim that the UI geometry is hardcoded in
plain text: the `x,y,w,h` tuples are editable strings, not compiled constants.
**V** — with the correction that each dialog declares its own size, rather than
every dialog filling 640×480.

---

## 4. `PALANIM.DAT` (palette animation)

Plain text, 112 non-empty lines, 1847 B (`report.palanim[]`). First line is a
count (`66`), second is `5`, then **5 animation blocks** (`report.palanim[0]
.animation_blocks`), each introduced by a header line of three integers
(`<slot> -1 <frames>`) followed by `<frames>`+1 body rows of
`<index> <R> <G> <B>`. The body rows are palette indices and RGB triples and
are **not** dumped — the report records the grammar and the counts, not the
colours. **V** for structure; the meaning of `66` and `5` is **H**.

---

## 5. Fonts (`.MFT`)

Six files (`LARGE`, `MEDBOLD`, `MEDIUM`, `NORMAL`, `SMALL`, `VLARGE`), each
`MFT\0` magic + version u32 = 2 (`report.mft[]`, all six `version == 2`). **V**
for magic/version; the glyph table below the header is **H** (not decoded —
this is geometry, and only the header is claimed).

---

## 6. Sound containers (`.wdb`)

Three files, all `MQDB` v9 (see §2 table) — the wave database reuses the image
container format with sound payloads. `report.mqdb[]` lists `BATTLE.WDB` 325
chunks, `CAPITAL.WDB` 12, `MIDGARD.WDB` 302, each tiling to EOF. **V** for the
container structure; the per-chunk audio codec is **H** (not decoded).

---

## 7. Music (`.wav`)

25 files, all `RIFF`/`WAVE` (`report.wav[]`). 23 use WAVE format tag 17 (IMA
ADPCM) at 22050 Hz stereo, 1 (`AMBIEN11.WAV`) is tag 17 at 44100 Hz stereo, and
1 (`AMBIENT5.WAV`) is tag 1 (PCM) at 22050 Hz **mono**. **V** — a small
refinement of the plan's "plain `.wav`": they are WAVE files, but the majority
are ADPCM-compressed, which only matters to a decoder, not to the "music needs
no CD" conclusion.

---

## 8. Video (`.smk`)

41 Smacker files, all `SMK2` magic (`report.smk[]`). Dimension histogram:
35 at 352×284 (briefings), 4 at 640×292, 2 at 640×480 (`INTRO`, `CREDITS`).
Frame counts and per-file sizes are in the report. **V** for magic and
geometry; the frame data is not decoded.

---

## 9. `Imgs1\CAPITAL.DAT` (found while scanning, not in the plan)

Plain text, INI-like: 4 sections (`[HUMAN]`, `[UNDEAD]`, `[DWARF]`,
`[HERETIC]`) and 118 `key=value` lines over 138 non-empty lines
(`report.capital_dat[]`). **V** for structure; semantics **H**.

---

## Open questions

| # | Question | Status | What would settle it |
|---|---|---|---|
| Q5 | `MQDB` header field @ `0x18` (near file size but not equal), and the `MQRC` chunk field @ `+0x0C` (usually = size, `0` on some chunks) | **H** | Trace the reader in `C4DLL-R.DLL`/`HA312W32.DLL` to the two fields, or find a file where `+0x0C ≠ +0x10` on an *image* chunk and diff the payloads against a retail decode. |
| Q6 | Is the case-insensitive resolution (paths *and* ID strings) Wine, or a Win32 API inside the game's DLLs? | **H** (was "works, mechanism unverified" in the plan) | A retail run under Wine with `WINEDEBUG=+file` while `Config.exe`/the game resolves `globals` vs `Globals`; or a disassembly of the string-compare in `C4DLL-R.DLL`. |
| Q7 | What do the two trailing u32s of a name-table entry mean (observed `0` and a small increasing integer)? | **H** (new) | Cross-check against the `ImgData\*.DBF` frame-count fields (`UNITFRAME`, `SPELLFRAME`): if entry *i*'s integer equals the sprite's frame count, it is a frame count. |
| Q8 | What are the `MQRC` chunk-id *roles* (ids 1/2/3 are `DBI`/palette/name-table in some files but appear in different orders; what do the id-4+ values and the out-of-order ids like 956 encode)? | **H** (new) | Group chunks by id and correlate the id with the payload's leading name/type; a decode of one id's payload confirms the role. |
| Q9 | `.wdb` per-chunk audio codec and `.smk`/`.wav` decode | **H** (new) | Standard Smacker / IMA-ADPCM decoders against one file each — out of scope for this card (no media decoding). |

The plan's former Q10 (a `*` prefix on some `Tglobal.TXT_ID`s) is **resolved**:
the `*` was the record deletion flag at byte 0, leaking into the field read by
an off-by-one; there is no `*` prefix on IDs.

Nothing above is filled in by analogy; each row states what would actually
falsify it.
