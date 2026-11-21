"""Tests for the ``data`` report builder (:mod:`disciples_play.data`)."""

from __future__ import annotations

import json

import pytest

from disciples_play.__main__ import main
from disciples_play.data import build_report

from .fixtures import build_dbf, build_mqdb, write


def _synthetic_tree(tmp_path) -> str:
    """Build a tiny synthetic install: DBFs, one DBI, one DLG, one WAV."""

    write(
        tmp_path / "Globals" / "GTEST.DBF",
        build_dbf([("ID", "C", 4), ("VAL", "N", 2)], records=[b"a" * 6]),
    )

    # Tglobal + a referencing table, so the cross-reference report has data.
    # IDs are 10 characters (g000uu0000 style); there is no leading count or
    # marker digit on a reference -- that "convention" was an artifact of the
    # record-deletion-flag off-by-one.
    write(
        tmp_path / "Globals" / "Tglobal.dbf",
        build_dbf(
            [("TXT_ID", "C", 10), ("ENGLISH", "C", 10)],
            records=[b"x000tg1000" + b" " * 10],
        ),
    )
    write(
        tmp_path / "Globals" / "GUNITS.DBF",
        build_dbf(
            [("UNIT_ID", "C", 10), ("NAME_TXT", "C", 10), ("RACE_ID", "C", 10)],
            records=[b"g000uu0000" + b"x000tg1000" + b"g000rr0000"],
        ),
    )
    write(
        tmp_path / "Globals" / "GRACE.DBF",
        build_dbf([("RACE_ID", "C", 10)], records=[b"g000rr0000"]),
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
    # GUNITS.NAME_TXT == "x000tg1000" resolves to Tglobal's single TXT_ID.
    assert name_link["field_missing"] is False
    assert name_link["resolved"] == 1
    assert name_link["nonempty"] == 1
    # GUNITS.RACE_ID == "g000rr0000" resolves to GRACE's "g000rr0000".
    assert xref["race_link"]["field_missing"] is False
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


def test_build_report_rejects_non_install_dir(tmp_path) -> None:
    # A directory with neither Globals/ nor Exe/ is not a Disciples install.
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(NotADirectoryError):
        build_report(str(empty))


def test_dbf_reports_no_duplicate_paths(tmp_path) -> None:
    # Mixed-case .DBF/.dbf names must each be reported exactly once.  The old
    # "*.DBF" + "*.dbf" double-glob reports every table twice on a
    # case-insensitive filesystem (Windows); this test pins the invariant.
    for name in ("A.DBF", "B.dbf", "C.DBF"):
        write(tmp_path / "Globals" / name, build_dbf([("ID", "C", 4)], records=[b"aaaa"]))
    report = build_report(str(tmp_path))
    paths = [d["path"] for d in report["dbf"]]
    assert len(paths) == 3
    assert len(set(paths)) == 3


def test_build_report_survives_non_dbase_file(tmp_path) -> None:
    # A text file and an empty file named .DBF must be reported as per-file
    # errors, not abort the whole run.
    write(tmp_path / "Globals" / "GOOD.DBF", build_dbf([("ID", "C", 4)], records=[b"aaaa"]))
    write(tmp_path / "Globals" / "BOGUS.DBF", b"this is not a dBase file")
    write(tmp_path / "Globals" / "EMPTY.DBF", b"")
    report = build_report(str(tmp_path))
    ok = [d for d in report["dbf"] if "error" not in d]
    errors = [d for d in report["dbf"] if "error" in d]
    assert len(ok) == 1
    assert {d["path"] for d in errors} == {"BOGUS.DBF", "EMPTY.DBF"}


def test_data_subcommand_returns_nonzero_on_bad_dbf(tmp_path) -> None:
    write(tmp_path / "Globals" / "GOOD.DBF", build_dbf([("ID", "C", 4)], records=[b"aaaa"]))
    write(tmp_path / "Globals" / "BOGUS.DBF", b"not a dbase file")
    rc = main(["data", "--game-dir", str(tmp_path), "--json"])
    assert rc == 1


def test_data_subcommand_non_install_dir_returns_two(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    rc = main(["data", "--game-dir", str(empty)])
    assert rc == 2


def test_cross_reference_reports_missing_field(tmp_path) -> None:
    # A GUNITS.DBF without a NAME_TXT column must be reported as "field
    # missing", not silently rendered as 0/0 resolving references.
    write(
        tmp_path / "Globals" / "Tglobal.dbf",
        build_dbf([("TXT_ID", "C", 10)], records=[b"x000tg1000"]),
    )
    write(
        tmp_path / "Globals" / "GUNITS.DBF",
        build_dbf([("UNIT_ID", "C", 10)], records=[b"g000uu0000"]),
    )
    report = build_report(str(tmp_path))
    xref = report["cross_references"]
    name_link = next(link for link in xref["text_links"] if link["field"] == "NAME_TXT")
    assert name_link["field_missing"] is True
    assert name_link["nonempty"] is None
    assert name_link["resolved"] is None
