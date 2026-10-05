"""Unit tests for opt-in description override loading."""

import json

import pytest

from agent.client import (
    AgentResult,
    DescriptionOverrides,
    _apply_description_overrides,
    description_overrides_from_env,
    get_description_override_status,
    load_description_overrides_file,
    overrides_requested_from_env,
    resolve_description_overrides_file,
    run_agent,
)


class _FakeTool:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.inputSchema = {}

    def model_copy(self, *, update: dict):
        return _FakeTool(self.name, update.get("description", self.description))


def test_overrides_disabled_when_flag_absent(monkeypatch, tmp_path):
    overrides_file = tmp_path / "description_overrides.json"
    overrides_file.write_text(json.dumps({"base_readQuery": "override text"}))
    monkeypatch.delenv("USE_DESCRIPTION_OVERRIDES", raising=False)
    monkeypatch.setenv("DESCRIPTION_OVERRIDES_FILE", str(overrides_file))

    env = {
        "DESCRIPTION_OVERRIDES_FILE": str(overrides_file),
    }
    assert overrides_requested_from_env(env) is False
    loaded = description_overrides_from_env(env)
    assert loaded.active is False
    assert loaded.mapping == {}
    assert get_description_override_status(loaded)["mode"] == "mcp_server"


def test_overrides_enabled_with_flag_and_nonempty_file(monkeypatch, tmp_path):
    overrides_file = tmp_path / "description_overrides.json"
    overrides_file.write_text(json.dumps({"base_readQuery": "override text"}))
    env = {
        "USE_DESCRIPTION_OVERRIDES": "1",
        "DESCRIPTION_OVERRIDES_FILE": str(overrides_file),
    }

    loaded = description_overrides_from_env(env)
    assert loaded.active is True
    assert loaded.mapping == {"base_readQuery": "override text"}
    status = get_description_override_status(loaded)
    assert status["mode"] == "overrides"
    assert status["tool_count"] == 1


def test_empty_overrides_file_raises_when_opted_in(tmp_path):
    overrides_file = tmp_path / "description_overrides.json"
    overrides_file.write_text("{}")
    env = {
        "USE_DESCRIPTION_OVERRIDES": "1",
        "DESCRIPTION_OVERRIDES_FILE": str(overrides_file),
    }
    with pytest.raises(ValueError, match="no tool descriptions"):
        description_overrides_from_env(env)


def test_missing_overrides_file_raises_when_opted_in(tmp_path):
    env = {
        "USE_DESCRIPTION_OVERRIDES": "1",
        "DESCRIPTION_OVERRIDES_FILE": str(tmp_path / "missing.json"),
    }
    with pytest.raises(FileNotFoundError):
        description_overrides_from_env(env)


def test_status_for_empty_mapping_is_mcp_server():
    status = DescriptionOverrides(mapping={}).status()
    assert status["mode"] == "mcp_server"
    assert status["tool_count"] == 0


def test_apply_description_overrides_patches_matching_tools():
    tools = [_FakeTool("base_readQuery", "live description")]
    patched = _apply_description_overrides(tools, {"base_readQuery": "patched description"})
    assert patched[0].description == "patched description"


def test_resolve_description_overrides_file_is_path_only(tmp_path):
    path = tmp_path / "description_overrides.json"
    path.write_text(json.dumps({"base_readQuery": "x"}))
    resolved = resolve_description_overrides_file({"DESCRIPTION_OVERRIDES_FILE": str(path)})
    assert resolved == path


def test_load_description_overrides_file_skips_comment_keys(tmp_path):
    path = tmp_path / "description_overrides.json"
    path.write_text(json.dumps({"_comment": "keep", "base_readQuery": "patched"}))
    assert load_description_overrides_file(path) == {"base_readQuery": "patched"}


def test_run_agent_passes_the_overrides_argument(monkeypatch):
    monkeypatch.setenv("USE_DESCRIPTION_OVERRIDES", "1")
    monkeypatch.setenv("DESCRIPTION_OVERRIDES_FILE", "/tmp/not-the-source.json")
    captured = {}

    async def fake_run(**kwargs):
        captured.update(kwargs)
        return AgentResult(tool_calls=[], final_response="ok")

    monkeypatch.setattr("agent.client._run_agent_async", fake_run)
    overrides = DescriptionOverrides(mapping={"base_tableList": "patched"})
    result = run_agent("list tables", bedrock_client=object(), overrides=overrides)
    assert result.final_response == "ok"
    assert captured["overrides"] is overrides


def test_run_agent_without_overrides_ignores_the_environment(monkeypatch):
    monkeypatch.setenv("USE_DESCRIPTION_OVERRIDES", "1")
    monkeypatch.setenv("DESCRIPTION_OVERRIDES_FILE", "/tmp/not-the-source.json")
    captured = {}

    async def fake_run(**kwargs):
        captured.update(kwargs)
        return AgentResult(tool_calls=[], final_response="ok")

    monkeypatch.setattr("agent.client._run_agent_async", fake_run)
    run_agent("list tables", bedrock_client=object())
    assert captured["overrides"] is None
