"""Tests for the ``MQDB`` chunk/tag scanner (:mod:`disciples_play.mqdb`)."""

from __future__ import annotations

from disciples_play.mqdb import scan_mqdb

from .fixtures import build_mqdb, write


def _payload(name: bytes, size: int) -> bytes:
    return name + b"\x00" * (size - len(name))


def _hypotheses(report: dict) -> dict:
    return {(h["start_offset"], h["endian"], h["size_offset"]): h for h in report["hypotheses"]}


def test_scans_a_tiling_container(tmp_path) -> None:
    chunks = [
        (3, _payload(b"ARMY01C", 32)),
        (4, _payload(b"ARMY01D", 40)),
        (5, _payload(b"ARMY01H", 36)),
    ]
    path = write(tmp_path / "T.dbi", build_mqdb(chunks))

    report = scan_mqdb(path)
    assert report["is_mqdb"] is True
    assert report["magic"] == "MQDB"
    assert report["version_le"] == 9

    winner = report["winner"]
    assert winner["start_offset"] == 28
    assert winner["endian"] == "little"
    assert winner["size_offset"] == 16
    assert winner["chunks"] == 3
    assert winner["in_range"] is True
    assert winner["tiles_exactly"] is True
    assert winner["offsets_non_decreasing"] is True

    names = [c["name"] for c in report["chunks"]]
    assert names == ["ARMY01C", "ARMY01D", "ARMY01H"]


def test_big_endian_hypothesis_loses(tmp_path) -> None:
    chunks = [(1, _payload(b"ARMY01C", 32))]
    path = write(tmp_path / "T.dbi", build_mqdb(chunks))

    report = scan_mqdb(path)
    by_key = _hypotheses(report)

    little = by_key[(28, "little", 16)]
    big = by_key[(28, "big", 16)]
    assert little["chunks"] == 1
    assert little["tiles_exactly"] is True
    # Big-endian reads the size field as a huge value and overruns immediately.
    assert big["chunks"] == 0
    assert big["in_range"] is False

    assert report["winner"]["endian"] == "little"


def test_wrong_start_offset_scores_zero_chunks(tmp_path) -> None:
    chunks = [(1, _payload(b"ARMY01C", 32))]
    path = write(tmp_path / "T.dbi", build_mqdb(chunks))

    report = scan_mqdb(path)
    by_key = _hypotheses(report)

    # At offset 24 the bytes are the 0x18 header field, not a "MQRC" tag.
    assert by_key[(24, "little", 16)]["chunks"] == 0
    assert by_key[(24, "big", 16)]["chunks"] == 0
    assert report["winner"]["start_offset"] == 28


def test_size_field_at_16_wins_when_second_field_differs(tmp_path) -> None:
    # A chunk whose +0x0C field is 0 while the true size lives at +0x10, as in
    # the real ISO.DBI's first chunk.  The scanner must prefer size@+16.
    chunks = [
        (956, _payload(b"BTILE000", 14928), 0),
        (2, _payload(b"", 1024)),
    ]
    path = write(tmp_path / "T.dbi", build_mqdb(chunks))

    report = scan_mqdb(path)
    by_key = _hypotheses(report)

    assert by_key[(28, "little", 16)]["tiles_exactly"] is True
    assert by_key[(28, "little", 16)]["chunks"] == 2
    # With size read from +0x0C, the first chunk has size 0 and the walk stalls.
    assert by_key[(28, "little", 12)]["chunks"] == 1
    assert by_key[(28, "little", 12)]["tiles_exactly"] is False

    assert report["winner"]["size_offset"] == 16


def test_non_mqdb_file_is_flagged(tmp_path) -> None:
    path = write(tmp_path / "not.dbi", b"NOTA" + b"\x00" * 64)
    report = scan_mqdb(path)
    assert report["is_mqdb"] is False
    assert report["magic"] == "NOTA"


def test_reports_header_hint_field(tmp_path) -> None:
    chunks = [(1, _payload(b"ARMY01C", 32))]
    path = write(tmp_path / "T.dbi", build_mqdb(chunks, header_field_0x18=1234))
    report = scan_mqdb(path)
    assert report["header_field_0x18"] == 1234
