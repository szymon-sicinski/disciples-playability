"""Read-only dBase III reader for *Disciples: Sacred Lands Gold* ``.DBF`` tables.

The game ships its game data as a family of dBase III files (magic byte
``0x03``).  This module reads only the *structure* of those files -- the header
and the per-field descriptors -- so a report can be produced without touching
the row data as content.  No row values are interpreted as game data; the
reader exists to state, and verify, the table geometry.

A dBase III file is laid out as::

    offset  size  meaning
    0x00    1     version byte (0x03 == dBase III, no memo file)
    0x01    3     last-update date (YY, MM, DD)
    0x04    4     number of records (little-endian u32)
    0x08    2     header length in bytes (little-endian u16)
    0x0A    2     record length in bytes (little-endian u16)
    0x20    ...   field descriptors, 32 bytes each
    ...     1     0x0D terminator
    ...     ...   records, ``reclen`` bytes each
    EOF     1     0x1A end-of-file marker

Each record begins with a 1-byte deletion flag (``0x20`` space = live, ``0x2A``
``*`` = deleted) followed by the field values, so ``record_len == 1 +
sum(field lengths)``.  The reader starts field offsets at 1 to skip that flag,
and skips deleted records when reading a column.

The arithmetic identity ``header_len + records * record_len + 1 == file_size``
is the structural check used throughout this project: when it holds, the header
is internally consistent and the record grid tiles the file exactly.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path

#: dBase III magic byte (no DBT memo file).
DBASE3 = 0x03
#: Size of the fixed part of a dBase III header.
HEADER_FIXED = 32
#: Size of one field descriptor.
FIELD_DESCRIPTOR = 32
#: Terminator byte that ends the field-descriptor list.
FIELD_TERMINATOR = 0x0D
#: End-of-file marker byte.
EOF_MARKER = 0x1A
#: Bytes before the first field in every record: the deletion flag.
RECORD_PREFIX_LEN = 1
#: Deletion-flag byte that marks a logically deleted record.
DELETED_FLAG = 0x2A


@dataclass(frozen=True)
class Field:
    """One dBase III field descriptor."""

    name: str
    type: str
    length: int
    decimal_count: int = 0


@dataclass(frozen=True)
class DbfHeader:
    """The structural part of a dBase III file, no row data."""

    version: int
    year: int
    month: int
    day: int
    records: int
    header_len: int
    record_len: int
    fields: tuple[Field, ...]

    @property
    def field_count(self) -> int:
        return len(self.fields)

    @property
    def arithmetic_ok(self) -> bool:
        """True when the header length is internally consistent.

        ``header_len`` must equal ``32 + N*32 + 1`` for exactly ``N`` field
        descriptors.  This is a geometry check that does not need the file.
        """

        return self.header_len == HEADER_FIXED + self.field_count * FIELD_DESCRIPTOR + 1

    def closes_file(self, file_size: int) -> bool:
        """True when the header's record grid tiles ``file_size`` exactly."""

        return self.header_len + self.records * self.record_len + 1 == file_size


def parse_dbf_header(data: bytes) -> DbfHeader:
    """Parse the header and field descriptors from ``data``.

    ``data`` only needs to cover the header (``header_len`` bytes); the row
    bytes are never read.  Raises :class:`ValueError` if the field-descriptor
    list does not terminate where the header length says it must.
    """

    if len(data) < HEADER_FIXED:
        raise ValueError("buffer too short for a dBase III header")
    version = data[0]
    year, month, day = data[1], data[2], data[3]
    records = struct.unpack_from("<I", data, 4)[0]
    header_len = struct.unpack_from("<H", data, 8)[0]
    record_len = struct.unpack_from("<H", data, 10)[0]

    field_count = (header_len - HEADER_FIXED - 1) // FIELD_DESCRIPTOR
    if (header_len - HEADER_FIXED - 1) % FIELD_DESCRIPTOR != 0:
        raise ValueError(f"header_len {header_len} is not 32 + N*32 + 1")
    if HEADER_FIXED + field_count * FIELD_DESCRIPTOR >= len(data):
        raise ValueError("buffer too short for the field descriptors")

    fields: list[Field] = []
    for i in range(field_count):
        off = HEADER_FIXED + i * FIELD_DESCRIPTOR
        desc = data[off : off + FIELD_DESCRIPTOR]
        name = desc[:11].split(b"\x00", 1)[0].decode("latin-1")
        ftype = chr(desc[11])
        length = desc[16]
        decimal_count = desc[17]
        fields.append(Field(name=name, type=ftype, length=length, decimal_count=decimal_count))

    terminator = data[HEADER_FIXED + field_count * FIELD_DESCRIPTOR]
    if terminator != FIELD_TERMINATOR:
        raise ValueError(
            f"field-list terminator is {terminator:#04x}, expected {FIELD_TERMINATOR:#04x}"
        )

    return DbfHeader(
        version=version,
        year=year,
        month=month,
        day=day,
        records=records,
        header_len=header_len,
        record_len=record_len,
        fields=tuple(fields),
    )


