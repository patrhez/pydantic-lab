from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai_harness import StepPersistence

from pydantic_lab.storage.steps import DatabaseStepStore


async def test_database_store_drives_real_native_checkpoints(store, local):
    steps = DatabaseStepStore(store, local.id)
    agent = Agent(
        TestModel(custom_output_text="Saved"),
        capabilities=[StepPersistence(store=steps, capture_frontier=True)],
    )
    result = await agent.run("Remember this", conversation_id=local.id)
    runs = await steps.list_runs(conversation_id=local.id)
    assert len(runs) == 1
    snapshot = await steps.latest_snapshot(run_id=runs[0].run_id)
    assert snapshot and snapshot.state == "complete"
    assert snapshot.messages == result.all_messages()
    await steps.save_snapshot(snapshot)
    assert len(await steps.list_snapshots(run_id=runs[0].run_id)) >= 1


async def test_sqlite_duplicate_keys_keep_events_and_replace_effect_results(store, local):
    from dataclasses import replace

    import pytest
    from pydantic_ai_harness.step_persistence import RunRecord, StepEvent, ToolEffectRecord

    steps = DatabaseStepStore(store, local.id)
    run = RunRecord(run_id="duplicate-test")
    await steps.register_run(run)
    with pytest.raises(ValueError, match="already exists"):
        await steps.register_run(run)
    event = StepEvent(
        run_id=run.run_id,
        kind="tool_call_completed",
        step_index=1,
        idempotency_key="completion",
        tool_name="read_file",
    )
    await steps.append_event(event)
    await steps.append_event(replace(event, tool_name="write_file"))
    assert [e.tool_name for e in await steps.list_events(run_id=run.run_id)] == ["read_file"]
    # No idempotency identity means append, even when two payloads match.
    await steps.append_event(replace(event, idempotency_key=None))
    await steps.append_event(replace(event, idempotency_key=None))
    assert len(await steps.list_events(run_id=run.run_id)) == 3
    effect = ToolEffectRecord(
        run_id=run.run_id, tool_call_id="call", tool_name="write_file", status="started"
    )
    await steps.record_tool_effect(effect)
    await steps.record_tool_effect(replace(effect, status="completed"))
    assert (
        await steps.get_tool_effect(run_id=run.run_id, tool_call_id="call")
    ).status == "completed"
    assert not await steps.list_unresolved_tool_effects(run_id=run.run_id)
