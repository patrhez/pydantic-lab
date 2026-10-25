import asyncio

from pydantic_lab.models import Run
from pydantic_lab.runtime.agent import StreamRecorder


async def test_timer_flushes_short_open_block_without_more_provider_events(store, local):
    run = Run(prompt="Short stream", status="running")
    store.mutate(local.id, lambda s, e: s.runs.append(run))
    recorder = StreamRecorder(store, local.id, run.id)
    recorder.buffer = "Small unfinished paragraph"
    import time

    recorder.oldest = time.monotonic()
    recorder.timer = asyncio.create_task(recorder.tick())
    try:
        await asyncio.sleep(0.16)
        events = store.replay(local.id)
        assert [e["text"] for e in events if e["kind"] == "assistant.delta"] == [
            "Small unfinished paragraph"
        ]
        recorder.buffer = " remaining"
        await recorder.close()
        assert store.get(local.id).run(run.id).answer == "Small unfinished paragraph remaining"
    finally:
        await recorder.close()
