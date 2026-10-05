"""Tests for shallow multi-turn case schema validation."""

import pytest

from tests.case_runner import MAX_TURNS, validate_eval_case, validate_multi_turn_case


def test_valid_two_turn_case():
    case = {
        "id": "example",
        "type": "multi_turn",
        "turns": [
            {"input": "Preview some rows", "expect": "clarification"},
            {
                "input": "Preview mydb.evals_employees",
                "expected_tools": [{"name": "base_tablePreview", "params": {}}],
            },
        ],
    }
    validate_eval_case(case)


def test_rejects_single_turn():
    with pytest.raises(ValueError, match="at least 2 turns"):
        validate_multi_turn_case({"id": "bad", "turns": [{"input": "hi", "expect": "clarification"}]})


def test_rejects_too_many_turns():
    turns = [{"input": f"turn {i}", "expect": "clarification"} for i in range(MAX_TURNS)]
    turns.append({"input": "one too many", "expect": "clarification"})
    with pytest.raises(ValueError, match=f"at most {MAX_TURNS} turns"):
        validate_multi_turn_case({"id": "bad", "turns": turns})


def test_rejects_turn_without_mode():
    with pytest.raises(ValueError, match="exactly one of"):
        validate_multi_turn_case(
            {
                "id": "bad",
                "turns": [
                    {"input": "Preview some rows"},
                    {"input": "Preview mydb.e", "expected_tools": [{"name": "base_tablePreview", "params": {}}]},
                ],
            }
        )


def test_rejects_turn_with_both_modes():
    with pytest.raises(ValueError, match="exactly one of"):
        validate_multi_turn_case(
            {
                "id": "bad",
                "turns": [
                    {
                        "input": "Preview some rows",
                        "expect": "clarification",
                        "expected_tools": [{"name": "base_tablePreview", "params": {}}],
                    },
                    {"input": "again", "expected_tools": [{"name": "base_tablePreview", "params": {}}]},
                ],
            }
        )


def test_turns_require_multi_turn_type():
    with pytest.raises(ValueError, match="only valid when type is multi_turn"):
        validate_eval_case(
            {
                "id": "bad",
                "type": "missing_parameter",
                "turns": [
                    {"input": "Preview some rows", "expect": "clarification"},
                    {
                        "input": "Preview mydb.e",
                        "expected_tools": [{"name": "base_tablePreview", "params": {}}],
                    },
                ],
            }
        )


def test_multi_turn_without_turns_is_rejected():
    with pytest.raises(ValueError, match="require a turns array"):
        validate_eval_case({"id": "bad", "type": "multi_turn"})


def test_ambiguous_selection_requires_competing_tool():
    with pytest.raises(ValueError, match="require competing_tool"):
        validate_eval_case(
            {
                "id": "bad",
                "type": "ambiguous_selection",
                "expected_tools": [{"name": "plot_line_chart", "params": {}}],
            }
        )
