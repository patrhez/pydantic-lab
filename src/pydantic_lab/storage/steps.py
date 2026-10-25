"""MySQL implementation of the public native StepStore contract."""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Any

from pydantic import TypeAdapter
from pydantic_ai_harness.step_persistence import (
    ContinuableSnapshot,
    RunRecord,
    StepEvent,
    ToolEffectRecord,
)
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from pydantic_lab.storage.control import ControlStore

meta = MetaData()
records = Table(
    "framework_records",
    meta,
    Column(
        "seq", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    ),
    Column("category", String(20), nullable=False),
    Column("run_id", String(200), nullable=False, index=True),
    Column("record_key", String(200), nullable=True),
    Column("payload", JSON, nullable=False),
    UniqueConstraint("category", "run_id", "record_key"),
)
TYPES = {
    "run": RunRecord,
    "event": StepEvent,
    "snapshot": ContinuableSnapshot,
    "effect": ToolEffectRecord,
}


class DatabaseStepStore:
    """Store native dataclasses as validated JSON without replacing checkpoint semantics."""

    def __init__(self, control: ControlStore, session_id: str):
        self.control = control
        self.session_id = session_id
        meta.create_all(control.engine)

    async def _write(self, category: str, record: Any, key: str | None, replace: bool = False):
        adapter = TypeAdapter(TYPES[category])
        payload = adapter.dump_python(record, mode="json")

        values = dict(category=category, run_id=record.run_id, record_key=key, payload=payload)
        if category == "run":
            statement = records.insert().values(**values)
        elif self.control.engine.dialect.name == "mysql":
            statement = mysql_insert(records).values(**values)
            statement = statement.on_duplicate_key_update(
                payload=statement.inserted.payload if replace else records.c.payload
            )
        elif self.control.engine.dialect.name == "sqlite":
            statement = sqlite_insert(records).values(**values)
            conflict = dict(index_elements=["category", "run_id", "record_key"])
            statement = (
                statement.on_conflict_do_update(
                    **conflict, set_={"payload": statement.excluded.payload}
                )
                if replace
                else statement.on_conflict_do_nothing(**conflict)
            )
        else:
            raise ValueError("StepStore supports MySQL and SQLite")

        def write():
            try:
                with self.control.engine.begin() as conn:
                    # Let the unique constraint arbitrate inserts. Locking a missing
                    # row first takes an InnoDB gap lock and can deadlock peer writers.
                    conn.execute(statement)
            except IntegrityError as error:
                duplicate = (
                    getattr(error.orig, "args", (None,))[0] == 1062
                    or getattr(error.orig, "sqlite_errorcode", None)
                    == sqlite3.SQLITE_CONSTRAINT_UNIQUE
                )
                if category == "run" and duplicate:
                    raise ValueError("Framework run identity already exists") from error
                raise

        await asyncio.to_thread(write)

    async def _read(self, category: str, run_id: str | None = None):
        def read():
            with self.control.engine.connect() as conn:
                query = (
                    select(records.c.payload)
                    .where(records.c.category == category)
                    .order_by(records.c.seq)
                )
                if run_id:
                    query = query.where(records.c.run_id == run_id)
                return [
                    TypeAdapter(TYPES[category]).validate_python(p)
                    for p in conn.execute(query).scalars()
                ]

        return await asyncio.to_thread(read)

    async def register_run(self, record: RunRecord):
        await self._write("run", record, record.run_id)

    async def get_run(self, *, run_id: str):
        rows = await self._read("run", run_id)
        return rows[0] if rows else None

    async def list_runs(self, *, parent_run_id=None, conversation_id=None):
        rows = await self._read("run")
        return sorted(
            [
                r
                for r in rows
                if (parent_run_id is None or r.parent_run_id == parent_run_id)
                and (conversation_id is None or r.conversation_id == conversation_id)
            ],
            key=lambda r: r.started_at,
        )

    async def append_event(self, event: StepEvent):
        await self._write("event", event, event.idempotency_key)

    async def list_events(self, *, run_id: str):
        return await self._read("event", run_id)

    async def save_snapshot(self, snapshot: ContinuableSnapshot):
        await self._write("snapshot", snapshot, snapshot.idempotency_key)

    async def list_snapshots(self, *, run_id: str, include_interrupted=False):
        rows = await self._read("snapshot", run_id)
        return [s for s in rows if include_interrupted or s.state == "complete"]

    async def latest_snapshot(self, *, run_id: str, include_interrupted=False):
        rows = await self.list_snapshots(run_id=run_id, include_interrupted=include_interrupted)
        return rows[-1] if rows else None

    async def record_tool_effect(self, record: ToolEffectRecord):
        await self._write("effect", record, record.tool_call_id, replace=True)

    async def get_tool_effect(self, *, run_id: str, tool_call_id: str):
        return next(
            (r for r in await self._read("effect", run_id) if r.tool_call_id == tool_call_id), None
        )

    async def list_unresolved_tool_effects(self, *, run_id: str):
        return [r for r in await self._read("effect", run_id) if r.status == "started"]


class ObservedStepStore:
    """Delegate storage to the framework backend and log committed boundaries."""

    def __init__(self, native, control, session_id, logical_run_id):
        self.native = native
        self.control = control
        self.session_id = session_id
        self.logical_run_id = logical_run_id

    def __getattr__(self, name):
        return getattr(self.native, name)

    async def save_snapshot(self, snapshot):
        await self.native.save_snapshot(snapshot)
        self.control.emit(
            self.session_id,
            "checkpoint.saved",
            run_id=self.logical_run_id,
            native_run_id=snapshot.run_id,
            checkpoint_id=snapshot.idempotency_key,
            boundary=snapshot.state,
            step=snapshot.step_index,
        )
