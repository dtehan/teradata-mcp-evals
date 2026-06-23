"""Unit tests for audit_cases.py (offline logic only — no MCP connection)."""

from backup.audit_cases import (
    audit_ambiguous_pair_gaps,
    audit_live_tool_gaps,
    happy_path_tools,
    tools_referenced_in_cases,
)


def test_tools_referenced_in_cases_includes_turns():
    cases = [
        {
            "id": "mt",
            "turns": [
                {"input": "hi", "expect": "clarification"},
                {"input": "go", "expected_tools": [{"name": "base_tablePreview", "params": {}}]},
            ],
        },
        {"id": "single", "expected_tools": [{"name": "base_readQuery", "params": {}}]},
    ]
    assert tools_referenced_in_cases(cases) == {"base_tablePreview", "base_readQuery"}


def test_happy_path_tools_only_counts_happy_cases():
    cases = [
        {"id": "h", "type": "happy_path", "expected_tools": [{"name": "base_tableList", "params": {}}]},
        {"id": "a", "type": "ambiguous_selection", "expected_tools": [{"name": "base_readQuery", "params": {}}]},
    ]
    assert happy_path_tools(cases) == {"base_tableList"}


def test_audit_live_tool_gaps_missing_happy_and_stale():
    cases = [
        {"id": "h", "type": "happy_path", "expected_tools": [{"name": "base_tableList", "params": {}}]},
        {"id": "old", "type": "happy_path", "expected_tools": [{"name": "base_removedTool", "params": {}}]},
    ]
    live = {"base_tableList", "base_readQuery"}

    gaps = audit_live_tool_gaps("base", live, cases, require_happy_path=True)
    assert any("missing happy_path for live tool: base_readQuery" in g for g in gaps)
    assert any("stale tool name" in g and "base_removedTool" in g for g in gaps)


def test_audit_live_tool_gaps_non_priority_notes_only():
    cases = []
    live = {"chat_completeChat"}

    gaps = audit_live_tool_gaps("chat", live, cases, require_happy_path=False)
    assert any("no cases yet" in g for g in gaps)
    assert not any("missing happy_path for live tool" in g for g in gaps)


def test_audit_ambiguous_pair_gaps_detects_missing_pair():
    gaps = audit_ambiguous_pair_gaps("base", [])
    assert any("base_readQuery" in g and "base_tablePreview" in g for g in gaps)
