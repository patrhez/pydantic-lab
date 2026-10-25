"""Session transactions are the authority; Redis only reduces notification latency."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    select,
)
from sqlalchemy.engine import Connection

from pydantic_lab.models import Session

metadata = MetaData()
sessions = Table(
    "sessions",
    metadata,
    Column("id", String(40), primary_key=True),
    Column("payload", JSON, nullable=False),
)
events = Table(
    "events",
    metadata,
    Column(
        "id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    ),
    Column("session_id", String(40), index=True),
    Column("payload", JSON, nullable=False),
)
requests = Table(
    "requests",
    metadata,
    Column("id", String(180), primary_key=True),
    Column("payload", JSON, nullable=False),
)
extension_trust = Table(
    "extension_trust",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("signature", String(64), nullable=False),
)


def trust_key(repository: str, category: str) -> str:
    return hashlib.sha256(f"{repository}\0{category}".encode()).hexdigest()


T = TypeVar("T")


class Conflict(ValueError):
    pass


class ControlStore:
    def __init__(self, url: str, redis_url: str | None = None):
        kwargs = (
            {"connect_args": {"check_same_thread": False, "timeout": 30}}
            if url.startswith("sqlite")
            else {}
        )
        self.engine = create_engine(url, pool_pre_ping=True, **kwargs)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def configure(connection, _):
                connection.isolation_level = None
                connection.execute("PRAGMA journal_mode=WAL")

            @event.listens_for(self.engine, "begin")
            def begin(connection):
                connection.exec_driver_sql("BEGIN IMMEDIATE")

        metadata.create_all(self.engine)
        self.notifier = None
        if redis_url:
            import redis

            self.notifier = redis.Redis.from_url(
                redis_url, socket_connect_timeout=0.2, socket_timeout=0.2
            )

    def _log(self, session_id, kind, data):
        keys = {
            "run_id",
            "native_run_id",
            "checkpoint_id",
            "approval_id",
            "call_id",
            "tool",
            "status",
            "decision",
            "boundary",
            "duration_ms",
            "reason",
            "permission",
            "policy_revision",
        }
        logging.getLogger("pydantic_lab.events").info(
            json.dumps(
                {
                    "kind": kind,
                    "timestamp": time.time(),
                    "session_id": session_id,
                    **{k: v for k, v in data.items() if k in keys},
                }
            )
        )

    def _notify(self, session_id: str):
        if self.notifier:
            try:
                self.notifier.publish("lab.events", session_id)
            except Exception:
                pass  # Durable polling remains authoritative.

    def create(self, session: Session) -> Session:
        with self.engine.begin() as conn:
            for category in ("skills", "instructions", "mcp"):
                saved = conn.execute(
                    select(extension_trust.c.signature).where(
                        extension_trust.c.id == trust_key(session.repository, category)
                    )
                ).scalar_one_or_none()
                if saved is not None:
                    session.trust.setdefault(category, saved)
            conn.execute(
                sessions.insert().values(id=session.id, payload=session.model_dump(mode="json"))
            )
            self.emit_tx(conn, session.id, "session.created", {"title": session.title})
        self._notify(session.id)
        return session

    def list(self) -> list[Session]:
        with self.engine.connect() as conn:
            result = [
                Session.model_validate(p)
                for p in conn.execute(select(sessions.c.payload)).scalars()
            ]
        return sorted(result, key=lambda s: s.updated_at, reverse=True)

    def get(self, session_id: str) -> Session:
        with self.engine.connect() as conn:
            payload = conn.execute(
                select(sessions.c.payload).where(sessions.c.id == session_id)
            ).scalar_one_or_none()
        if payload is None:
            raise KeyError(session_id)
        return Session.model_validate(payload)

    @staticmethod
    def emit_tx(conn: Connection, session_id: str, kind: str, data: dict[str, Any]):
        payload = {"kind": kind, "timestamp": time.time(), **data}
        conn.execute(events.insert().values(session_id=session_id, payload=payload))

    def mutate(
        self, session_id: str, fn: Callable[[Session, Callable], T], request_id: str | None = None
    ) -> T:
        key = f"{session_id}:{request_id}" if request_id else None
        with self.engine.begin() as conn:
            payload = conn.execute(
                select(sessions.c.payload).where(sessions.c.id == session_id).with_for_update()
            ).scalar_one_or_none()
            if payload is None:
                raise KeyError(session_id)
            if key:
                prior = conn.execute(
                    select(requests.c.payload).where(requests.c.id == key)
                ).scalar_one_or_none()
                if prior is not None:
                    return prior
            session = Session.model_validate(payload)
            previous_trust = dict(session.trust)
            committed = []

            def emit(kind, **data):
                self.emit_tx(conn, session_id, kind, data)
                committed.append((kind, data))

            result = fn(session, emit)
            for category, signature in session.trust.items():
                if previous_trust.get(category) != signature:
                    record_id = trust_key(session.repository, category)
                    prior_trust = conn.execute(
                        select(extension_trust.c.id)
                        .where(extension_trust.c.id == record_id)
                        .with_for_update()
                    ).scalar_one_or_none()
                    if prior_trust:
                        conn.execute(
                            extension_trust.update()
                            .where(extension_trust.c.id == record_id)
                            .values(signature=signature)
                        )
                    else:
                        conn.execute(
                            extension_trust.insert().values(id=record_id, signature=signature)
                        )
            session.updated_at = time.time()
            conn.execute(
                sessions.update()
                .where(sessions.c.id == session_id)
                .values(payload=session.model_dump(mode="json"))
            )
            if key:
                conn.execute(requests.insert().values(id=key, payload=result))
        self._notify(session_id)
        for kind, data in committed:
            self._log(session_id, kind, data)
        return result

    def emit(self, session_id: str, kind: str, **data):
        with self.engine.begin() as conn:
            self.emit_tx(conn, session_id, kind, data)
        self._notify(session_id)
        self._log(session_id, kind, data)

    def replay(self, session_id: str, after: int = 0) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(events)
                .where(events.c.session_id == session_id, events.c.id > after)
                .order_by(events.c.id)
                .limit(1000)
            ).mappings()
            return [{"id": row["id"], **row["payload"]} for row in rows]

    def snapshot(self, session_id: str) -> dict:
        with self.engine.begin() as conn:
            payload = conn.execute(
                select(sessions.c.payload).where(sessions.c.id == session_id).with_for_update()
            ).scalar_one()
            cursor = (
                conn.execute(
                    select(events.c.id)
                    .where(events.c.session_id == session_id)
                    .order_by(events.c.id.desc())
                    .limit(1)
                ).scalar()
                or 0
            )
            return {"session": payload, "cursor": cursor}
