"""Tests for the ``data`` report builder (:mod:`disciples_play.data`)."""

from __future__ import annotations

import json

import pytest

from disciples_play.__main__ import main
from disciples_play.data import build_report

from .fixtures import build_dbf, build_mqdb, write


def _synthetic_tree(tmp_path) -> str:
    """Build a tiny synthetic install: DBFs, one DBI, one DLG, one WAV."""

    fields = [("ID", "C", 4), ("VAL", "N", 2)]
    write(tmp_path / "Globals" / "GTEST.DBF", build_dbf(fields, records=[b"a" * 6]))

    # Tglobal + a referencing table, so the cross-reference report has data.
    write(
        tmp_path / "Globals" / "Tglobal.dbf",
        build_dbf(
            [("TXT_ID", "C", 9), ("ENGLISH", "C", 10)],
            records=[b"x000tg100" + b" " * 10],
        ),
    )
    write(
        tmp_path / "Globals" / "GUNITS.DBF",
        build_dbf(
            [("UNIT_ID", "C", 9), ("NAME_TXT", "C", 10), ("RACE_ID", "C", 10)],
            records=[b"g000uu000" + b"x000tg100 " + b"1g000rr000"],
        ),
    )
    write(
        tmp_path / "Globals" / "GRACE.DBF",
        build_dbf([("RACE_ID", "C", 9)], records=[b"g000rr000"]),
    )

    chunks = [(3, b"ARMY01C\x00\x00\x00\x00\x00\x00\x00\x00"), (4, b"ARMY01D\x00" * 4)]
    write(tmp_path / "Imgs1" / "TEST.DBI", build_mqdb(chunks))

    write(
        tmp_path / "Interf" / "TEST.dlg",
        b"DIALOG\tDLG_TEST,0,0,640,480,1,BG\r\nBEGIN\r\n"
        b"\tBUTTON\tBTN_OK,10,10,20,20,,,,,0\r\nEND\r\n",
    )

    write(
        tmp_path / "Music" / "TEST.WAV",
        b"RIFF" + b"\x00" * 4 + b"WAVE" + b"fmt " + b"\x00" * 4 + b"\x00" * 16,
    )
    return str(tmp_path)


def test_build_report_inventory_counts(tmp_path) -> None:
    game_dir = _synthetic_tree(tmp_path)
    report = build_report(game_dir)

    inv = report["inventory"]
    assert inv["total_files"] == 7
    assert inv["by_extension"][".dbf"] == 4
    assert inv["by_extension"][".dbi"] == 1
    assert inv["by_extension"][".dlg"] == 1
    assert inv["by_extension"][".wav"] == 1
    assert inv["by_directory"]["Globals"] == 4
    assert inv["by_directory"]["Imgs1"] == 1
    assert inv["by_directory"]["Interf"] == 1
    assert inv["by_directory"]["Music"] == 1


def test_build_report_dbf_summary(tmp_path) -> None:
    report = build_report(_synthetic_tree(tmp_path))
    assert len(report["dbf"]) == 4
    by_path = {d["path"]: d for d in report["dbf"]}
    d = by_path["GTEST.DBF"]
    assert d["arithmetic_ok"] is True
    assert [f["name"] for f in d["fields"]] == ["ID", "VAL"]


def test_build_report_cross_references(tmp_path) -> None:
    report = build_report(_synthetic_tree(tmp_path))
    xref = report["cross_references"]
    assert xref["text_id_count"] == 1
    name_link = next(link for link in xref["text_links"] if link["field"] == "NAME_TXT")
    # GUNITS.NAME_TXT == "x000tg100" resolves to Tglobal's single TXT_ID.
    assert name_link["resolved"] == 1
    assert name_link["nonempty"] == 1
    # GUNITS.RACE_ID == "1g000rr000" -> "g000rr000" in GRACE.
    assert xref["race_link"]["resolved"] == 1
    assert xref["race_link"]["nonempty"] == 1


def test_build_report_mqdb_vote(tmp_path) -> None:
    report = build_report(_synthetic_tree(tmp_path))
    assert len(report["mqdb"]) == 1
    m = report["mqdb"][0]
    assert m["is_mqdb"] is True
    assert m["winner"]["start_offset"] == 28
    assert m["winner"]["tiles_exactly"] is True


def test_build_report_dlg_digest(tmp_path) -> None:
    report = build_report(_synthetic_tree(tmp_path))
    assert len(report["dlg"]) == 1
    d = report["dlg"][0]
    assert d["dialog_blocks"] == 1
    assert d["element_types"] == {"BUTTON": 1}


def test_build_report_wav_digest(tmp_path) -> None:
    report = build_report(_synthetic_tree(tmp_path))
    assert len(report["wav"]) == 1
    assert report["wav"][0]["magic"] == "RIFF"


def test_report_is_json_serialisable(tmp_path) -> None:
    report = build_report(_synthetic_tree(tmp_path))
    text = json.dumps(report)
    assert "GTEST.DBF" in text


def test_data_subcommand_emits_json(tmp_path) -> None:
    game_dir = _synthetic_tree(tmp_path)
    rc = main(["data", "--game-dir", game_dir, "--json"])
    assert rc == 0


def test_data_subcommand_missing_dir_returns_two(tmp_path) -> None:
    rc = main(["data", "--game-dir", str(tmp_path / "does-not-exist")])
    assert rc == 2


def test_build_report_rejects_non_directory(tmp_path) -> None:
    not_a_dir = tmp_path / "nope"
    not_a_dir.write_text("hi")
    with pytest.raises(NotADirectoryError):
        build_report(str(not_a_dir))
