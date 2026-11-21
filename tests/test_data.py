"""Tests for the ``data`` report builder (:mod:`disciples_play.data`)."""

from __future__ import annotations

import json
import os
import sys

import pytest

from disciples_play.__main__ import main
from disciples_play.data import build_report, report_error_count

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


def _synthetic_install(tmp_path) -> str:
    """The same tree, plus a stub ``Exe/Disciple.exe`` + ``DISCIPLE.INI``.

    The ``data`` subcommand resolves the install through
    ``launch.resolve_install`` (like the launcher), which keys on
    ``Exe/Disciple.exe``; the CLI-level tests need that stub, while the
    ``build_report``-level tests exercise the data folders directly.
    """

    _synthetic_tree(tmp_path)
    exe_dir = tmp_path / "Exe"
    exe_dir.mkdir(exist_ok=True)
    (exe_dir / "Disciple.exe").write_bytes(b"MZ")
    (exe_dir / "DISCIPLE.INI").write_bytes(b"")
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
    game_dir = _synthetic_install(tmp_path)
    rc = main(["data", "--game-dir", game_dir, "--json"])
    assert rc == 0


def test_data_subcommand_missing_dir_returns_two(tmp_path) -> None:
    rc = main(["data", "--game-dir", str(tmp_path / "does-not-exist")])
    assert rc == 2


def test_data_subcommand_accepts_toplevel_game_dir(tmp_path) -> None:
    # ``disciples-play --game-dir X data`` must resolve the install the same as
    # ``disciples-play data --game-dir X``.  The subparser's own ``--game-dir``
    # (same dest, default None) used to shadow the top-level one, silently
    # dropping a value the caller put *before* ``data``.
    game_dir = _synthetic_install(tmp_path)
    rc = main(["--game-dir", game_dir, "data", "--json"])
    assert rc == 0


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
    _synthetic_install(tmp_path)
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


def test_id_type_report_counts_prefix_type_pairs(tmp_path) -> None:
    # GUNITS.UNIT_ID=g000uu0000, NAME_TXT=x000tg1000, RACE_ID=g000rr0000;
    # GRACE.RACE_ID=g000rr0000; Tglobal.TXT_ID=x000tg1000.  GTEST.DBF's ID is
    # 4 chars, so it does not contribute.
    report = build_report(_synthetic_tree(tmp_path))
    types = {(t["prefix"], t["type"]): t["count"] for t in report["id_types"]["types"]}
    assert types == {("g", "uu"): 1, ("x", "tg"): 2, ("g", "rr"): 2}


def test_data_env_var_install_source(tmp_path, monkeypatch) -> None:
    game_dir = _synthetic_install(tmp_path)
    monkeypatch.setenv("DISCIPLES_GAME_DIR", game_dir)
    assert main(["data", "--json"]) == 0


def test_data_config_file_install_source(tmp_path, monkeypatch) -> None:
    game_dir = _synthetic_install(tmp_path)
    config_dir = tmp_path / "config"
    monkeypatch.delenv("DISCIPLES_GAME_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
    monkeypatch.setenv("APPDATA", str(config_dir))
    (config_dir / "disciples-play").mkdir(parents=True)
    (config_dir / "disciples-play" / "config.ini").write_text(f"game_dir = {game_dir}\n")
    assert main(["data", "--json"]) == 0


def test_data_resolves_parent_dir(tmp_path) -> None:
    # The launcher resolves a copied-retail folder one level down; data must
    # resolve the same way instead of refusing the parent directory.
    inner = tmp_path / "Games" / "Disciples Gold"
    _synthetic_install(inner)
    assert main(["data", "--game-dir", str(tmp_path / "Games"), "--json"]) == 0


def test_data_no_install_specified_returns_two(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DISCIPLES_GAME_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "no-config"))
    assert main(["data", "--json"]) == 2


def test_help_mentions_data_subcommand(capsys) -> None:
    assert main(["--help"]) == 0
    assert "data" in capsys.readouterr().out


def test_build_report_survives_unreadable_dlg(tmp_path, monkeypatch) -> None:
    # A per-file reader that raises must not take the whole report down; the
    # _safe() wrapper turns it into a per-file error dict.
    import disciples_play.data as data_mod

    def boom(path):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(data_mod, "_dlg_report", boom)
    report = build_report(_synthetic_tree(tmp_path))
    assert any("error" in d and "Permission denied" in d["error"] for d in report["dlg"])
    assert report_error_count(report) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="chmod 000 does not block reads on Windows")
def test_build_report_survives_unreadable_mqdb(tmp_path) -> None:
    if os.geteuid() == 0:
        pytest.skip("running as root; chmod 000 does not block reads")
    game_dir = _synthetic_tree(tmp_path)
    dbi = tmp_path / "Imgs1" / "TEST.DBI"
    dbi.chmod(0)
    try:
        report = build_report(game_dir)
    finally:
        dbi.chmod(0o644)
    assert any("error" in m for m in report["mqdb"])
    assert report_error_count(report) == 1


def test_data_returns_nonzero_on_unreadable_non_dbf(tmp_path, monkeypatch) -> None:
    # An unreadable non-DBF file must yield exit 1 (data incomplete), not a
    # traceback -- the hardening covers every reader, not just .DBF.
    import disciples_play.data as data_mod

    def boom(path):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(data_mod, "_smk_report", boom)
    game_dir = _synthetic_install(tmp_path)
    (tmp_path / "Video").mkdir()
    (tmp_path / "Video" / "X.SMK").write_bytes(b"SMK2" + b"\x00" * 12)
    assert main(["data", "--game-dir", game_dir, "--json"]) == 1
