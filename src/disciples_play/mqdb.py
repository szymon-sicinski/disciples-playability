"""Read-only ``MQDB`` container scanner for *Disciples: Sacred Lands Gold*.

``.dbi`` (interface / image), ``.ff`` (large frame data) and ``.wdb`` (sound)
files all share one container format identified by the 4-byte magic ``MQDB``.
This module is a *chunk/tag scanner*: it never assumes a field layout beyond
the parts that are directly observable, and it reports offsets and sizes only.
It decodes no pixels, no palette entries and no audio samples.

Observed structure (verified against the retail install, see
``docs/data-layout.md``)::

    offset  size  meaning
    0x00    4     magic ``MQDB``
    0x04    4     zero
    0x08    4     version (little-endian u32; observed value 9)
    0x0C    4     zero
    0x10    4     zero
    0x14    4     zero
    0x18    4     near-end-of-file hint (exact meaning open, see Q5)
    0x1C    ...   a linear sequence of ``MQRC`` chunks

Each ``MQRC`` chunk is::

    offset  size  meaning
    0x00    4     tag ``MQRC``
    0x04    4     zero
    0x08    4     chunk id (small, non-unique integer)
    0x0C    4     second length field (usually equals the payload size, 0 for
                  some chunks; meaning open)
    0x10    4     payload size (little-endian u32) -- the field that tiles
    0x14    4     one (most chunks) or zero
    0x18    4     zero
    0x1C    ...   payload of ``size`` bytes

The chunks tile the file exactly.  Because the structure is recovered by
*scanning* rather than assumed, the scanner evaluates competing hypotheses --
both endiannesses, two candidate positions for the first chunk, and two
candidate positions for the payload-size field -- and prints the score for
each, so a wrong assumption is visible in the output instead of hiding behind a
plausible-looking table.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path

#: Container magic, shared by ``.dbi`` / ``.ff`` / ``.wdb``.
MAGIC = b"MQDB"
#: Chunk tag that begins every payload chunk.
CHUNK_TAG = b"MQRC"
#: Size of the fixed container header.
HEADER_LEN = 28
#: Size of one chunk header.
CHUNK_HEADER_LEN = 28
#: Candidate positions for the first chunk (the two plausible table starts).
CANDIDATE_STARTS = (HEADER_LEN, 24)
#: Candidate offsets of the payload-size field within a chunk header.
SIZE_FIELD_OFFSETS = (16, 12)
#: Both endiannesses to evaluate.
ENDIANNESSES = ("little", "big")


@dataclass(frozen=True)
class Chunk:
    """One ``MQRC`` chunk: offset, id, payload size and leading name."""

    offset: int
    chunk_id: int
    payload_size: int
    name: str


@dataclass(frozen=True)
class Hypothesis:
    """A candidate interpretation of the chunk table."""

    start_offset: int
    endian: str
    size_offset: int


@dataclass(frozen=True)
class HypothesisResult:
    """The outcome of walking chunks under one :class:`Hypothesis`."""

    hypothesis: Hypothesis
    chunks: int
    in_range: bool
    tiles_exactly: bool
    leftover: int
    offsets_non_decreasing: bool
    sizes_non_decreasing: bool
    score: int


def _read_u32(data: bytes, offset: int, endian: str) -> int:
    fmt = "<I" if endian == "little" else ">I"
    return struct.unpack_from(fmt, data, offset)[0]


def _leading_name(payload: bytes) -> str:
    if len(payload) < 8:
        return ""
    raw = payload[:8]
    # Layer names are null-terminated ASCII (e.g. b"ARMY01C\x00").
    name = raw.split(b"\x00", 1)[0]
    if name and all(0x20 <= b < 0x7F for b in name):
        return name.decode("ascii")
    return ""


def _walk_chunks(data: bytes, file_size: int, hypothesis: Hypothesis) -> HypothesisResult:
    """Walk ``MQRC`` chunks under ``hypothesis`` and score the result."""

    start = hypothesis.start_offset
    pos = start
    chunks: list[Chunk] = []
    in_range = True
    while pos + CHUNK_HEADER_LEN <= file_size:
        if data[pos : pos + 4] != CHUNK_TAG:
            break
        chunk_id = _read_u32(data, pos + 8, hypothesis.endian)
        size = _read_u32(data, pos + hypothesis.size_offset, hypothesis.endian)
        payload_start = pos + CHUNK_HEADER_LEN
        if payload_start + size > file_size:
            in_range = False
            break
        chunks.append(
            Chunk(
                offset=pos,
                chunk_id=chunk_id,
                payload_size=size,
                name=_leading_name(data[payload_start : payload_start + size]),
            )
        )
        pos = payload_start + size
        if pos == file_size:
            break
        if pos > file_size:
            in_range = False
            break

    if not in_range:
        leftover = -1
        tiles_exactly = False
    else:
        leftover = file_size - pos
        tiles_exactly = leftover == 0

    offsets = [c.offset for c in chunks]
    sizes = [c.payload_size for c in chunks]
    offsets_non_decreasing = all(offsets[i] >= offsets[i - 1] for i in range(1, len(offsets)))
    sizes_non_decreasing = all(sizes[i] >= sizes[i - 1] for i in range(1, len(sizes)))

    # The score is driven by the criteria that discriminate between a
    # self-consistent chunk table and a wrong assumption: how many chunks walk,
    # whether the walk stays in range, and whether it tiles the file exactly.
    # ``sizes_non_decreasing`` is reported for completeness but is *not* part of
    # the score: this is a tag-length-value format, so payload sizes vary by
    # design and a sorted-size check would reject the correct interpretation.
    score = (
        len(chunks) * 10_000
        + (1_000 if tiles_exactly else 0)
        + (100 if in_range else 0)
        + (10 if hypothesis.size_offset == 16 else 0)
    )
    return HypothesisResult(
        hypothesis=hypothesis,
        chunks=len(chunks),
        in_range=in_range,
        tiles_exactly=tiles_exactly,
        leftover=leftover,
        offsets_non_decreasing=offsets_non_decreasing,
        sizes_non_decreasing=sizes_non_decreasing,
        score=score,
    )


def _tag_positions(data: bytes, tag: bytes) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        i = data.find(tag, start)
        if i == -1:
            break
        positions.append(i)
        start = i + 1
    return positions


def scan_mqdb(path: str | os.PathLike[str]) -> dict:
    """Scan one ``MQDB`` container and return a JSON-serialisable report.

    The report carries the file size, magic, version, the competing hypotheses
    and their scores, the winning chunk table, and the leading names of each
    chunk.  It never decodes payload bytes and never computes a hash.
    """

    path = Path(path)
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        data = fh.read()

    magic = data[:4]
    is_mqdb = magic == MAGIC
    version = _read_u32(data, 8, "little") if len(data) >= 12 else None
    version_be = _read_u32(data, 8, "big") if len(data) >= 12 else None
    field_0x18 = _read_u32(data, 0x18, "little") if len(data) >= 0x1C else None

    hypotheses = [
        _walk_chunks(data, size, Hypothesis(start_offset=s, endian=e, size_offset=o))
        for s in CANDIDATE_STARTS
        for e in ENDIANNESSES
        for o in SIZE_FIELD_OFFSETS
    ]
    # Best first: highest score, then smallest leftover (a clean tile wins).
    hypotheses.sort(key=lambda r: (-r.score, r.leftover if r.leftover >= 0 else 10**12))
    winner = hypotheses[0]

    chunks: list[dict] = []
    if is_mqdb and winner.chunks:
        pos = winner.hypothesis.start_offset
        while pos + CHUNK_HEADER_LEN <= size and data[pos : pos + 4] == CHUNK_TAG:
            payload_size = _read_u32(
                data, pos + winner.hypothesis.size_offset, winner.hypothesis.endian
            )
            payload_start = pos + CHUNK_HEADER_LEN
            chunks.append(
                {
                    "offset": pos,
                    "chunk_id": _read_u32(data, pos + 8, winner.hypothesis.endian),
                    "payload_size": payload_size,
                    "name": _leading_name(data[payload_start : payload_start + payload_size]),
                }
            )
            pos = payload_start + payload_size
            if pos >= size:
                break

    return {
        "path": path.name,
        "size": size,
        "magic": magic.decode("latin-1"),
        "is_mqdb": is_mqdb,
        "version_le": version,
        "version_be": version_be,
        "header_field_0x18": field_0x18,
        "hypotheses": [
            {
                "start_offset": r.hypothesis.start_offset,
                "endian": r.hypothesis.endian,
                "size_offset": r.hypothesis.size_offset,
                "chunks": r.chunks,
                "in_range": r.in_range,
                "tiles_exactly": r.tiles_exactly,
                "leftover": r.leftover,
                "offsets_non_decreasing": r.offsets_non_decreasing,
                "sizes_non_decreasing": r.sizes_non_decreasing,
                "score": r.score,
            }
            for r in hypotheses
        ],
        "winner": {
            "start_offset": winner.hypothesis.start_offset,
            "endian": winner.hypothesis.endian,
            "size_offset": winner.hypothesis.size_offset,
            "chunks": winner.chunks,
            "in_range": winner.in_range,
            "tiles_exactly": winner.tiles_exactly,
            "leftover": winner.leftover,
            "offsets_non_decreasing": winner.offsets_non_decreasing,
            "sizes_non_decreasing": winner.sizes_non_decreasing,
            "score": winner.score,
        },
        "chunks": chunks,
        "mqrc_tag_count": len(_tag_positions(data, CHUNK_TAG)),
    }


def render_mqdb_report(report: dict) -> str:
    """Render a :func:`scan_mqdb` report as human-readable text.

    The hypothesis table is printed so a wrong guess is visible: each row shows
    the start offset, endianness, size-field offset, chunks walked, whether the
    walk stayed in range and tiled the file, and its score.
    """

    lines: list[str] = []
    lines.append(f"{report['path']}: {report['size']} bytes")
    lines.append(
        f"  magic={report['magic']!r} is_mqdb={report['is_mqdb']} "
        f"version_le={report['version_le']} version_be={report['version_be']} "
        f"header@0x18={report['header_field_0x18']}"
    )
    if not report["is_mqdb"]:
        lines.append("  not an MQDB container; no chunk table")
        return "\n".join(lines)

    lines.append("  hypotheses (start, endian, size@, chunks, in_range, tiles, leftover, score):")
    for h in report["hypotheses"]:
        lines.append(
            f"    start={h['start_offset']:>3} {h['endian']:>7} size@+{h['size_offset']:<2} "
            f"chunks={h['chunks']:>4} in_range={str(h['in_range']):>5} "
            f"tiles={str(h['tiles_exactly']):>5} leftover={h['leftover']:>8} score={h['score']}"
        )
    w = report["winner"]
    lines.append(
        f"  winner: start={w['start_offset']} {w['endian']}-endian size@+{w['size_offset']}, "
        f"{w['chunks']} chunks, tiles={w['tiles_exactly']}, "
        f"offsets_non_decreasing={w['offsets_non_decreasing']}, "
        f"sizes_non_decreasing={w['sizes_non_decreasing']}"
    )
    lines.append("  chunk table (offset, id, size, name):")
    for c in report["chunks"]:
        lines.append(
            f"    {c['offset']:>8}  id={c['chunk_id']:>5}  {c['payload_size']:>8}  {c['name']}"
        )
    lines.append(f"  MQRC tag occurrences in file: {report['mqrc_tag_count']}")
    return "\n".join(lines)
