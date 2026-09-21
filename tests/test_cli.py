from pathlib import Path

import pytest

from cc_extrator import cli


def test_extract_uses_defaults(monkeypatch):
    received = {}
    monkeypatch.setattr(cli.chronotools, "extract", lambda rom, work: received.update(rom=rom, work=work) or work / "ct.txt")

    cli.main(["extract"])

    assert received == {"rom": Path("data/ChronoTrigger.sfc"), "work": Path("work")}


def test_apply_accepts_custom_out(monkeypatch):
    received = {}
    monkeypatch.setattr(cli.chronotools, "apply_patch", lambda work, out: received.update(out=out) or out)

    cli.main(["apply", "--out", "custom.sfc"])

    assert received["out"] == Path("custom.sfc")


ORIGINAL = "*r;item types\n$t1:WEAPON\n*z;dialog (x)\n$d1:CYRUS: Yes.\n"


def _work(tmp_path, translated):
    (tmp_path / "ct.en.txt").write_bytes(ORIGINAL.encode("iso-8859-15"))
    (tmp_path / "ct.txt").write_bytes(translated.encode("iso-8859-15"))
    return str(tmp_path)


def test_check_passes_on_a_valid_script(tmp_path, capsys):
    work = _work(tmp_path, ORIGINAL.replace("WEAPON", "ARMA"))

    cli.main(["check", "--work", work, "--glossary", str(tmp_path / "none.tsv")])

    assert "0 errors" in capsys.readouterr().out


def test_check_exits_with_an_error_status_on_problems(tmp_path, capsys):
    work = _work(tmp_path, ORIGINAL.replace("WEAPON", "ARMAMENTO"))

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["check", "--work", work, "--glossary", str(tmp_path / "none.tsv")])

    assert exit_info.value.code == 1
    assert "too-long" in capsys.readouterr().out


def test_check_explains_when_the_original_script_is_missing(tmp_path):
    (tmp_path / "ct.txt").write_text(ORIGINAL)

    with pytest.raises(SystemExit, match="Run extract first"):
        cli.main(["check", "--work", str(tmp_path)])


def test_insert_does_not_run_when_the_check_fails(tmp_path, monkeypatch):
    work = _work(tmp_path, ORIGINAL.replace("WEAPON", "ARMAMENTO"))
    monkeypatch.setattr(cli.chronotools, "insert", lambda work_dir: pytest.fail("insert must not run"))

    with pytest.raises(SystemExit):
        cli.main(["insert", "--work", work, "--glossary", str(tmp_path / "none.tsv")])


def test_insert_runs_after_a_clean_check(tmp_path, monkeypatch, capsys):
    work = _work(tmp_path, ORIGINAL.replace("WEAPON", "ARMA"))
    monkeypatch.setattr(cli.chronotools, "insert", lambda work_dir: work_dir / "ctpatch.ips")

    cli.main(["insert", "--work", work, "--glossary", str(tmp_path / "none.tsv")])

    assert "ctpatch.ips" in capsys.readouterr().out


def test_skip_check_goes_straight_to_insert(tmp_path, monkeypatch, capsys):
    work = _work(tmp_path, ORIGINAL.replace("WEAPON", "ARMAMENTO"))
    monkeypatch.setattr(cli.chronotools, "insert", lambda work_dir: work_dir / "ctpatch.ips")

    cli.main(["insert", "--work", work, "--skip-check"])

    assert "ctpatch.ips" in capsys.readouterr().out


def test_insert_reports_a_tool_error_without_a_traceback(tmp_path, monkeypatch):
    work = _work(tmp_path, ORIGINAL)

    def fail(work_dir):
        raise cli.chronotools.ChronotoolsError("ctinsert reported 2 errors")

    monkeypatch.setattr(cli.chronotools, "insert", fail)

    with pytest.raises(SystemExit, match="ctinsert reported 2 errors"):
        cli.main(["insert", "--work", work, "--glossary", str(tmp_path / "none.tsv")])
