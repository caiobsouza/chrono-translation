import subprocess
from pathlib import Path

import pytest

from cc_extrator import chronotools


@pytest.fixture
def outputs():
    return []


@pytest.fixture
def calls(monkeypatch, outputs):
    recorded = []

    def fake_run(command, **kwargs):
        recorded.append(command)
        if command[-1] == "ctinsert" and not (outputs and b"ERROR" in outputs[0]):
            mount = next(arg for arg in command if arg.endswith(":/work"))
            (Path(mount.removesuffix(":/work")) / "ctpatch-nohdr.ips").write_text("patch")
        stdout = kwargs.get("stdout")
        if hasattr(stdout, "write"):
            stdout.write(b"config")
        return subprocess.CompletedProcess(command, 0, stdout=outputs.pop(0) if outputs else b"")

    monkeypatch.setattr(chronotools.subprocess, "run", fake_run)
    return recorded


@pytest.fixture
def rom(tmp_path: Path) -> Path:
    path = tmp_path / "rom.sfc"
    path.write_bytes(b"rom")
    return path


def test_extract_copies_rom_and_default_config(calls, rom, tmp_path):
    work = tmp_path / "work"
    (work).mkdir()
    (work / "ctdump.out").write_text("dump")

    script = chronotools.extract(rom, work)

    assert (work / "chrono.smc").read_bytes() == b"rom"
    assert (work / "ct.cfg").read_bytes() == b"config"
    assert script.read_text() == "dump"
    assert calls[-1][-2:] == ["ctdump", "chrono.smc"]


def test_extract_keeps_existing_script_and_config(calls, rom, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "ct.txt").write_text("translated")
    (work / "ct.cfg").write_text("custom")
    (work / "ctdump.out").write_text("dump")

    chronotools.extract(rom, work)

    assert (work / "ct.txt").read_text() == "translated"
    assert (work / "ct.cfg").read_text() == "custom"


def test_extract_fails_when_rom_is_missing(calls, tmp_path):
    with pytest.raises(FileNotFoundError, match="ROM not found"):
        chronotools.extract(tmp_path / "missing.sfc", tmp_path / "work")


def test_insert_requires_previous_step(calls, tmp_path):
    with pytest.raises(FileNotFoundError, match="ct.txt"):
        chronotools.insert(tmp_path)


def test_insert_runs_ctinsert_then_fixes_checksum(calls, tmp_path):
    for name in ("chrono.smc", "ct.txt", "ct.cfg"):
        (tmp_path / name).write_text("x")

    patch = chronotools.insert(tmp_path)

    assert patch == tmp_path / "ctpatch.ips"
    assert calls[-2][-1] == "ctinsert"
    assert calls[-1][-4:] == ["fixchecksum", "ctpatch-nohdr.ips", "chrono.smc", "ctpatch.ips"]
    assert f"{tmp_path.resolve()}:/work" in calls[-1]


def test_apply_patch_copies_result_to_out(calls, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "chrono.smc").write_text("x")
    (work / "ctpatch.ips").write_text("x")
    (work / "patched.smc").write_text("patched")
    out = tmp_path / "out" / "result.sfc"

    chronotools.apply_patch(work, out)

    assert out.read_text() == "patched"
    assert calls[-1][-4:] == ["unmakeips", "ctpatch.ips", "chrono.smc", "patched.smc"]


def test_extract_saves_the_original_script_once(calls, rom, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "ctdump.out").write_text("dump")

    chronotools.extract(rom, work)
    (work / "ct.txt").write_text("translated")
    (work / "ctdump.out").write_text("second dump")
    chronotools.extract(rom, work)

    assert (work / "ct.en.txt").read_text() == "dump"
    assert (work / "ct.txt").read_text() == "translated"


def _ready(work: Path) -> None:
    for name in ("chrono.smc", "ct.txt", "ct.cfg"):
        (work / name).write_text("x")


def test_insert_fails_when_ctinsert_prints_an_error(calls, outputs, tmp_path):
    _ready(tmp_path)
    outputs.append(b"Loading dialog...\nError: Too long text\nCreating ctpatch-nohdr.ips\n")

    with pytest.raises(chronotools.ChronotoolsError, match="Too long text"):
        chronotools.insert(tmp_path)

    assert not any("fixchecksum" in call for call in calls)


def test_insert_removes_patches_left_by_ctinsert_after_an_error(calls, outputs, tmp_path):
    _ready(tmp_path)
    (tmp_path / "ctpatch-nohdr.ips").write_text("old")
    (tmp_path / "ctpatch-hdr.ips").write_text("old")
    (tmp_path / "ctpatch.ips").write_text("old")
    outputs.append(b"ERROR: Organization to page 18 failed\n")

    with pytest.raises(chronotools.ChronotoolsError):
        chronotools.insert(tmp_path)

    assert not list(tmp_path.glob("ctpatch*.ips"))


def test_insert_ignores_an_error_word_inside_a_normal_line(calls, outputs, tmp_path):
    _ready(tmp_path)
    outputs.append(b"> Saved: 100 bytes\nnothing wrong, no errors here\n")

    assert chronotools.insert(tmp_path) == tmp_path / "ctpatch.ips"


def test_insert_fails_clearly_when_ctinsert_creates_no_patch(calls, tmp_path, monkeypatch):
    _ready(tmp_path)
    monkeypatch.setattr(chronotools.subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=b""))

    with pytest.raises(chronotools.ChronotoolsError, match="without creating"):
        chronotools.insert(tmp_path)
