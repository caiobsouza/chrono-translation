"""Minimal reader and writer for the paletted, uncompressed TARGA files Chronotools uses.

The rows are kept top down in memory. The header and palette are kept as they were
read so the file can be written back byte for byte apart from the pixels.
"""

import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Image:
    width: int
    height: int
    rows: list[list[int]]
    header: bytes
    bottom_left_origin: bool

    def save(self, path: Path) -> None:
        rows = list(reversed(self.rows)) if self.bottom_left_origin else self.rows
        path.write_bytes(self.header + b"".join(bytes(row) for row in rows))


def read(path: Path) -> Image:
    data = path.read_bytes()
    id_length, color_map_type, image_type = data[0], data[1], data[2]
    if color_map_type != 1 or image_type != 1:
        raise ValueError(f"{path} is not an uncompressed paletted TARGA file")
    _, palette_length, palette_bits = struct.unpack("<HHB", data[3:8])
    width, height = struct.unpack("<HH", data[12:16])
    if data[16] != 8:
        raise ValueError(f"{path} must have 8 bits per pixel")
    descriptor = data[17]
    start = 18 + id_length + palette_length * (palette_bits // 8)
    rows = [list(data[start + y * width:start + (y + 1) * width]) for y in range(height)]
    bottom_left = not descriptor & 0x20
    if bottom_left:
        rows.reverse()
    return Image(width, height, rows, data[:start], bottom_left)
