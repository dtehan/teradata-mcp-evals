"""Multi-turn MCP agent that drives tool selection via Bedrock Claude."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

import boto3
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@dataclass
class ToolCallRecord:
    name: str
    input_parameters: dict[str, Any]


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


async def _run_agent_async(
    prompt: str,
    model_id: str,
    bedrock_client,
    mcp_url: str,
    max_steps: int,
) -> AgentResult:
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            bedrock_tools = [_mcp_tool_to_bedrock(t) for t in tools_response.tools]

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
                    tool_results = []
                    for block in output_message["content"]:
                        if block.get("type") != "toolUse":
                            continue
                        tool_name = block["name"]
                        tool_input = block["input"]
                        tool_use_id = block["toolUseId"]

                        tool_calls_made.append(
                            ToolCallRecord(name=tool_name, input_parameters=tool_input)
                        )

                        try:
                            mcp_result = await session.call_tool(tool_name, tool_input)
                            result_text = json.dumps(
                                [c.model_dump() for c in mcp_result.content],
                                default=str,
                            )
                        except Exception as exc:
                            result_text = f"Tool error: {exc}"

                        tool_results.append(
                            {
                                "toolResult": {
                                    "toolUseId": tool_use_id,
                                    "content": [{"text": result_text}],
                                }
                            }
                        )

                    messages.append({"role": "user", "content": tool_results})

                else:
                    for block in output_message["content"]:
                        if block.get("type") == "text":
                            final_response += block["text"]
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
