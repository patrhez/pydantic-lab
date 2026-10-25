"""Opt-in concurrency regression against a real MySQL database.

Set LAB_TEST_DATABASE_URL to a reachable MySQL URL. Tests use unique run IDs
and remove only their own framework records. No model requests are made.
"""

import asyncio
import os
from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic_ai_harness.step_persistence import RunRecord, StepEvent, ToolEffectRecord
from sqlalchemy import delete

from pydantic_lab.storage.control import ControlStore
from pydantic_lab.storage.steps import DatabaseStepStore, records

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("LAB_TEST_DATABASE_URL"),
        reason="Set LAB_TEST_DATABASE_URL for real MySQL concurrency tests",
    ),
]


@pytest.fixture
def mysql_stores():
    url = os.environ["LAB_TEST_DATABASE_URL"]
    assert url.startswith("mysql"), "This regression requires MySQL, not SQLite"
    controls = [ControlStore(url) for _ in range(3)]
    stores = [DatabaseStepStore(control, "concurrency-test") for control in controls]
    run_ids = []
    yield stores, run_ids
    with controls[0].engine.begin() as conn:
        conn.execute(delete(records).where(records.c.run_id.in_(run_ids)))
    for control in controls:
        control.engine.dispose()


async def test_mysql_concurrent_event_inserts_preserve_unique_records(mysql_stores):
    stores, run_ids = mysql_stores
    for _ in range(6):
        run_id = uuid4().hex
        run_ids.append(run_id)
        await stores[0].register_run(RunRecord(run_id=run_id))
        batch = [
            StepEvent(
                run_id=run_id,
                kind="tool_call_completed",
                step_index=1,
                tool_call_id=f"call-{i}",
                tool_name="find_files",
                idempotency_key=f"completed-{i}",
            )
            for i in range(48)
        ]
        # Different adapters and connections must safely insert new and repeated keys.
        results = await asyncio.gather(
            *(stores[i % 3].append_event(event) for i, event in enumerate(batch * 2)),
            return_exceptions=True,
        )
        assert not [result for result in results if isinstance(result, Exception)], results
        saved = await stores[0].list_events(run_id=run_id)
        assert len(saved) == len(batch)
        assert {e.tool_call_id for e in saved} == {e.tool_call_id for e in batch}
        await stores[1].append_event(replace(batch[0], tool_name="write_file"))
        assert all(e.tool_name == "find_files" for e in await stores[0].list_events(run_id=run_id))


async def test_mysql_effect_updates_and_run_identity_contract(mysql_stores):
    stores, run_ids = mysql_stores
    run_id = uuid4().hex
    run_ids.append(run_id)
    run = RunRecord(run_id=run_id)
    await stores[0].register_run(run)
    with pytest.raises(ValueError, match="already exists"):
        await stores[1].register_run(run)
    effect = ToolEffectRecord(
        run_id=run_id, tool_call_id="effect", tool_name="write_file", status="started"
    )
    await stores[0].record_tool_effect(effect)
    await stores[1].record_tool_effect(replace(effect, status="completed"))
    saved = await stores[2].get_tool_effect(run_id=run_id, tool_call_id="effect")
    assert saved.status == "completed"
    assert not await stores[2].list_unresolved_tool_effects(run_id=run_id)


async def test_mysql_native_parallel_tool_loops_and_snapshot_deduplication(mysql_stores):
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai_harness import StepPersistence

    def model(messages, info):
        if any(isinstance(part, ToolReturnPart) for message in messages for part in message.parts):
            return ModelResponse(parts=[TextPart("Done")])
        return ModelResponse(
            parts=[
                ToolCallPart("echo", {"value": str(i)}, tool_call_id=f"call-{i}") for i in range(12)
            ]
        )

    async def echo(value: str) -> str:
        await asyncio.sleep(0)
        return value

    stores, run_ids = mysql_stores

    async def execute(index):
        run_id = uuid4().hex
        run_ids.append(run_id)
        steps = stores[index % len(stores)]
        agent = Agent(
            FunctionModel(model),
            tools=[echo],
            capabilities=[StepPersistence(store=steps, capture_frontier=True)],
        )
        result = await agent.run("Run parallel tools", run_id=run_id)
        assert result.output == "Done"
        events = await steps.list_events(run_id=run_id)
        assert len([e for e in events if e.kind == "tool_call_completed"]) == 12
        snapshots = await steps.list_snapshots(run_id=run_id)
        snapshot = await steps.latest_snapshot(run_id=run_id)
        assert snapshot and snapshot.messages == result.all_messages()
        await asyncio.gather(*(store.save_snapshot(snapshot) for store in stores))
        assert len(await steps.list_snapshots(run_id=run_id)) == len(snapshots)

    results = await asyncio.gather(*(execute(i) for i in range(4)), return_exceptions=True)
    assert not [r for r in results if isinstance(r, Exception)], results
