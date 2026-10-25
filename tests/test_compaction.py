from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel
from pydantic_ai_harness import StepPersistence
from pydantic_ai_harness.step_persistence import InMemoryStepStore, is_provider_valid

from pydantic_lab.models import Run
from pydantic_lab.runtime.compaction import LoggedCompaction


async def test_native_compaction_logs_estimates_and_keeps_valid_protocol(store, local):
    run = Run(prompt="Continue")
    store.mutate(local.id, lambda s, e: s.runs.append(run))
    history = []
    for i in range(12):
        history.extend(
            [
                ModelRequest(parts=[UserPromptPart(f"Question {i}: " + ("details " * 20))]),
                ModelResponse(
                    parts=[
                        ToolCallPart("read_file", {"path": "sample.py"}, tool_call_id=f"read-{i}")
                    ]
                ),
                ModelRequest(
                    parts=[ToolReturnPart("read_file", "sample content", tool_call_id=f"read-{i}")]
                ),
                ModelResponse(parts=[TextPart(f"Answer {i}")]),
            ]
        )
    steps = InMemoryStepStore()
    capability = LoggedCompaction(
        store=store,
        session_id=local.id,
        logical_run_id=run.id,
        model=TestModel(custom_output_text="Preserved task summary"),
        max_messages=8,
        keep_messages=4,
    )
    agent = Agent(
        TestModel(custom_output_text="Continued"),
        capabilities=[capability, StepPersistence(store=steps, capture_frontier=True)],
    )
    result = await agent.run("Continue", message_history=history, conversation_id=local.id)
    assert len(result.all_messages()) < len(history)
    assert is_provider_valid(result.all_messages())
    assert len(history) == 48
    records = [e for e in store.replay(local.id) if e["kind"] == "compaction.completed"]
    assert records and records[0]["estimated"]
    assert records[0]["after"] < records[0]["before"]
