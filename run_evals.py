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

from preflight import run_preflight


CASE_TYPE_FILTERS = {
    "happy_path": "happy",
    "ambiguous_selection": "ambiguous",
    "missing_parameter": "missing",
    "multi_tool": "multi_tool",
    "multi_turn": "clarify_then_call",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Teradata MCP evals via deepeval + pytest")
    parser.add_argument("--module", help="Run evals for a specific module only (base, sec, dba, ...)")
    parser.add_argument(
        "--type",
        dest="case_type",
        help=(
            "Filter by case type (happy_path, ambiguous_selection, missing_parameter, "
            "multi_tool, multi_turn). Matches substrings in pytest case IDs."
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose pytest output")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip Teradata eval-table check (not recommended for live eval runs)",
    )
    args = parser.parse_args()

    if not args.skip_preflight:
        run_preflight()

    cmd = ["deepeval", "test", "run", "tests/"]

    if args.module:
        cmd += ["-k", f"test_{args.module}"]

    if args.case_type:
        keyword = CASE_TYPE_FILTERS.get(args.case_type, args.case_type)
        existing_k = next((cmd[i + 1] for i, c in enumerate(cmd) if c == "-k"), None)
        if existing_k:
            idx = cmd.index("-k")
            cmd[idx + 1] = f"{existing_k} and {keyword}"
        else:
            cmd += ["-k", keyword]

    if args.verbose:
        cmd.append("-v")

    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
