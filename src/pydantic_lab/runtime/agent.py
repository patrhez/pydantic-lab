"""Compose public capabilities; Pydantic AI owns the model/tool loop."""

from __future__ import annotations

import asyncio
import time

from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPart, TextPartDelta
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import DeferredToolRequests
from pydantic_ai_harness import FileSystem, Shell, StepPersistence

from pydantic_lab.config import Settings
from pydantic_lab.runtime.compaction import LoggedCompaction
from pydantic_lab.runtime.policy import ExecutionPolicy


class StreamRecorder:
    """A timer flushes small chunks even when the provider stops sending data."""

    def __init__(self, store, sid, rid):
        self.store, self.sid, self.rid = store, sid, rid
        self.buffer = ""
        self.oldest = 0.0
        self.timer = None

    def flush(self):
        if not self.buffer:
            return
        text = self.buffer

        def save(session, emit):
            session.run(self.rid).answer += text
            emit("assistant.delta", run_id=self.rid, text=text)

        self.store.mutate(self.sid, save)
        self.buffer = ""

    async def tick(self):
        while True:
            await asyncio.sleep(0.025)
            if self.buffer and time.monotonic() - self.oldest >= 0.1:
                self.flush()

    async def __call__(self, ctx, events):
        if not self.timer:
            self.timer = asyncio.create_task(self.tick())
        async for event in events:
            text = ""
            if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                text = event.delta.content_delta
            elif isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                text = event.part.content
            if text:
                if not self.buffer:
                    self.oldest = time.monotonic()
                self.buffer += text
                if len(self.buffer.encode()) >= 2048 or "\n\n" in self.buffer:
                    self.flush()
            elif not isinstance(event, PartDeltaEvent):
                self.flush()

    async def close(self):
        if self.timer:
            self.timer.cancel()
            await asyncio.gather(self.timer, return_exceptions=True)
        self.flush()


def provider(settings: Settings):
    if settings.demo:
        from pydantic_ai.models.test import TestModel

        return TestModel(
            call_tools=[settings.demo_tool],
            custom_output_text="Demo run complete. Tools ran through the real framework loop and Docker sandbox.",
        )
    if not settings.api_key:
        raise ValueError("Configure DEEPSEEK_API_KEY before starting a run")
    return OpenAIChatModel(
        settings.model,
        provider=OpenAIProvider(base_url=settings.base_url, api_key=settings.api_key),
    )


def build_agent(settings, store, session, run, step_store, *, model=None, extensions=()):
    shell = Shell(
        tools=["run_command"],
        default_timeout=60,
        denied_env_patterns=["*KEY*", "*TOKEN*", "*SECRET*"],
        allowed_commands=session.policy.allowed_commands,
        denied_commands=[] if session.policy.allowed_commands else session.policy.denied_commands,
        denied_operators=session.policy.denied_operators,
        max_output_chars=64000,
        max_file_bytes=20_000_000,
    )
    from pydantic_ai.toolsets import AbstractToolset

    toolsets = [item for item in extensions if isinstance(item, AbstractToolset)]
    capabilities = [
        ExecutionPolicy(
            store=store, session_id=session.id, run_id=run.id, max_requests=settings.request_limit
        ),
        FileSystem(root_dir="/workspace", denied_patterns=session.policy.denied_paths),
        shell,
        LoggedCompaction(
            model=model or provider(settings),
            max_tokens=settings.compaction_tokens,
            keep_messages=6,
            receipts=False,
            store=store,
            session_id=session.id,
            logical_run_id=run.id,
        ),
        StepPersistence(store=step_store, capture_frontier=True),
        *[item for item in extensions if not isinstance(item, AbstractToolset)],
    ]
    return Agent(
        model or provider(settings),
        output_type=[str, DeferredToolRequests],
        name="coding_agent",
        capabilities=capabilities,
        toolsets=toolsets,
        instructions="You are a coding agent. Work only in /workspace. Read files before editing. Use the supplied file and command tools. Respect refusals and changed-file conflicts. Explain changes and tests briefly. Do not delegate to other agents. Never claim an operation ran without a tool result.",
        model_settings={
            "parallel_tool_calls": False,
            "extra_body": {"thinking": {"type": "disabled"}},
        }
        if not settings.demo and model is None
        else None,
    )
