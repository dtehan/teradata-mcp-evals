"""Shared fixtures and helpers for the Teradata MCP eval suite."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

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
    data = json.loads(path.read_text())
    # Filter out comment/instruction stubs
    return [c for c in data.get("cases", []) if "id" in c]


def build_test_case(case: dict, bedrock_client, agent_model_id: str):
    """Run the agent on a case and return a deepeval LLMTestCase."""
    from deepeval.test_case import LLMTestCase, ToolCall
    from agent.client import run_agent

    evals_db = os.environ.get("EVALS_DATABASE", "")
    resolved = _substitute(case, evals_db)

    result = run_agent(
        prompt=resolved["input"],
        model_id=agent_model_id,
        bedrock_client=bedrock_client,
    )

    tools_called = [
        ToolCall(name=tc.name, input_parameters=tc.input_parameters)
        for tc in result.tool_calls
    ]
    expected_tools = [
        ToolCall(name=tc["name"], input_parameters=tc.get("params", {}))
        for tc in resolved.get("expected_tools", [])
    ]

    return LLMTestCase(
        input=resolved["input"],
        actual_output=result.final_response,
        tools_called=tools_called,
        expected_tools=expected_tools,
    )


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
