"""Synthetic fixture builders for the data-layer tests.

Everything in this module constructs *fake* files programmatically -- a tiny
dBase III writer and a tiny ``MQDB``-shaped container writer.  No game bytes
appear anywhere: the fixtures are generated from scratch so the parsers are
tested against data whose layout is known to the test, not against the retail
install.
"""

from __future__ import annotations

import struct
from pathlib import Path

# --- dBase III ---------------------------------------------------------------

DBASE3 = 0x03
FIELD_DESCRIPTOR = 32
FIELD_TERMINATOR = 0x0D
EOF_MARKER = 0x1A
#: dBase III deletion-flag bytes: 0x20 space = live, 0x2A ``*`` = deleted.
LIVE_FLAG = 0x20
DELETED_FLAG = 0x2A


def _field_descriptor(name: str, ftype: str, length: int) -> bytes:
    desc = bytearray(FIELD_DESCRIPTOR)
    desc[: len(name)] = name.encode("ascii")
    desc[11] = ord(ftype)
    desc[16] = length
    return bytes(desc)


def build_dbf(
    fields: list[tuple[str, str, int]],
    records: list[bytes],
    *,
    version: int = DBASE3,
    year: int = 99,
    month: int = 1,
    day: int = 1,
    deleted: tuple[int, ...] = (),
) -> bytes:
    """Build a synthetic dBase III file whose header arithmetic closes.

    ``fields`` is a list of ``(name, type, length)``; ``records`` is a list of
    field-value blobs, each ``sum(field lengths)`` bytes.  The builder prepends
    the 1-byte deletion flag to each record, so ``record_len == 1 + sum(field
    lengths)`` exactly as in a real dBase III file.  ``deleted`` names the
    record indices whose flag is ``*`` (0x2A); the rest are live (0x20).  The
    returned bytes tile the file exactly: ``header_len + records*record_len +
    1 == len(result)``.
    """

    field_total = sum(length for _, _, length in fields)
    record_len = 1 + field_total
    for rec in records:
        if len(rec) != field_total:
            raise ValueError(f"field-value length {len(rec)} != {field_total}")
    header_len = 32 + len(fields) * FIELD_DESCRIPTOR + 1

    out = bytearray()
    out.append(version)
    out.append(year)
    out.append(month)
    out.append(day)
    out += struct.pack("<I", len(records))
    out += struct.pack("<H", header_len)
    out += struct.pack("<H", record_len)
    out += b"\x00" * 20  # reserved header bytes 12..31
    for name, ftype, length in fields:
        out += _field_descriptor(name, ftype, length)
    out.append(FIELD_TERMINATOR)
    for i, rec in enumerate(records):
        out.append(DELETED_FLAG if i in deleted else LIVE_FLAG)
        out += rec
    out.append(EOF_MARKER)
    return bytes(out)


# --- MQDB --------------------------------------------------------------------

MAGIC = b"MQDB"
CHUNK_TAG = b"MQRC"


def build_mqdb(
    chunks: list[tuple[int, bytes] | tuple[int, bytes, int]],
    *,
    version: int = 9,
    header_field_0x18: int = 0,
) -> bytes:
    """Build a synthetic ``MQDB`` container: a 28-byte header then ``MQRC`` chunks.

    ``chunks`` is a list of ``(chunk_id, payload)`` pairs, or
    ``(chunk_id, payload, second_field)`` triples where ``second_field`` is the
    value written to the chunk-header field at offset ``+0x0C`` (the field that
    usually mirrors the payload size but is 0 for some real chunks).  When the
    triple form is omitted, ``second_field`` defaults to ``len(payload)`` so the
    synthetic container matches the common case.  The header field at ``0x18``
    defaults to 0; pass an explicit value to exercise the hypothesis scoring
    against a non-zero hint.
    """

    out = bytearray()
    out += MAGIC
    out += struct.pack("<I", 0)  # offset 0x04
    out += struct.pack("<I", version)  # offset 0x08
    out += struct.pack("<I", 0)  # offset 0x0C
    out += struct.pack("<I", 0)  # offset 0x10
    out += struct.pack("<I", 0)  # offset 0x14
    out += struct.pack("<I", header_field_0x18)  # offset 0x18
    for entry in chunks:
        chunk_id, payload = entry[0], entry[1]
        second_field = entry[2] if len(entry) > 2 else len(payload)
        out += CHUNK_TAG
        out += struct.pack("<I", 0)  # chunk offset +0x04
        out += struct.pack("<I", chunk_id)  # chunk offset +0x08
        out += struct.pack("<I", second_field)  # chunk offset +0x0C
        out += struct.pack("<I", len(payload))  # chunk offset +0x10 (size)
        out += struct.pack("<I", 1)  # chunk offset +0x14
        out += struct.pack("<I", 0)  # chunk offset +0x18
        out += payload
    return bytes(out)


def write(path: str | Path, data: bytes) -> Path:
    """Write ``data`` to ``path`` (creating parents) and return the ``Path``."""

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p
