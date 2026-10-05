"""deepeval metrics for the Teradata MCP eval suite.

Tool name and parameter correctness are decided by judge/checks.py before any
metric runs. ToolCorrectnessMetric is not used: without available_tools it
assigns a constant selection score and never calls Bedrock. Clarification is
the only LLM judge, via GEval.
"""

from __future__ import annotations

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams

from judge.kinds import Kind, kind_of


def clarification_metric(judge_llm) -> GEval:
    """For missing_parameter cases and clarification turns: the agent asked instead of guessing."""
    return GEval(
        name="Clarification Check",
        criteria=(
            "The agent was given a prompt that is missing a required parameter. "
            "The agent should ask the user for the missing information rather than "
            "inventing a value or proceeding with a guess. "
            "Score 1.0 if the response contains a clear request for the missing information. "
            "Score 0.0 if the agent fabricated a parameter value or called a tool without asking."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=judge_llm,
        threshold=0.5,
    )


def get_metrics(case: dict, judge_llm, *, kind: Kind | None = None) -> list:
    """Return GEval clarification when the kind forbids tool calls, otherwise no metrics."""
    resolved = kind if kind is not None else kind_of(case)
    if not resolved.expects_tool_calls:
        return [clarification_metric(judge_llm)]
    return []
