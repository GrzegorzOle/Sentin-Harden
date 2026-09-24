#!/usr/bin/env python3
"""Build the standalone artifact.

Runs the checks that must pass before an artifact is worth building, then calls
PyInstaller with the project spec. The order matters: a base with findings must
not be frozen, because the rule files travel inside the artifact and a fault
there is only discovered on the machine being audited.

Usage:
    python tools/build_artifact.py [--skip-validation] [--clean]

Exit code 0 means the artifact was built and its rule base was found in place.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SPEC = PROJECT / "sentin-harden.spec"
DIST = PROJECT / "dist" / "Sentin-Harden"


def run(command: list[str], description: str) -> None:
    print(f"==> {description}")
    result = subprocess.run(command, cwd=PROJECT)
    if result.returncode != 0:
        raise SystemExit(f"{description}: failed with code {result.returncode}")


def validate() -> None:
    run(
        [sys.executable, str(PROJECT / "tools" / "validate_rules.py")],
        "checking the rule base",
    )


def build(clean: bool) -> None:
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    if clean:
        command.append("--clean")
    command.append(str(SPEC))
    run(command, "freezing the application")


def verify() -> None:
    """Confirm the artifact carries what it needs to carry.

    PyInstaller reports success even where a data directory was collected
    empty, so the rule base is counted here instead of being taken on trust.
    """
    print("==> checking the artifact")
    # The suffix is Windows-only. Naming it unconditionally made this check fail
    # on Linux after a freeze that had in fact succeeded.
    executable = DIST / ("Sentin-Harden.exe" if os.name == "nt" else "Sentin-Harden")
    if not executable.exists():
        raise SystemExit(f"the executable is missing: {executable}")

    # In a directory build the bundled data lands beside the runtime, under
    # _internal. Both layouts are accepted so that a change in PyInstaller does
    # not silently turn this check into one that never looks anywhere.
    candidates = [DIST / "_internal" / "rules", DIST / "rules"]
    rules_root = next((path for path in candidates if path.is_dir()), None)
    if rules_root is None:
        raise SystemExit("the rule base did not reach the artifact")

    targets = sorted(
        path.name for path in rules_root.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    )
    total = len(list(rules_root.glob("*/rules/*.yaml")))
    if not targets or total == 0:
        raise SystemExit("the rule base reached the artifact empty")

    schema = rules_root / "_schema" / "rule.schema.json"
    if not schema.exists():
        raise SystemExit("the schema did not reach the artifact")

    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"    executable: {executable}")
    print(f"    targets:    {len(targets)} ({', '.join(targets)})")
    print(f"    rules:      {total}")
    print(f"    size:       {size / (1024 * 1024):.0f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="build without checking the rule base first",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="discard the previous build directory before starting",
    )
    args = parser.parse_args()

    if not SPEC.exists():
        raise SystemExit(f"the build configuration is missing: {SPEC}")

    if args.clean and DIST.parent.exists():
        shutil.rmtree(DIST.parent, ignore_errors=True)

    if not args.skip_validation:
        validate()
    build(args.clean)
    verify()

    print("==> done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
