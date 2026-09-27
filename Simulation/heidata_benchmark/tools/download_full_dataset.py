"""Download and verify the complete public heiDATA dataset.

The downloader discovers the published files from the heiDATA Dataverse API,
stores the archives outside the repository, resumes interrupted downloads, and
verifies each file against the publisher supplied MD5 checksum.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import socket
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DATASET_DOI = "doi:10.11588/DATA/D3WZID"
DATASET_API = (
    "https://heidata.uni-heidelberg.de/api/datasets/:persistentId/"
    "?persistentId=" + DATASET_DOI
)
ACCESS_URL = "https://heidata.uni-heidelberg.de/api/access/datafile/{}"
DEFAULT_ROOT = Path.home() / "Datasets" / "heiDATA_D3WZID"
CHUNK_SIZE = 8 * 1024 * 1024
RANGE_CHUNK_SIZE = 64 * 1024 * 1024
RANGE_RETRIES = 8
USER_AGENT = "PGBMThesisHeiDATA/1.0 (academic research)"


def _request(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 90):
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    return urlopen(Request(url, headers=request_headers), timeout=timeout)


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def fetch_dataset_metadata() -> dict:
    with _request(DATASET_API) as response:
        return json.loads(response.read().decode("utf-8"))


def published_files(metadata: dict) -> List[dict]:
    version = metadata["data"]["latestVersion"]
    records = []
    for entry in version["files"]:
        data_file = entry["dataFile"]
        category = "code" if "Code" in entry.get("categories", []) else "data"
        records.append(
            {
                "id": data_file["id"],
                "filename": data_file["filename"],
                "category": category,
                "content_type": data_file.get("contentType"),
                "size_bytes": int(data_file["filesize"]),
                "md5": data_file["md5"].lower(),
                "persistent_id": data_file.get("persistentId"),
                "url": ACCESS_URL.format(data_file["id"]),
            }
        )
    return sorted(records, key=lambda record: (record["category"], record["filename"]))


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            block = handle.read(CHUNK_SIZE)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _target_path(root: Path, record: dict) -> Path:
    folder = root / ("code" if record["category"] == "code" else "archives")
    return folder / record["filename"]


def verify_file(path: Path, record: dict) -> dict:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    size = path.stat().st_size
    if size != record["size_bytes"]:
        return {
            "status": "size_mismatch",
            "path": str(path),
            "size_bytes": size,
            "expected_size_bytes": record["size_bytes"],
        }
    actual_md5 = md5_file(path)
    return {
        "status": "verified" if actual_md5 == record["md5"] else "checksum_mismatch",
        "path": str(path),
        "size_bytes": size,
        "md5": actual_md5,
        "expected_md5": record["md5"],
    }


def _range_block(record: dict, start: int, end: int, logger: logging.Logger) -> bytes:
    expected_length = end - start + 1
    for attempt in range(1, RANGE_RETRIES + 1):
        try:
            with _request(
                record["url"],
                headers={"Range": "bytes={}-{}".format(start, end)},
                timeout=90,
            ) as response:
                status = getattr(response, "status", 200)
                content_range = response.headers.get("Content-Range", "")
                block = response.read()
            if status != 206 or not content_range.startswith("bytes {}-{}".format(start, end)):
                raise RuntimeError(
                    "range request returned unexpected response: status={}, range={!r}".format(
                        status, content_range
                    )
                )
            if len(block) != expected_length:
                raise RuntimeError(
                    "range response length mismatch: expected {}, got {}".format(
                        expected_length, len(block)
                    )
                )
            return block
        except socket.timeout as error:
            if attempt == RANGE_RETRIES:
                raise RuntimeError(
                    "timed out reading {} after {} attempts".format(
                        record["filename"], RANGE_RETRIES
                    )
                ) from error
            delay = min(120, 2 ** (attempt - 1) * 2)
            logger.warning(
                "range read timed out for %s at %d, retry %d/%d in %ds",
                record["filename"], start, attempt, RANGE_RETRIES, delay,
            )
            time.sleep(delay)
        except (HTTPError, URLError, OSError, RuntimeError) as error:
            if attempt == RANGE_RETRIES:
                raise RuntimeError(
                    "failed range {}-{} for {} after {} attempts: {}".format(
                        start, end, record["filename"], RANGE_RETRIES, error
                    )
                ) from error
            delay = min(120, 2 ** (attempt - 1) * 2)
            logger.warning(
                "range request failed for %s at %d, retry %d/%d in %ds: %s",
                record["filename"], start, attempt, RANGE_RETRIES, delay, error,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")


def _download_record(record: dict, root: Path, logger: logging.Logger) -> dict:
    target = _target_path(root, record)
    partial = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)

    existing = verify_file(target, record)
    if existing["status"] == "verified":
        logger.info("already verified: %s", target)
        return {**record, **existing}
    if target.exists():
        raise RuntimeError(
            "existing file does not match publisher metadata: {} ({})".format(
                target, existing["status"]
            )
        )

    start = partial.stat().st_size if partial.exists() else 0
    if start > record["size_bytes"]:
        raise RuntimeError("partial file is larger than expected: {}".format(partial))

    downloaded = start
    last_report = time.monotonic()
    with partial.open("ab") as handle:
        while downloaded < record["size_bytes"]:
            end = min(downloaded + RANGE_CHUNK_SIZE, record["size_bytes"]) - 1
            block = _range_block(record, downloaded, end, logger)
            handle.write(block)
            handle.flush()
            downloaded += len(block)
            now = time.monotonic()
            if now - last_report >= 10 or downloaded == record["size_bytes"]:
                logger.info(
                    "downloading %s: %.1f%% (%d/%d bytes)",
                    target.name,
                    100.0 * downloaded / record["size_bytes"],
                    downloaded,
                    record["size_bytes"],
                )
                last_report = now

    result = verify_file(partial, record)
    if result["status"] != "verified":
        raise RuntimeError(
            "download verification failed for {}: {}".format(target, result)
        )
    os.replace(partial, target)
    logger.info("verified: %s", target)
    return {**record, **result, "path": str(target)}


def _configure_logging(root: Path) -> logging.Logger:
    logger = logging.getLogger("heidata_full_download")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    file_handler = logging.FileHandler(root / "download.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream)
    logger.addHandler(file_handler)
    return logger


def download_dataset(root: Path, dry_run: bool = False) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    metadata = fetch_dataset_metadata()
    records = published_files(metadata)
    _write_json(root / "dataset_metadata.json", metadata)
    _write_json(
        root / "publisher_manifest.json",
        {
            "dataset_doi": DATASET_DOI,
            "dataset_url": "https://doi.org/10.11588/DATA/D3WZID",
            "files": records,
        },
    )

    if dry_run:
        return {"root": str(root), "files": records, "dry_run": True}

    logger = _configure_logging(root)
    results = []
    for record in records:
        results.append(_download_record(record, root, logger))
        _write_json(
            root / "download_state.json",
            {"dataset_doi": DATASET_DOI, "files": results},
        )
    return {"root": str(root), "files": results, "dry_run": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="discover files and sizes without downloading them",
    )
    args = parser.parse_args()
    result = download_dataset(args.output.expanduser(), dry_run=args.dry_run)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
