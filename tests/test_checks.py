"""Unit tests for deterministic structural checks."""

import pytest

from judge.checks import ToolCallRecord, assert_deterministic_checks, run_deterministic_checks
from judge.kinds import CLARIFICATION, TOOL_TURN, kind_of, select_cases


def _call(name: str, **params) -> ToolCallRecord:
    return ToolCallRecord(name=name, input_parameters=params)


def test_missing_parameter_rejects_tool_calls():
    case = {"id": "test", "type": "missing_parameter", "expected_tools": []}
    errors = run_deterministic_checks(case, [_call("base_readQuery", sql="SELECT 1")])
    assert len(errors) == 1
    assert "no tool calls" in errors[0]


def test_happy_path_checks_tool_name_and_exact_params():
    case = {
        "id": "test",
        "type": "happy_path",
        "expected_tools": [
            {
                "name": "base_tableList",
                "params": {"database_name": "mydb"},
            }
        ],
    }
    assert not run_deterministic_checks(
        case,
        [_call("base_tableList", database_name="mydb")],
    )
    errors = run_deterministic_checks(
        case,
        [_call("base_tablePreview", database_name="mydb", table_name="t")],
    )
    assert any("base_tableList" in e for e in errors)


def test_multi_tool_enforces_order_and_count():
    case = {
        "id": "test",
        "type": "multi_tool",
        "expected_tools": [
            {"name": "base_tableList", "params": {"database_name": "mydb"}},
            {"name": "base_tablePreview", "params": {"database_name": "mydb", "table_name": "evals_employees"}},
        ],
    }
    ok_calls = [
        _call("base_tableList", database_name="mydb"),
        _call("base_tablePreview", database_name="mydb", table_name="evals_employees"),
    ]
    assert not run_deterministic_checks(case, ok_calls)

    wrong_order = list(reversed(ok_calls))
    errors = run_deterministic_checks(case, wrong_order)
    assert any("step 1" in e for e in errors)


def test_sql_param_presence_only():
    case = {
        "id": "test",
        "type": "happy_path",
        "expected_tools": [
            {
                "name": "base_readQuery",
                "params": {"sql": "SELECT 1"},
            }
        ],
    }
    assert not run_deterministic_checks(
        case,
        [_call("base_readQuery", sql="SELECT 2")],
    )


def test_assert_raises_on_failure():
    case = {"id": "bad", "type": "missing_parameter", "expected_tools": []}
    try:
        assert_deterministic_checks(case, [_call("base_readQuery")])
        raise AssertionError("expected assertion")
    except AssertionError as exc:
        assert "bad" in str(exc)



def test_clarification_kind_rejects_tools_without_rewriting_type():
    case = {"id": "turn", "expected_tools": []}
    errors = run_deterministic_checks(case, [_call("base_readQuery", sql="SELECT 1")], kind=CLARIFICATION)
    assert len(errors) == 1
    assert "no tool calls" in errors[0]


def test_tool_turn_kind_checks_primary_tool():
    case = {
        "id": "turn",
        "expected_tools": [{"name": "base_tableList", "params": {"database_name": "mydb"}}],
    }
    assert not run_deterministic_checks(
        case,
        [_call("base_tableList", database_name="mydb")],
        kind=TOOL_TURN,
    )



def test_get_metrics_skips_tool_kinds():
    from judge.metrics import get_metrics

    for case_type in ("happy_path", "ambiguous_selection", "multi_tool", "multi_turn"):
        case = {"type": case_type}
        if case_type == "multi_turn":
            case["turns"] = []
        assert get_metrics(case, judge_llm=None) == []


def test_select_cases_uses_the_type_field_not_the_id():
    cases = [
        {
            "id": "sec_user_missing_role_clarify_then_call",
            "type": "multi_turn",
            "turns": [],
        },
        {"id": "base_read_missing_sql", "type": "missing_parameter"},
    ]
    assert [case["id"] for case in select_cases(cases, "missing_parameter")] == ["base_read_missing_sql"]
    assert [case["id"] for case in select_cases(cases, "multi_turn")] == [
        "sec_user_missing_role_clarify_then_call"
    ]


def test_kind_of_rejects_turns_on_the_wrong_type():
    with pytest.raises(ValueError, match="only valid when type is multi_turn"):
        kind_of({"id": "bad", "type": "missing_parameter", "turns": []})
