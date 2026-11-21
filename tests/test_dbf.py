"""Tests for the read-only dBase III reader (:mod:`disciples_play.dbf`)."""

from __future__ import annotations

import struct

import pytest

from disciples_play.dbf import (
    DBASE3,
    RECORD_PREFIX_LEN,
    column_values,
    field_offsets,
    parse_dbf_header,
    read_dbf,
    summarize_dbf,
)

from .fixtures import build_dbf, write


def test_parse_header_round_trips_field_geometry() -> None:
    fields = [("CATEGORY", "N", 2), ("CHANCE", "N", 3), ("NAME_TXT", "C", 10)]
    data = build_dbf(fields, records=[b" " * 15, b" " * 15])
    header = parse_dbf_header(data)

    assert header.version == DBASE3
    assert header.records == 2
    assert header.record_len == 16  # 1-byte deletion flag + 15 bytes of fields
    assert header.field_count == 3
    assert [f.name for f in header.fields] == ["CATEGORY", "CHANCE", "NAME_TXT"]
    assert [f.type for f in header.fields] == ["N", "N", "C"]
    assert [f.length for f in header.fields] == [2, 3, 10]
    assert header.arithmetic_ok
    assert header.closes_file(len(data))


def test_header_arithmetic_closes_on_disk(tmp_path) -> None:
    fields = [("BUILD_ID", "C", 10), ("LEVEL", "N", 1), ("COST", "C", 29)]
    rec = b" " * 40
    path = write(tmp_path / "Globals" / "GBUILD.DBF", build_dbf(fields, records=[rec] * 5))
    summary = summarize_dbf(path)

    assert summary["version"] == DBASE3
    assert summary["records"] == 5
    assert summary["record_len"] == 41  # 1 + 10 + 1 + 29
    assert summary["live_records"] == 5
    assert summary["deleted_records"] == 0
    assert summary["arithmetic_ok"] is True
    assert summary["field_count"] == 3


def test_read_dbf_returns_header_and_record_bytes(tmp_path) -> None:
    fields = [("ID", "C", 4), ("N", "N", 2)]
    rec0 = b"aaaa" + b"12"
    rec1 = b"bbbb" + b"34"
    path = write(tmp_path / "T.dbf", build_dbf(fields, records=[rec0, rec1]))

    header, records = read_dbf(path)
    assert header.records == 2
    # Each record is the 1-byte deletion flag (0x20 space) + 6 field bytes.
    assert len(records) == 2 * 7
    assert records[:7] == b" " + rec0
    assert records[7:] == b" " + rec1


def test_field_offsets_start_after_deletion_flag() -> None:
    fields = [("UNIT_ID", "C", 10), ("RACE_ID", "C", 10), ("NAME_TXT", "C", 10)]
    data = build_dbf(fields, records=[b" " * 30])
    header = parse_dbf_header(data)

    offsets = field_offsets(header)
    # The first field starts at 1, not 0: byte 0 of a record is the flag.
    assert offsets["UNIT_ID"] == (RECORD_PREFIX_LEN, 10)
    assert offsets["RACE_ID"] == (RECORD_PREFIX_LEN + 10, 10)
    assert offsets["NAME_TXT"] == (RECORD_PREFIX_LEN + 20, 10)


def test_column_values_reads_after_the_flag_and_skips_deleted(tmp_path) -> None:
    fields = [("ID", "C", 4)]
    # Three records: live "aaaa", deleted "bbbb", live "cccc".
    path = write(
        tmp_path / "T.dbf",
        build_dbf(fields, records=[b"aaaa", b"bbbb", b"cccc"], deleted=(1,)),
    )
    header, records = read_dbf(path)

    assert column_values(header, records, "ID") == ["aaaa", "cccc"]
    # With skip_deleted disabled the deleted row is included.
    assert column_values(header, records, "ID", skip_deleted=False) == ["aaaa", "bbbb", "cccc"]


def test_summarize_dbf_reports_deleted_count(tmp_path) -> None:
    fields = [("ID", "C", 4)]
    path = write(
        tmp_path / "T.dbf",
        build_dbf(fields, records=[b"aaaa", b"bbbb", b"cccc"], deleted=(0, 2)),
    )
    summary = summarize_dbf(path)
    assert summary["records"] == 3
    assert summary["live_records"] == 1
    assert summary["deleted_records"] == 2


def test_read_dbf_rejects_short_buffer_with_value_error(tmp_path) -> None:
    # A 3-byte file and an empty file must raise ValueError, never struct.error.
    for size in (0, 3):
        path = write(tmp_path / f"short{size}.dbf", b"\x00" * size)
        with pytest.raises(ValueError):
            read_dbf(path)


def test_summarize_dbf_reports_error_for_non_dbase_file(tmp_path) -> None:
    path = write(tmp_path / "BOGUS.DBF", b"this is plain text, not a dBase file\n" * 4)
    summary = summarize_dbf(path)
    assert "error" in summary
    assert summary["path"] == "BOGUS.DBF"


def test_column_values_returns_empty_for_missing_field(tmp_path) -> None:
    fields = [("ID", "C", 4)]
    path = write(tmp_path / "T.dbf", build_dbf(fields, records=[b"aaaa"]))
    header, records = read_dbf(path)
    assert column_values(header, records, "NOPE") == []


def test_arithmetic_mismatch_is_reported(tmp_path) -> None:
    fields = [("ID", "C", 4)]
    good = build_dbf(fields, records=[b"aaaa"])
    # Corrupt the record count: claim 2 records while only 1 is present.
    corrupted = bytearray(good)
    struct.pack_into("<I", corrupted, 4, 2)
    path = write(tmp_path / "bad.dbf", bytes(corrupted))

    summary = summarize_dbf(path)
    assert summary["records"] == 2
    assert summary["arithmetic_ok"] is False


def test_parse_rejects_truncated_header() -> None:
    with pytest.raises(ValueError):
        parse_dbf_header(b"\x03\x00\x00\x00")


def test_parse_rejects_bad_terminator() -> None:
    fields = [("ID", "C", 4)]
    data = bytearray(build_dbf(fields, records=[b"aaaa"]))
    # Flip the field-list terminator byte.
    data[32 + 32] = 0x00
    with pytest.raises(ValueError):
        parse_dbf_header(bytes(data))
