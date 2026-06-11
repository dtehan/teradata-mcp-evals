"""
Entry point for the Teradata MCP eval suite.

Usage:
    uv run python run_evals.py                        # all modules
    uv run python run_evals.py --module base          # one module
    uv run python run_evals.py --module base --type ambiguous_selection
    uv run python run_evals.py --verbose
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Teradata MCP evals via deepeval + pytest")
    parser.add_argument("--module", help="Run evals for a specific module only (base, sec, dba, ...)")
    parser.add_argument("--type", dest="case_type", help="Filter by case type (happy_path, ambiguous_selection, missing_parameter, multi_tool)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose pytest output")
    args = parser.parse_args()

    cmd = ["deepeval", "test", "run", "tests/"]

    if args.module:
        cmd += ["-k", f"test_{args.module}"]

    if args.case_type:
        # deepeval passes extra -k filters through to pytest
        existing_k = next((cmd[i + 1] for i, c in enumerate(cmd) if c == "-k"), None)
        if existing_k:
            idx = cmd.index("-k")
            cmd[idx + 1] = f"{existing_k} and {args.case_type}"
        else:
            cmd += ["-k", args.case_type]

    if args.verbose:
        cmd.append("-v")

    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
