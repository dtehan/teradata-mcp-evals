"""Shared fixtures and helpers for the Teradata MCP eval suite."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Keep EVALS_DATABASE and Bedrock settings from .env. Drop override flags that
# only existed in .env so a plain pytest run cannot silently patch descriptions.
_preset_use = os.environ.get("USE_DESCRIPTION_OVERRIDES")
_preset_file = os.environ.get("DESCRIPTION_OVERRIDES_FILE")
load_dotenv()
if _preset_use is None:
    os.environ.pop("USE_DESCRIPTION_OVERRIDES", None)
if _preset_file is None:
    os.environ.pop("DESCRIPTION_OVERRIDES_FILE", None)

CASES_DIR = Path(__file__).parent.parent / "cases"
MODULES = ["base", "dba", "sec", "qlty", "chat", "plot", "tmpl"]


def _substitute(obj, evals_db: str):
    """Recursively replace {EVALS_DATABASE} in strings within dicts/lists."""
    if isinstance(obj, str):
        return obj.replace("{EVALS_DATABASE}", evals_db)
    if isinstance(obj, dict):
        return {k: _substitute(v, evals_db) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute(i, evals_db) for i in obj]
    return obj


def load_cases(module: str) -> list[dict]:
    path = CASES_DIR / f"{module}.json"
    if not path.exists():
        return []
    from judge.kinds import select_cases

    data = json.loads(path.read_text())
    cases = [c for c in data.get("cases", []) if "id" in c]
    return select_cases(cases, os.environ.get("EVALS_RUN_TYPE"))


_session_overrides = None


def _description_overrides():
    from agent.client import DescriptionOverrides

    global _session_overrides
    if _session_overrides is None:
        _session_overrides = DescriptionOverrides(mapping={})
    return _session_overrides


def build_test_case(case: dict, bedrock_client, agent_model_id: str):
    """Run a single-turn case and return a deepeval LLMTestCase."""
    from tests.case_runner import build_test_case as _build_test_case

    evals_db = os.environ.get("EVALS_DATABASE", "").strip()
    resolved = _substitute(case, evals_db)
    return _build_test_case(resolved, bedrock_client, agent_model_id, overrides=_description_overrides())


def assert_eval_case(case: dict, bedrock_client, agent_model_id: str, judge_llm) -> None:
    """Run and score any eval case (single- or multi-turn)."""
    from tests.case_runner import assert_eval_case as _assert_eval_case

    evals_db = os.environ.get("EVALS_DATABASE", "").strip()
    resolved = _substitute(case, evals_db)
    _assert_eval_case(resolved, bedrock_client, agent_model_id, judge_llm, overrides=_description_overrides())


@pytest.fixture(scope="session")
def bedrock_client():
    import boto3
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


@pytest.fixture(scope="session")
def agent_model_id() -> str:
    return os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")


@pytest.fixture(scope="session")
def judge_llm(bedrock_client):
    from judge.bedrock_llm import BedrockLLM
    return BedrockLLM(bedrock_client=bedrock_client)


def pytest_sessionstart(session) -> None:
    """Initialize eval result collection for live eval runs."""
    from agent.client import description_overrides_from_env
    from judge.report import begin_eval_run

    global _session_overrides
    _session_overrides = description_overrides_from_env()
    status = _session_overrides.status()
    agent_model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
    judge_model_id = os.environ.get("BEDROCK_JUDGE_MODEL_ID", agent_model_id)
    begin_eval_run(
        agent_model_id=agent_model_id,
        judge_model_id=judge_model_id,
        evals_database=os.environ.get("EVALS_DATABASE", "").strip(),
        description_mode=str(status["mode"]),
        description_overrides_file=status.get("file"),  # type: ignore[arg-type]
        description_override_count=int(status.get("tool_count") or 0),
    )


def pytest_sessionfinish(session, exitstatus) -> None:
    """Write a markdown/json summary when live eval cases were executed."""
    from judge.report import get_current_report, write_eval_summary

    report = get_current_report()
    if report is None or not report.results:
        return

    artifacts = write_eval_summary(report)
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal is not None:
        terminal.write_line("")
        terminal.write_line(f"Eval run: {artifacts.run_id}")
        terminal.write_line(f"Run directory: results/{artifacts.run_dir.name}")
        terminal.write_line("Summary: results/latest_summary.md (copy of this run)")
        terminal.write_line("Index: results/index.json")
