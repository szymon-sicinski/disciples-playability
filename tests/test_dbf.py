"""Tests for the read-only dBase III reader (:mod:`disciples_play.dbf`)."""

from __future__ import annotations

import struct

import pytest

from disciples_play.dbf import DBASE3, parse_dbf_header, read_dbf, summarize_dbf

from .fixtures import build_dbf, write


def test_parse_header_round_trips_field_geometry() -> None:
    fields = [("CATEGORY", "N", 2), ("CHANCE", "N", 3), ("NAME_TXT", "C", 10)]
    data = build_dbf(fields, records=[b" " * 15, b" " * 15])
    header = parse_dbf_header(data)

    assert header.version == DBASE3
    assert header.records == 2
    assert header.record_len == 15
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
    assert summary["record_len"] == 40
    assert summary["arithmetic_ok"] is True
    assert summary["field_count"] == 3


def test_read_dbf_returns_header_and_record_bytes(tmp_path) -> None:
    fields = [("ID", "C", 4), ("N", "N", 2)]
    rec0 = b"aaaa" + b"12"
    rec1 = b"bbbb" + b"34"
    path = write(tmp_path / "T.dbf", build_dbf(fields, records=[rec0, rec1]))

    header, records = read_dbf(path)
    assert header.records == 2
    assert len(records) == 2 * 6
    assert records[:6] == rec0
    assert records[6:] == rec1


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
