"""HTTP control plane. Workspace actions are durably delegated to the worker."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Literal
from urllib.parse import urlparse

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from pydantic_lab.application.controls import Controls
from pydantic_lab.config import Settings
from pydantic_lab.models import Policy, Session, identity
from pydantic_lab.storage.control import Conflict, ControlStore


class NewSession(BaseModel):
    repository: str
    policy: Policy | None = None
    branch: str | None = None
    commit: str | None = None
    title: str | None = None
    init_commands: list[str] = Field(default_factory=list)
    request_id: str = Field(default_factory=identity, max_length=64)


class Message(BaseModel):
    content: str
    mode: Literal["queue", "steer"] = "queue"
    request_id: str = Field(default_factory=identity, max_length=64)


class Decision(BaseModel):
    allow: bool
    request_id: str = Field(default_factory=identity, max_length=64)


class Control(BaseModel):
    request_id: str = Field(default_factory=identity, max_length=64)


class Action(Control):
    kind: Literal["trust", "start", "stop_sandbox", "rebuild", "network", "delete"]
    payload: dict = Field(default_factory=dict)


class Recovery(Control):
    action: Literal["continue", "retry", "abort"]
    confirmed: bool = False


def public_session(session: Session) -> dict:
    payload = session.model_dump(mode="json")
    payload.pop("history", None)
    for run in payload["runs"]:
        run.pop("pending_history", None)
    return payload


def create_app(settings=None, store=None):
    settings = settings or Settings.load()
    store = store or ControlStore(settings.database_url, settings.redis_url)
    controls = Controls(store)
    app = FastAPI(title="Pydantic Lab API", version="0.1.0")
    app.state.store = store

    @app.exception_handler(Conflict)
    async def conflict(_, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(KeyError)
    async def missing(_, error):
        return JSONResponse(status_code=404, content={"detail": "Session not found"})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "role": "api"}

    @app.get("/api/sessions")
    def list_sessions():
        return [
            public_session(s) for s in store.list() if s.status != "deleted" and s.mode == "server"
        ]

    @app.post("/api/sessions", status_code=202)
    def create(body: NewSession):
        parsed = urlparse(body.repository)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise Conflict("Enter a public HTTP(S) Git URL without credentials")
        if body.branch and body.commit:
            raise Conflict("Choose a branch or a commit, not both")
        if body.commit and (
            len(body.commit) != 40 or any(c not in "0123456789abcdefABCDEF" for c in body.commit)
        ):
            raise Conflict("Commit must be a full 40-character SHA")
        # A stable creation identity makes a retried form submission idempotent.
        if len(body.request_id) > 40 or not body.request_id.replace("-", "").isalnum():
            raise Conflict("Invalid request identity")
        sid = body.request_id
        try:
            existing = store.get(sid)
            return public_session(existing)
        except KeyError:
            pass
        session = Session(
            id=sid,
            title=body.title or parsed.path.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git"),
            mode="server",
            repository=body.repository,
            branch=body.branch,
            commit=body.commit,
            status="provisioning",
            init_commands=body.init_commands,
            policy=body.policy or settings.policy,
        )
        session.sandbox.image = settings.image
        try:
            store.create(session)
        except IntegrityError:
            return public_session(store.get(sid))
        return public_session(session)

    @app.get("/api/sessions/{sid}")
    def detail(sid: str):
        snapshot = store.snapshot(sid)
        snapshot["session"] = public_session(Session.model_validate(snapshot["session"]))
        snapshot["events"] = [
            e
            for e in store.replay(sid, max(0, snapshot["cursor"] - 500))
            if e["id"] <= snapshot["cursor"]
        ]
        return snapshot

    @app.post("/api/sessions/{sid}/messages", status_code=202)
    def send(sid: str, body: Message):
        return controls.send(sid, body.content, body.mode, body.request_id)

    @app.post("/api/sessions/{sid}/stop", status_code=202)
    def stop(sid: str, body: Control):
        return controls.stop(sid, body.request_id)

    @app.post("/api/sessions/{sid}/continue", status_code=202)
    def resume_queue(sid: str, body: Control):
        return controls.continue_queue(sid, body.request_id)

    @app.post("/api/sessions/{sid}/approvals/{aid}")
    def approval(sid: str, aid: str, body: Decision):
        return controls.decide(sid, aid, body.allow, body.request_id)

    @app.post("/api/sessions/{sid}/recovery")
    def recover(sid: str, body: Recovery):
        return controls.recover(sid, body.action, body.confirmed, body.request_id)

    @app.post("/api/sessions/{sid}/actions", status_code=202)
    def action(sid: str, body: Action):
        def enqueue(session, emit):
            if body.kind in {"trust", "rebuild", "network", "delete", "stop_sandbox"} and (
                session.active()
                or session.status == "provisioning"
                or any(a.status == "pending" for a in session.setup_approvals)
            ):
                raise Conflict("Stop or resolve pending execution before changing the workspace")
            if body.kind == "delete" and body.payload.get("confirmation") != "DELETE":
                raise Conflict("Type DELETE to confirm permanent workspace removal")
            if body.kind == "network" and not isinstance(body.payload.get("enabled"), bool):
                raise Conflict("Network state must be a boolean")
            if body.kind == "delete":
                session.paused = True
                session.status = "deleting"
            aid = identity()
            session.actions.append(
                {"id": aid, "kind": body.kind, "payload": body.payload, "status": "queued"}
            )
            emit("action.queued", action=body.kind, action_id=aid)
            return {"action_id": aid}

        return store.mutate(sid, enqueue, body.request_id)

    @app.get("/api/sessions/{sid}/workspace/{kind}")
    async def inspect(sid: str, kind: str, approval_id: str | None = None):
        store.get(sid)
        if kind not in {"diff", "extensions", "approval"}:
            raise Conflict("Unknown inspection")
        base = os.environ.get("LAB_AGENT_URL", "http://127.0.0.1:8001")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    f"{base}/internal/sessions/{sid}/inspect/{kind}",
                    params={"approval_id": approval_id} if approval_id else {},
                )
            return JSONResponse(status_code=response.status_code, content=response.json())
        except httpx.HTTPError:
            raise HTTPException(
                503, "Agent workspace service is unavailable; retry inspection"
            ) from None

    @app.get("/api/sessions/{sid}/events")
    async def stream(
        sid: str, request: Request, after: int = 0, last_event_id: str | None = Header(None)
    ):
        store.get(sid)
        try:
            cursor = max(after, int(last_event_id or 0))
        except ValueError:
            raise HTTPException(400, "Invalid event cursor") from None

        async def generate():
            nonlocal cursor
            idle = 0
            while not await request.is_disconnected():
                batch = await asyncio.to_thread(store.replay, sid, cursor)
                for item in batch:
                    cursor = item["id"]
                    yield f"id: {cursor}\ndata: {json.dumps(item)}\n\n"
                idle += 1
                if idle % 40 == 0:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def main():
    uvicorn.run(create_app(), host=os.environ.get("LAB_API_HOST", "127.0.0.1"), port=8000)
