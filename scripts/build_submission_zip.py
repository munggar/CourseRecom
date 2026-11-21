#!/usr/bin/env python3
"""Create a clean CourseRecom submission archive without local secrets/build artifacts."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT.parent / "CourseRecom-submission.zip"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    "dist",
    "build",
    "coverage",
    "playwright-report",
    "test-results",
    ".playwright",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log", ".zip"}
EXCLUDED_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDED_ENV_NAMES = {".env", "env.cloud"}


def should_exclude(path: Path, relative: Path) -> bool:
    parts = set(relative.parts)
    if parts & EXCLUDED_DIRS:
        return True

    name = path.name
    if name in EXCLUDED_FILES or name in EXCLUDED_ENV_NAMES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True

    # Keep documented examples, never ship actual local/production secrets.
    if name.startswith(".env.") and not (
        name.endswith(".example") or name.endswith(".sample")
    ):
        return True
    if name.endswith((".sqlite-wal", ".sqlite-shm")):
        return True
    return False


def build_archive(output: Path) -> tuple[int, int]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output == REPO_ROOT or REPO_ROOT in output.parents:
        raise ValueError("Output archive must be written outside the source tree.")

    file_count = 0
    uncompressed_bytes = 0
    temp_output = output.with_suffix(output.suffix + ".tmp")
    root_name = REPO_ROOT.name

    try:
        with zipfile.ZipFile(
            temp_output,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for current, directories, filenames in os.walk(REPO_ROOT):
                current_path = Path(current)
                relative_dir = current_path.relative_to(REPO_ROOT)
                directories[:] = sorted(
                    directory
                    for directory in directories
                    if not should_exclude(
                        current_path / directory,
                        relative_dir / directory,
                    )
                )
                for filename in sorted(filenames):
                    source = current_path / filename
                    relative = source.relative_to(REPO_ROOT)
                    if should_exclude(source, relative):
                        continue
                    arcname = Path(root_name) / relative
                    archive.write(source, arcname.as_posix())
                    file_count += 1
                    uncompressed_bytes += source.stat().st_size

        temp_output.replace(output)
    except Exception:
        temp_output.unlink(missing_ok=True)
        raise

    return file_count, uncompressed_bytes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package CourseRecom source/docs/tests without .git, venv, dependencies, secrets or local databases."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination ZIP (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    count, uncompressed = build_archive(args.output)
    archive_size = args.output.stat().st_size
    print(f"Archive: {args.output}")
    print(f"Files: {count}")
    print(f"Source size: {uncompressed:,} bytes")
    print(f"ZIP size: {archive_size:,} bytes")
    print("Excluded: .git, virtualenvs, node_modules, build/cache folders, .env secrets, local DBs, logs and nested ZIPs.")


if __name__ == "__main__":
    main()
