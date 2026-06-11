#!/usr/bin/env python3
"""Run the reference kit checks used by local development and CI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PYTHON_CHECKS = [
    [
        sys.executable,
        "-m",
        "py_compile",
        "btc_tx_parser.py",
        "btc_ergo_proof.py",
        "test_rosen_bridge.py",
        "tests/fixtures.py",
        "tests/test_reference_kit.py",
        "tests/test_vector_schema.py",
        "tests/test_fuzz_differential.py",
    ],
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    [
        sys.executable,
        "btc_ergo_proof.py",
        "verify-local",
        "test-vectors/valid/rosen-bridge-output1.proof.json",
    ],
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Run only Python syntax, unit, and vector checks.",
    )
    parser.add_argument(
        "--sbt-only",
        action="store_true",
        help="Run only the AppKit ErgoScript compilation check.",
    )
    args = parser.parse_args()

    if args.python_only and args.sbt_only:
        parser.error("--python-only and --sbt-only are mutually exclusive")

    commands = []
    if not args.sbt_only:
        commands.extend(PYTHON_CHECKS)
    if not args.python_only:
        commands.append([find_sbt(), "test"])

    for command in commands:
        print_command(command)
        subprocess.run(command, cwd=ROOT, check=True, stdout=sys.stdout, stderr=sys.stdout)

    print("All checks passed.")
    return 0


def find_sbt() -> str:
    sbt = shutil.which("sbt") or shutil.which("sbt.bat")
    if sbt is None:
        raise SystemExit("sbt is required for ErgoScript compilation checks.")
    return sbt


def print_command(command: list[str]) -> None:
    display = [
        Path(part).name if part == sys.executable or Path(part).is_absolute() else part
        for part in command
    ]
    print(f"\n$ {' '.join(display)}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