def read_dbf(path: str | os.PathLike[str]) -> tuple[DbfHeader, bytes]:
    """Read a ``.DBF`` file and return ``(header, records_bytes)``.

    ``records_bytes`` is the raw record grid (``records * record_len`` bytes)
    read once, so callers that want to inspect row values can slice it without
    re-opening the file.  This module itself never interprets row content.

    Raises :class:`ValueError` (never :class:`struct.error`) when the buffer is
    too short to hold a header, or when the header's field-descriptor list is
    malformed -- so one bad file surfaces as a clean per-file error rather than
    an uncaught traceback.
    """

    path = Path(path)
    with open(path, "rb") as fh:
        fixed = fh.read(HEADER_FIXED)
        if len(fixed) < HEADER_FIXED:
            raise ValueError(f"buffer too short for a dBase III header ({len(fixed)} bytes)")
        header_len = struct.unpack_from("<H", fixed, 8)[0]
        header = parse_dbf_header(fixed + fh.read(header_len - HEADER_FIXED))
        records_bytes = fh.read(header.records * header.record_len)
    return header, records_bytes


def _deleted_record_count(records_bytes: bytes, header: DbfHeader) -> int:
    """Count records whose deletion flag is ``*`` (``0x2A``).

    Iterates only over the record bytes actually present, so a truncated file
    (whose record grid is shorter than ``records * record_len``) is counted
    over what exists rather than indexing out of range.
    """

    present = min(header.records, len(records_bytes) // header.record_len)
    return sum(1 for i in range(present) if records_bytes[i * header.record_len] == DELETED_FLAG)


def summarize_dbf(path: str | os.PathLike[str]) -> dict:
    """Return a JSON-serialisable structural summary of a ``.DBF`` file.

    Contains geometry and field descriptors only -- no row values, so a report
    built from this never leaks game data.  A file that cannot be read (not a
    dBase file, truncated, unreadable) is reported as ``{"path": ..., "error":
    ...}`` instead of raising, so one bad byte in a 131-file install does not
    take the whole report down.
    """

    path = Path(path)
    try:
        size = os.path.getsize(path)
        header, records_bytes = read_dbf(path)
    except (ValueError, OSError) as exc:
        return {"path": path.name, "error": str(exc)}

    deleted = _deleted_record_count(records_bytes, header)
    return {
        "path": path.name,
        "size": size,
        "version": header.version,
        "records": header.records,
        "live_records": header.records - deleted,
        "deleted_records": deleted,
        "header_len": header.header_len,
        "record_len": header.record_len,
        "arithmetic_ok": header.closes_file(size),
        "field_count": header.field_count,
        "fields": [{"name": f.name, "type": f.type, "length": f.length} for f in header.fields],
    }


def field_offsets(header: DbfHeader) -> dict[str, tuple[int, int]]:
    """Map each field name to ``(offset, length)`` within one record.

    Offsets start at :data:`RECORD_PREFIX_LEN` (1) because every dBase III
    record begins with a 1-byte deletion flag before the first field.
    """

    offsets: dict[str, tuple[int, int]] = {}
    off = RECORD_PREFIX_LEN
    for f in header.fields:
        offsets[f.name] = (off, f.length)
        off += f.length
    return offsets


def column_values(
    header: DbfHeader,
    records_bytes: bytes,
    field_name: str,
    *,
    skip_deleted: bool = True,
) -> list[str]:
    """Decode one named column as stripped ``latin-1`` strings.

    Structural only: this returns identifier/geometry strings (such as the
    ``ID``-style columns) and never interprets numeric or blob content.

    Records whose deletion flag is ``*`` (``0x2A``) are skipped unless
    ``skip_deleted`` is false; deleted rows are never returned as live data.
    """

    if field_name not in {f.name for f in header.fields}:
        return []
    offset, length = field_offsets(header)[field_name]
    values: list[str] = []
    present = min(header.records, len(records_bytes) // header.record_len)
    for i in range(present):
        raw = records_bytes[i * header.record_len : (i + 1) * header.record_len]
        if skip_deleted and raw[0] == DELETED_FLAG:
            continue
        values.append(raw[offset : offset + length].decode("latin-1").strip())
    return values
