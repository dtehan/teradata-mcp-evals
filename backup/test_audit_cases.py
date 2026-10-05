"""Unit tests for audit_cases.py (offline logic only — no MCP connection)."""

from backup.audit_cases import (
    audit_ambiguous_pair_gaps,
    audit_live_tool_gaps,
    covered_ambiguous_pairs,
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


def test_covered_ambiguous_pairs_uses_stored_competitor():
    cases = [
        {
            "id": "plot_line_vs_radar_ambiguous",
            "type": "ambiguous_selection",
            "competing_tool": "plot_radar_chart",
            "expected_tools": [{"name": "plot_line_chart", "params": {}}],
        }
    ]
    assert frozenset({"plot_line_chart", "plot_radar_chart"}) in covered_ambiguous_pairs("plot", cases)


def test_shipped_plot_cases_store_the_competitor():
    from tests.conftest import load_cases

    by_id = {case["id"]: case for case in load_cases("plot")}
    assert by_id["plot_line_vs_radar_ambiguous"]["competing_tool"] == "plot_radar_chart"
    assert by_id["plot_pie_vs_polar_ambiguous"]["competing_tool"] == "plot_polar_chart"


def test_audit_plot_pairs_pass_when_competitor_is_stored():
    cases = [
        {
            "id": "plot_line_vs_radar_ambiguous",
            "type": "ambiguous_selection",
            "competing_tool": "plot_radar_chart",
            "expected_tools": [{"name": "plot_line_chart", "params": {}}],
        },
        {
            "id": "plot_pie_vs_polar_ambiguous",
            "type": "ambiguous_selection",
            "competing_tool": "plot_polar_chart",
            "expected_tools": [{"name": "plot_pie_chart", "params": {}}],
        },
        {"id": "h1", "type": "happy_path", "expected_tools": [{"name": "plot_line_chart", "params": {}}]},
        {"id": "h2", "type": "happy_path", "expected_tools": [{"name": "plot_radar_chart", "params": {}}]},
        {"id": "h3", "type": "happy_path", "expected_tools": [{"name": "plot_pie_chart", "params": {}}]},
        {"id": "h4", "type": "happy_path", "expected_tools": [{"name": "plot_polar_chart", "params": {}}]},
    ]
    gaps = audit_ambiguous_pair_gaps("plot", cases)
    assert gaps == []
