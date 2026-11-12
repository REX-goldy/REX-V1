#!/usr/bin/env python3
"""Restore gitignored market data from the compressed seed archive.

The live preview/deploy snapshot only carries tracked files, so most of
``data/historical`` would be missing there. ``data/seed/historical.tar.xz`` is
a small tracked seed; this script unpacks it into the data root and only
copies files that are missing or differ, so a local checkout with the real
data is left untouched.
"""

from __future__ import annotations


import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed" / "historical.tar.xz"


def data_destination() -> Path:
    configured = os.environ.get("REX_DATA_DIR", "").strip()
    if configured:
        return Path(configured)
    return ROOT / "data" / "historical"


def prepare_destination(destination: Path) -> None:
    """Make sure the data root is a writable real directory.

    A developer checkout may keep the datasets outside the workspace and
    expose them through a symlink; that link is valid locally and must stay.
    In a synced preview/deploy snapshot the link target does not exist, so the
    dangling link is replaced by a real directory the seed can fill.
    """
    if destination.is_symlink():
        if destination.exists():
            return
        destination.unlink()
    destination.mkdir(parents=True, exist_ok=True)


def extract(archive: Path, destination: Path) -> tuple[int, int]:
    written = 0
    skipped = 0
    prepare_destination(destination)
    with tempfile.TemporaryDirectory(prefix="rex-seed-") as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive, "r:xz") as tar:
            try:
                tar.extractall(tmp_path, filter="data")
            except TypeError:  # Python < 3.11.4 has no extraction filter
                tar.extractall(tmp_path)
        for source in sorted(tmp_path.rglob("*")):
            if not source.is_file():
                continue
            target = destination / source.relative_to(tmp_path)
            # Never overwrite local datasets: the preview/deploy snapshot gets
            # the seed into an otherwise empty data root, while a developer
            # checkout keeps its real (gitignored) data untouched.
            if target.exists():
                skipped += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            written += 1
    return written, skipped


def main() -> int:
    if not SEED.is_file():
        print(f"[seed] no archive at {SEED}; skipping", flush=True)
        return 0
    destination = data_destination()
    written, skipped = extract(SEED, destination)
    print(
        f"[seed] {SEED.name}: wrote {written} file(s), kept {skipped} "
        f"existing file(s) in {destination}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
