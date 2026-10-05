"""
Entry point for the Teradata MCP eval suite.

Usage:
    uv run python run_evals.py                        # all modules
    uv run python run_evals.py --module base          # one module
    uv run python run_evals.py --module base --type ambiguous_selection
    uv run python run_evals.py --verbose
    uv run python run_evals.py --module base --with-description-overrides
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from preflight import run_preflight
from agent.client import description_overrides_from_env
from judge.kinds import KINDS
from judge.report import format_run_index, load_latest_pointer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Teradata MCP evals via deepeval + pytest")
    parser.add_argument("--module", help="Run evals for a specific module only (base, sec, dba, ...)")
    parser.add_argument(
        "--type",
        dest="case_type",
        help=(
            "Filter by the case type field "
            "(happy_path, ambiguous_selection, missing_parameter, multi_tool, multi_turn)."
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose pytest output")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip Teradata eval-table check (not recommended for live eval runs)",
    )
    parser.add_argument(
        "--with-description-overrides",
        action="store_true",
        help=(
            "Patch tool descriptions from description_overrides.json before routing "
            "(default: use live MCP server descriptions as baseline)"
        ),
    )
    parser.add_argument(
        "--description-overrides-file",
        help="Path to overrides JSON (enables overrides; default: description_overrides.json)",
    )
    parser.add_argument(
        "--run-label",
        help="Optional label appended to the run directory name (e.g. after-tablelist-fix)",
    )
    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="List recent eval runs from results/index.json and exit",
    )
    args = parser.parse_args()

    if args.list_runs:
        print(format_run_index())
        pointer = load_latest_pointer()
        if pointer:
            print("")
            print(f"Latest run: {pointer.get('run_id')}")
            print(f"  dir: results/{pointer.get('run_dir')}")
            print(f"  summary: results/{pointer.get('summary_md')}")
        sys.exit(0)

    if not args.skip_preflight:
        run_preflight()

    if args.case_type and args.case_type not in KINDS:
        parser.error(
            f"unknown case type {args.case_type!r}; expected one of {', '.join(KINDS)}",
        )

    os.environ["EVALS_RUN_MODULE"] = args.module or "all"
    os.environ["EVALS_RUN_TYPE"] = args.case_type or "all"
    if args.run_label:
        os.environ["EVALS_RUN_LABEL"] = args.run_label
    elif "EVALS_RUN_LABEL" in os.environ:
        del os.environ["EVALS_RUN_LABEL"]

    if args.with_description_overrides or args.description_overrides_file:
        os.environ["USE_DESCRIPTION_OVERRIDES"] = "1"
    if args.description_overrides_file:
        os.environ["DESCRIPTION_OVERRIDES_FILE"] = args.description_overrides_file

    cmd = ["deepeval", "test", "run", "tests/"]

    if args.module:
        cmd += ["-k", f"test_{args.module}"]

    if args.verbose:
        cmd.append("-v")

    try:
        overrides = description_overrides_from_env()
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    if overrides.active:
        print(f"Tool descriptions: overrides from {overrides.source_file} ({len(overrides.mapping)} tools)")
    else:
        print("Tool descriptions: live MCP server (baseline)")

    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    if result.returncode in {0, 1}:
        pointer = load_latest_pointer()
        if pointer:
            print("")
            print(f"Eval run: {pointer.get('run_id')}")
            print(f"Run directory: results/{pointer.get('run_dir')}")
            print(f"Summary: results/{pointer.get('summary_md')}")
            print("Latest copy: results/latest_summary.md")
            print("All runs: uv run python run_evals.py --list-runs")
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
