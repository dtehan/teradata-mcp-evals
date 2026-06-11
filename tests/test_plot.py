import pytest
from deepeval import assert_test
from judge.metrics import get_metrics
from tests.conftest import build_test_case, load_cases


@pytest.mark.parametrize("case", load_cases("plot"), ids=lambda c: c["id"])
def test_plot(case, bedrock_client, agent_model_id, judge_llm):
    tc = build_test_case(case, bedrock_client, agent_model_id)
    assert_test(tc, get_metrics(case, judge_llm))
