#!/usr/bin/env python3
"""Sync A-share report static site artifacts and rebuild the shareable zip."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Report date in YYYY-MM-DD format.")
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root containing a-share-report-site/.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    site_dir = workspace / "a-share-report-site"
    index = site_dir / "index.html"
    if not index.exists():
        raise SystemExit(f"Missing site entry: {index}")

    archive = workspace / f"a-share-report-{args.date}.html"
    shutil.copy2(index, archive)

    legacy = workspace / "a-share-report-2026-05-04.html"
    if legacy.exists():
        shutil.copy2(index, legacy)

    zip_path = workspace / "a-share-report-site.zip"
    if zip_path.exists():
        zip_path.unlink()

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for path in sorted(site_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(workspace).as_posix())

    print(f"archive={archive}")
    print(f"zip={zip_path}")


if __name__ == "__main__":
    main()
