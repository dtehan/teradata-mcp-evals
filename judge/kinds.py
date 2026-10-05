"""Canonical eval case kinds.

One table owns the type string, scoring policy, and whether a competitor is
stored on the case. Callers read Kind flags instead of copying type if-chains
or inferring the losing tool from an id suffix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Kind:
    name: str
    expects_tool_calls: bool
    ordered: bool = False
    has_turns: bool = False
    has_competitor: bool = False


KINDS: dict[str, Kind] = {
    "happy_path": Kind(name="happy_path", expects_tool_calls=True),
    "ambiguous_selection": Kind(
        name="ambiguous_selection",
        expects_tool_calls=True,
        has_competitor=True,
    ),
    "missing_parameter": Kind(
        name="missing_parameter",
        expects_tool_calls=False,
    ),
    "multi_tool": Kind(
        name="multi_tool",
        expects_tool_calls=True,
        ordered=True,
    ),
    "multi_turn": Kind(
        name="multi_turn",
        expects_tool_calls=True,
        has_turns=True,
    ),
}

CLARIFICATION = KINDS["missing_parameter"]
TOOL_TURN = KINDS["happy_path"]


def kind_of(case: dict[str, Any]) -> Kind:
    """Return the Kind for a case JSON object or a summary row.

    A stored ``type`` of ``multi_turn`` requires a ``turns`` array. A ``turns``
    array requires that type. A summary row that only has ``case_type`` is not
    a case document, so it is not checked for turns.
    """
    label = case.get("id") or case.get("case_id") or "<unknown>"
    name = case.get("type") or case.get("case_type")
    if not isinstance(name, str) or not name:
        raise ValueError(f"[{label}] case is missing type")
    kind = KINDS.get(name)
    if kind is None:
        raise ValueError(f"[{label}] unknown case type {name!r}")
    has_turns = "turns" in case
    if has_turns and not kind.has_turns:
        raise ValueError(f"[{label}] turns is only valid when type is multi_turn")
    if "type" in case and kind.has_turns and not has_turns:
        raise ValueError(f"[{label}] multi_turn cases require a turns array")
    return kind


def competing_tool(case: dict[str, Any]) -> str | None:
    """Return the stored losing tool on an ambiguous_selection case."""
    value = case.get("competing_tool")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def select_cases(cases: list[dict[str, Any]], case_type: str | None) -> list[dict[str, Any]]:
    """Keep cases whose ``type`` field equals ``case_type``.

    ``None`` and ``"all"`` keep every case. Matching uses the type field, not the case id.
    """
    if not case_type or case_type == "all":
        return list(cases)
    if case_type not in KINDS:
        raise ValueError(f"unknown case type {case_type!r}")
    return [case for case in cases if case.get("type") == case_type]
