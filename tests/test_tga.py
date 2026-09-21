import struct
from pathlib import Path

import pytest

from cc_extrator import tga


def make_file(path: Path, rows: list[list[int]], bottom_left: bool = True) -> None:
    height, width = len(rows), len(rows[0])
    palette = bytes(range(18))
    header = struct.pack("<BBBHHBHHHHBB", 0, 1, 1, 0, 6, 24, 0, 0, width, height, 8, 0 if bottom_left else 0x20)
    stored = list(reversed(rows)) if bottom_left else rows
    path.write_bytes(header + palette + b"".join(bytes(row) for row in stored))


def test_rows_are_read_top_down_for_a_bottom_left_file(tmp_path: Path):
    make_file(tmp_path / "a.tga", [[1, 2], [3, 4]])

    image = tga.read(tmp_path / "a.tga")

    assert image.rows == [[1, 2], [3, 4]]
    assert (image.width, image.height) == (2, 2)


def test_top_left_files_are_left_as_they_are(tmp_path: Path):
    make_file(tmp_path / "a.tga", [[1, 2], [3, 4]], bottom_left=False)

    assert tga.read(tmp_path / "a.tga").rows == [[1, 2], [3, 4]]


def test_saving_an_unchanged_image_reproduces_the_file(tmp_path: Path):
    make_file(tmp_path / "a.tga", [[1, 2, 3], [4, 5, 0]])
    original = (tmp_path / "a.tga").read_bytes()

    tga.read(tmp_path / "a.tga").save(tmp_path / "b.tga")

    assert (tmp_path / "b.tga").read_bytes() == original


def test_changed_pixels_are_written_and_the_palette_is_kept(tmp_path: Path):
    make_file(tmp_path / "a.tga", [[1, 2], [3, 4]])
    image = tga.read(tmp_path / "a.tga")

    image.rows[0][0] = 9
    image.save(tmp_path / "b.tga")

    assert tga.read(tmp_path / "b.tga").rows == [[9, 2], [3, 4]]
    assert (tmp_path / "b.tga").read_bytes()[18:36] == bytes(range(18))


def test_files_that_are_not_paletted_are_rejected(tmp_path: Path):
    (tmp_path / "a.tga").write_bytes(bytes([0, 0, 2]) + bytes(20))

    with pytest.raises(ValueError, match="uncompressed paletted"):
        tga.read(tmp_path / "a.tga")
