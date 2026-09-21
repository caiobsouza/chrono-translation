import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

IMAGE = "cc-extrator-chronotools"
DOCKER_DIR = Path(__file__).parent / "docker"
DEFAULT_CONFIG = "/opt/chronotools/ct.cfg"

ROM_NAME = "chrono.smc"
CONFIG_NAME = "ct.cfg"
DUMP_NAME = "ctdump.out"
SCRIPT_NAME = "ct.txt"
ORIGINAL_SCRIPT_NAME = "ct.en.txt"
RAW_PATCH_NAME = "ctpatch-nohdr.ips"
HEADER_PATCH_NAME = "ctpatch-hdr.ips"
PATCH_NAME = "ctpatch.ips"
PATCHED_ROM_NAME = "patched.smc"

_ERROR_LINE = re.compile(r"^\s*(ERROR|Error)\b")
_SHOWN_LINE = re.compile(r"^(> |Free space|Creating|Warning)")


class ChronotoolsError(RuntimeError):
    pass


def build_image() -> None:
    subprocess.run(["docker", "build", "-t", IMAGE, str(DOCKER_DIR)], check=True)


def extract(rom: Path, work_dir: Path) -> Path:
    """Dump the script and fonts. An existing ct.txt is never overwritten."""
    _prepare(rom, work_dir)
    _run_in_container(work_dir, "ctdump", ROM_NAME)
    script = work_dir / SCRIPT_NAME
    if not script.exists():
        shutil.copyfile(work_dir / DUMP_NAME, script)
    original = work_dir / ORIGINAL_SCRIPT_NAME
    if not original.exists():
        shutil.copyfile(work_dir / DUMP_NAME, original)
    return script


def insert(work_dir: Path) -> Path:
    """Compile ct.txt into an IPS patch that also fixes the ROM checksum.

    ctinsert writes a patch even after it reports errors, so any error line fails the
    step and a patch from an earlier run is removed first so it cannot be applied by mistake.
    """
    _require(work_dir, ROM_NAME, SCRIPT_NAME, CONFIG_NAME)
    _remove_patches(work_dir)
    try:
        _run_in_container(work_dir, "ctinsert", fail_on_error=True)
    except ChronotoolsError:
        _remove_patches(work_dir)
        raise
    if not (work_dir / RAW_PATCH_NAME).is_file():
        raise ChronotoolsError(f"ctinsert finished without creating {RAW_PATCH_NAME}, run insert again")
    _run_in_container(work_dir, "fixchecksum", RAW_PATCH_NAME, ROM_NAME, PATCH_NAME)
    return work_dir / PATCH_NAME


def apply_patch(work_dir: Path, out: Path) -> Path:
    """Apply the generated patch to the ROM and write the result to out."""
    _require(work_dir, ROM_NAME, PATCH_NAME)
    _run_in_container(work_dir, "unmakeips", PATCH_NAME, ROM_NAME, PATCHED_ROM_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(work_dir / PATCHED_ROM_NAME, out)
    return out


def _remove_patches(work_dir: Path) -> None:
    for name in (RAW_PATCH_NAME, PATCH_NAME, HEADER_PATCH_NAME):
        (work_dir / name).unlink(missing_ok=True)


def _prepare(rom: Path, work_dir: Path) -> None:
    if not rom.is_file():
        raise FileNotFoundError(f"ROM not found: {rom}")
    work_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rom, work_dir / ROM_NAME)
    config = work_dir / CONFIG_NAME
    if not config.exists():
        with config.open("wb") as file:
            subprocess.run(["docker", "run", "--rm", IMAGE, "cat", DEFAULT_CONFIG], stdout=file, check=True)


def _require(work_dir: Path, *names: str) -> None:
    missing = [name for name in names if not (work_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing in {work_dir}: {', '.join(missing)}. Run the previous step first.")


def _run_in_container(work_dir: Path, *command: str, fail_on_error: bool = False) -> None:
    docker = [
        "docker", "run", "--rm",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{work_dir.resolve()}:/work",
        IMAGE, *command,
    ]
    if not fail_on_error:
        subprocess.run(docker, check=True)
        return
    result = subprocess.run(docker, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines = re.split(r"[\r\n]+", (result.stdout or b"").decode("latin-1"))
    errors = [line.strip() for line in lines if _ERROR_LINE.match(line)]
    for line in lines:
        if _SHOWN_LINE.match(line) or _ERROR_LINE.match(line):
            print(line)
    if errors or result.returncode != 0:
        raise ChronotoolsError(f"{command[0]} reported {len(errors)} errors, first: {errors[0] if errors else 'exit code ' + str(result.returncode)}")
