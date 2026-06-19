"""Run single-turn and shallow multi-turn eval cases."""

from __future__ import annotations

import os
from typing import Any

from deepeval import assert_test
from deepeval.test_case import LLMTestCase, ToolCall

from agent.client import run_agent, run_agent_turns
from judge.checks import ToolCallRecord, assert_deterministic_checks
from judge.metrics import clarification_metric, get_metrics, tool_correctness_metric

MAX_TURNS = 7


def validate_multi_turn_case(case: dict) -> None:
    """Validate a shallow multi-turn case schema."""
    turns = case.get("turns")
    if turns is None:
        return

    if not isinstance(turns, list):
        raise ValueError(f"[{case.get('id')}] turns must be a list")

    if len(turns) < 2:
        raise ValueError(f"[{case.get('id')}] multi-turn cases need at least 2 turns")

    if len(turns) > MAX_TURNS:
        raise ValueError(f"[{case.get('id')}] multi-turn cases allow at most {MAX_TURNS} turns")

    for index, turn in enumerate(turns, start=1):
        is_clarification = turn.get("expect") == "clarification"
        has_tools = bool(turn.get("expected_tools"))
        if is_clarification == has_tools:
            raise ValueError(
                f"[{case.get('id')}] turn {index} must set exactly one of "
                "'expect': 'clarification' or non-empty 'expected_tools'",
            )
        if "input" not in turn:
            raise ValueError(f"[{case.get('id')}] turn {index} is missing 'input'")


def _to_tool_calls(records: list[ToolCallRecord]) -> list[ToolCall]:
    return [ToolCall(name=tc.name, input_parameters=tc.input_parameters) for tc in records]


def _make_test_case(
    *,
    user_input: str,
    response: str,
    tools_called: list[ToolCallRecord],
    expected_tools_raw: list[dict[str, Any]],
) -> LLMTestCase:
    return LLMTestCase(
        input=user_input,
        actual_output=response,
        tools_called=_to_tool_calls(tools_called),
        expected_tools=[
            ToolCall(name=t["name"], input_parameters=t.get("params", {}))
            for t in expected_tools_raw
        ],
    )


def build_test_case(case: dict, bedrock_client, agent_model_id: str) -> LLMTestCase:
    """Run a single-turn case and return a deepeval LLMTestCase."""
    validate_multi_turn_case(case)
    if "turns" in case:
        raise ValueError(f"[{case.get('id')}] use assert_eval_case() for multi-turn cases")

    result = run_agent(
        prompt=case["input"],
        model_id=agent_model_id,
        bedrock_client=bedrock_client,
    )

    raw_calls = [
        ToolCallRecord(name=tc.name, input_parameters=tc.input_parameters)
        for tc in result.tool_calls
    ]
    assert_deterministic_checks(case, raw_calls)

    return _make_test_case(
        user_input=case["input"],
        response=result.final_response,
        tools_called=raw_calls,
        expected_tools_raw=case.get("expected_tools", []),
    )


def assert_multi_turn_case(case: dict, bedrock_client, agent_model_id: str, judge_llm) -> None:
    """Run and score a shallow multi-turn case (2–7 turns)."""
    validate_multi_turn_case(case)
    turns = case["turns"]
    prompts = [turn["input"] for turn in turns]

    max_steps_per_turn = int(os.environ.get("AGENT_MAX_STEPS_PER_TURN", "3"))
    turn_results = run_agent_turns(
        prompts=prompts,
        model_id=agent_model_id,
        bedrock_client=bedrock_client,
        max_steps_per_turn=max_steps_per_turn,
    )

    conversation_prefix = ""

    for turn_number, (turn_spec, turn_result) in enumerate(zip(turns, turn_results, strict=True), start=1):
        raw_calls = [
            ToolCallRecord(name=tc.name, input_parameters=tc.input_parameters)
            for tc in turn_result.tool_calls
        ]
        turn_label = f"{case.get('id')} turn {turn_number}"

        if turn_spec.get("expect") == "clarification":
            assert_deterministic_checks(
                {"id": turn_label, "type": "missing_parameter", "expected_tools": []},
                raw_calls,
            )
            tc = _make_test_case(
                user_input=f"{conversation_prefix}User: {turn_spec['input']}",
                response=turn_result.final_response,
                tools_called=[],
                expected_tools_raw=[],
            )
            assert_test(tc, [clarification_metric(judge_llm)])
        else:
            pseudo_case = {
                "id": turn_label,
                "type": "happy_path",
                "expected_tools": turn_spec.get("expected_tools", []),
            }
            assert_deterministic_checks(pseudo_case, raw_calls)
            tc = _make_test_case(
                user_input=f"{conversation_prefix}User: {turn_spec['input']}",
                response=turn_result.final_response,
                tools_called=raw_calls,
                expected_tools_raw=turn_spec.get("expected_tools", []),
            )
            assert_test(tc, [tool_correctness_metric(judge_llm)])

        conversation_prefix += f"User: {turn_spec['input']}\nAssistant: {turn_result.final_response}\n"


def assert_eval_case(case: dict, bedrock_client, agent_model_id: str, judge_llm) -> None:
    """Run and score any eval case (single- or multi-turn)."""
    validate_multi_turn_case(case)
    if "turns" in case:
        assert_multi_turn_case(case, bedrock_client, agent_model_id, judge_llm)
        return

    tc = build_test_case(case, bedrock_client, agent_model_id)
    assert_test(tc, get_metrics(case, judge_llm))
