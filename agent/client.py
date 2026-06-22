"""Multi-turn MCP agent that drives tool selection via Bedrock Claude."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MAX_TOOL_RESULT_CHARS = int(os.environ.get("MAX_TOOL_RESULT_CHARS", "8000"))

# ---------------------------------------------------------------------------
# Description-override dev space
# ---------------------------------------------------------------------------
# Set DESCRIPTION_OVERRIDES_FILE (or place description_overrides.json in the
# repo root) to patch tool descriptions seen by Bedrock without touching the
# running MCP server.  The file is gitignored — safe to iterate freely.
# ---------------------------------------------------------------------------


def _load_description_overrides() -> dict[str, str]:
    """Return {tool_name: description} from the overrides file, or {} if absent."""
    env_path = os.environ.get("DESCRIPTION_OVERRIDES_FILE")
    if env_path:
        candidates = [Path(env_path)]
    else:
        candidates = [
            Path(__file__).parent.parent / "description_overrides.json",
            Path("description_overrides.json"),
        ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if isinstance(data, dict):
                    return {k: v for k, v in data.items() if isinstance(v, str)}
            except Exception:
                pass
    return {}


def _apply_description_overrides(tools: list, overrides: dict[str, str]) -> list:
    """Return a new list with tool descriptions replaced where an override exists."""
    if not overrides:
        return tools

    patched = []
    for tool in tools:
        name = getattr(tool, "name", None)
        if name and name in overrides:
            tool = tool.model_copy(update={"description": overrides[name]})
        patched.append(tool)
    return patched


@dataclass
class ToolCallRecord:
    name: str
    input_parameters: dict[str, Any]


@dataclass
class TurnResult:
    tool_calls: list[ToolCallRecord]
    final_response: str


@dataclass
class AgentResult:
    tool_calls: list[ToolCallRecord]
    final_response: str


def _make_bedrock_client(region: str = "us-east-1"):
    return boto3.client("bedrock-runtime", region_name=region)


def _mcp_tool_to_bedrock(tool) -> dict:
    return {
        "toolSpec": {
            "name": tool.name,
            "description": tool.description or "",
            "inputSchema": {"json": tool.inputSchema},
        }
    }


def _extract_text(content_blocks: list[dict]) -> str:
    parts: list[str] = []
    for block in content_blocks:
        if "text" in block:
            parts.append(block["text"])
        elif block.get("type") == "text" and block.get("text"):
            parts.append(block["text"])
    return "".join(parts)


def _iter_tool_uses(content_blocks: list[dict]):
    for block in content_blocks:
        if "toolUse" in block:
            tool_use = block["toolUse"]
            yield tool_use["name"], tool_use.get("input", {}), tool_use["toolUseId"]
        elif block.get("type") == "toolUse":
            yield block["name"], block.get("input", {}), block["toolUseId"]


async def _build_tool_results(session: ClientSession, content_blocks: list[dict]) -> tuple[list[dict], list[ToolCallRecord]]:
    tool_results: list[dict] = []
    tool_calls: list[ToolCallRecord] = []

    for tool_name, tool_input, tool_use_id in _iter_tool_uses(content_blocks):
        tool_calls.append(ToolCallRecord(name=tool_name, input_parameters=tool_input))

        try:
            mcp_result = await session.call_tool(tool_name, tool_input)
            result_text = json.dumps(
                [c.model_dump() for c in mcp_result.content],
                default=str,
            )
        except Exception as exc:
            result_text = f"Tool error: {exc}"

        if len(result_text) > MAX_TOOL_RESULT_CHARS:
            result_text = result_text[:MAX_TOOL_RESULT_CHARS] + "\n... [truncated]"

        tool_results.append(
            {
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"text": result_text}],
                }
            }
        )

    return tool_results, tool_calls


async def _handle_tool_use(
    session: ClientSession,
    messages: list[dict],
    output_message: dict,
    *,
    record_calls: list[ToolCallRecord],
) -> bool:
    """Append tool results to messages. Returns False if tool_use had no usable blocks."""
    tool_results, tool_calls = await _build_tool_results(session, output_message.get("content", []))
    if not tool_results:
        return False

    record_calls.extend(tool_calls)
    messages.append({"role": "user", "content": tool_results})
    return True

async def _run_agent_turns_async(
    prompts: list[str],
    model_id: str,
    bedrock_client,
    mcp_url: str,
    max_steps_per_turn: int,
) -> list[TurnResult]:
    """Run a scripted multi-turn conversation in one MCP session."""
    overrides = _load_description_overrides()
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            patched_tools = _apply_description_overrides(tools_response.tools, overrides)
            bedrock_tools = [_mcp_tool_to_bedrock(t) for t in patched_tools]

            messages: list[dict] = []
            turn_results: list[TurnResult] = []

            for prompt in prompts:
                messages.append({"role": "user", "content": [{"text": prompt}]})
                turn_tool_calls: list[ToolCallRecord] = []
                final_response = ""

                for _ in range(max_steps_per_turn):
                    response = bedrock_client.converse(
                        modelId=model_id,
                        messages=messages,
                        toolConfig={
                            "tools": bedrock_tools,
                            "toolChoice": {"auto": {}},
                        },
                    )

                    stop_reason = response["stopReason"]
                    output_message = response["output"]["message"]
                    messages.append(output_message)

                    if stop_reason == "tool_use":
                        handled = await _handle_tool_use(
                            session,
                            messages,
                            output_message,
                            record_calls=turn_tool_calls,
                        )
                        if not handled:
                            final_response = _extract_text(output_message.get("content", []))
                            break
                    else:
                        final_response = _extract_text(output_message.get("content", []))
                        break

                turn_results.append(
                    TurnResult(tool_calls=turn_tool_calls, final_response=final_response)
                )

            return turn_results


async def _run_agent_async(
    prompt: str,
    model_id: str,
    bedrock_client,
    mcp_url: str,
    max_steps: int,
) -> AgentResult:
    overrides = _load_description_overrides()
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            patched_tools = _apply_description_overrides(tools_response.tools, overrides)
            bedrock_tools = [_mcp_tool_to_bedrock(t) for t in patched_tools]

            messages: list[dict] = [
                {"role": "user", "content": [{"text": prompt}]}
            ]
            tool_calls_made: list[ToolCallRecord] = []
            final_response = ""

            for _ in range(max_steps):
                response = bedrock_client.converse(
                    modelId=model_id,
                    messages=messages,
                    toolConfig={
                        "tools": bedrock_tools,
                        "toolChoice": {"auto": {}},
                    },
                )

                stop_reason = response["stopReason"]
                output_message = response["output"]["message"]
                messages.append(output_message)

                if stop_reason == "tool_use":
                    handled = await _handle_tool_use(
                        session,
                        messages,
                        output_message,
                        record_calls=tool_calls_made,
                    )
                    if not handled:
                        final_response = _extract_text(output_message.get("content", []))
                        break
                else:
                    final_response = _extract_text(output_message.get("content", []))
                    break

            return AgentResult(tool_calls=tool_calls_made, final_response=final_response)


def run_agent(
    prompt: str,
    model_id: str | None = None,
    bedrock_client=None,
    mcp_url: str | None = None,
    max_steps: int | None = None,
) -> AgentResult:
    """Synchronous entry point — runs the async agent loop via asyncio.run()."""
    resolved_model = model_id or os.environ.get(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
    )
    resolved_url = mcp_url or os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")
    resolved_steps = max_steps or int(os.environ.get("AGENT_MAX_STEPS", "5"))

    if bedrock_client is None:
        bedrock_client = _make_bedrock_client(
            region=os.environ.get("AWS_REGION", "us-east-1"),
        )

    return asyncio.run(
        _run_agent_async(
            prompt=prompt,
            model_id=resolved_model,
            bedrock_client=bedrock_client,
            mcp_url=resolved_url,
            max_steps=resolved_steps,
        )
    )


def run_agent_turns(
    prompts: list[str],
    model_id: str | None = None,
    bedrock_client=None,
    mcp_url: str | None = None,
    max_steps_per_turn: int | None = None,
) -> list[TurnResult]:
    """Run a shallow multi-turn conversation (separate tool-call budget per turn)."""
    if not prompts:
        raise ValueError("prompts must contain at least one user message")

    resolved_model = model_id or os.environ.get(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
    )
    resolved_url = mcp_url or os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")
    resolved_steps = max_steps_per_turn or int(os.environ.get("AGENT_MAX_STEPS_PER_TURN", "3"))

    if bedrock_client is None:
        bedrock_client = _make_bedrock_client(
            region=os.environ.get("AWS_REGION", "us-east-1"),
        )

    return asyncio.run(
        _run_agent_turns_async(
            prompts=prompts,
            model_id=resolved_model,
            bedrock_client=bedrock_client,
            mcp_url=resolved_url,
            max_steps_per_turn=resolved_steps,
        )
    )
