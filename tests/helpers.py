"""Deterministic providers that exercise the real framework graph."""

import asyncio

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel


def one_tool(name, arguments, *, output="Done", call_id="operation-1", pause_after_tool=0):
    def response(messages, info):
        if any(
            getattr(part, "part_kind", None) == "tool-return"
            and getattr(part, "tool_call_id", None) == call_id
            for message in messages
            for part in message.parts
        ):
            return ModelResponse(parts=[TextPart(output)])
        return ModelResponse(parts=[ToolCallPart(name, arguments, tool_call_id=call_id)])

    async def stream(messages, info):
        result = response(messages, info)
        if pause_after_tool and any(isinstance(p, TextPart) for p in result.parts):
            await asyncio.sleep(pause_after_tool)
        for part in result.parts:
            if isinstance(part, TextPart):
                yield part.content
            else:
                yield {
                    0: DeltaToolCall(
                        name=part.tool_name,
                        json_args=part.args_as_json_str(),
                        tool_call_id=part.tool_call_id,
                    )
                }

    return FunctionModel(response, stream_function=stream)
