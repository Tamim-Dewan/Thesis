"""Extract the small benchmark sample from heiDATA archive files.

The script uses HTTP range requests, so it does not download a complete
archive. It writes only the OBJ files named by the sample manifest.
"""

from __future__ import annotations

import argparse
import struct
import urllib.request
import zlib
from pathlib import Path


BASE_URL = "https://heidata.uni-heidelberg.de/api/access/datafile/"
ARCHIVES = {
    "pre": (12667, ("b_001_pre.obj", "b_002_pre.obj", "b_003_pre.obj", "b_004_pre.obj", "b_005_pre.obj", "b_006_pre.obj", "b_007_pre.obj", "b_008_pre.obj")),
    "grade3": (12669, ("b_003_post.obj", "b_005_post.obj")),
    "grade4": (12668, ("b_001_post.obj",)),
    "grade5": (12672, ("b_002_post.obj",)),
}


def range_get(url: str, start: int, end: int) -> bytes:
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def archive_entries(url: str) -> dict[str, tuple[int, int, int, int]]:
    request = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        total = int(response.headers["Content-Range"].split("/")[-1])
    tail_start = max(0, total - 3_000_000)
    tail = range_get(url, tail_start, total - 1)
    end_position = tail.rfind(b"PK\x05\x06")
    if end_position >= 0:
        _, _, _, _, count, directory_size, directory_offset, _ = struct.unpack(
            "<4s4H2LH", tail[end_position:end_position + 22]
        )
    else:
        count = directory_size = directory_offset = 0
    if count == 0xFFFF or directory_size == 0xFFFFFFFF or directory_offset == 0xFFFFFFFF:
        zip64_position = tail.rfind(b"PK\x06\x06")
        values = struct.unpack("<4sQ2H2L4Q", tail[zip64_position:zip64_position + 56])
        count, directory_size, directory_offset = values[6], values[8], values[9]

    directory = range_get(url, directory_offset, directory_offset + directory_size - 1)
    entries: dict[str, tuple[int, int, int, int]] = {}
    position = 0
    for _ in range(count):
        if directory[position:position + 4] != b"PK\x01\x02":
            raise RuntimeError(f"invalid central directory at byte {position}")
        values = struct.unpack("<4s6H3L5H2L", directory[position:position + 46])
        filename_size, extra_size, comment_size = values[10], values[11], values[12]
        name = directory[position + 46:position + 46 + filename_size].decode("utf-8")
        entries[name] = (values[8], values[9], values[16], values[4])
        position += 46 + filename_size + extra_size + comment_size
    return entries


def extract_entry(url: str, name: str, entry: tuple[int, int, int, int]) -> bytes:
    compressed_size, uncompressed_size, offset, method = entry
    header = range_get(url, offset, offset + 29)
    _, _, _, _, _, _, _, _, _, filename_size, extra_size = struct.unpack("<4s5H3L2H", header)
    start = offset + 30 + filename_size + extra_size
    payload = range_get(url, start, start + compressed_size - 1)
    data = payload if method == 0 else zlib.decompress(payload, -15)
    if len(data) != uncompressed_size:
        raise RuntimeError(f"size mismatch for {name}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("heidata_benchmark/data/sample/raw"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for archive_name, (file_id, names) in ARCHIVES.items():
        url = BASE_URL + str(file_id)
        entries = archive_entries(url)
        for name in names:
            target = args.output / f"{archive_name}_{name}"
            target.write_bytes(extract_entry(url, name, entries[name]))
            print(f"{archive_name}: {name} -> {target}")


if __name__ == "__main__":
    main()
