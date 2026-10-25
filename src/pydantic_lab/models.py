"""Application records. Framework messages stay in their native serialized format."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def identity() -> str:
    return uuid.uuid4().hex


class Policy(BaseModel):
    revision: str = "1"
    auto_allow: list[str] = Field(default_factory=list)
    allowed_commands: list[str] = Field(default_factory=list)
    denied_commands: list[str] = Field(
        default_factory=lambda: ["rm", "rmdir", "mkfs", "dd", "shutdown", "reboot"]
    )
    denied_operators: list[str] = Field(
        default_factory=lambda: [";", "&&", "||", "|", ">", "<", "`", "$("]
    )
    denied_paths: list[str] = Field(
        default_factory=lambda: [".env*", "**/.env*", "*.pem", "*.key", "**/secrets*"]
    )

    @model_validator(mode="after")
    def check_command_mode(self):
        if self.allowed_commands and self.denied_commands:
            raise ValueError("Choose allowed_commands or denied_commands, not both")
        return self


class Approval(BaseModel):
    id: str = Field(default_factory=identity)
    call_id: str
    tool: str
    arguments: dict[str, Any]
    digest: str
    policy_revision: str
    status: Literal["pending", "allowed", "rejected", "expired"] = "pending"
    reason: str = "Default approval policy"
    file_hash: str | None = None
    created_at: float = Field(default_factory=time.time)
    setup: bool = False


class Receipt(BaseModel):
    call_id: str
    tool: str
    digest: str
    status: Literal["started", "succeeded", "failed", "outcome_unknown", "reconciled"]
    result: Any = None
    started_at: float = Field(default_factory=time.time)
    duration_ms: int | None = None


class Input(BaseModel):
    id: str = Field(default_factory=identity)
    content: str
    consumed: bool = False


class Run(BaseModel):
    id: str = Field(default_factory=identity)
    prompt: str
    status: str = "queued"
    native_ids: list[str] = Field(default_factory=list)
    request_count: int = 0
    pending_history: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    receipts: dict[str, Receipt] = Field(default_factory=dict)
    steers: list[Input] = Field(default_factory=list)
    frontier_at: float = 0
    stop_requested: bool = False
    answer: str = ""
    error: str | None = None
    owner: str | None = None
    created_at: float = Field(default_factory=time.time)


class SandboxBinding(BaseModel):
    id: str = Field(default_factory=identity)
    container: str | None = None
    volume: str | None = None
    image: str = "pydantic-lab-sandbox:local"
    network: bool = False
    state: str = "stopped"
    last_used: float = Field(default_factory=time.time)


class Session(BaseModel):
    id: str = Field(default_factory=identity)
    title: str
    mode: Literal["local", "server"]
    repository: str
    branch: str | None = None
    commit: str | None = None
    status: str = "ready"
    initialized: bool = False
    init_commands: list[str] = Field(default_factory=list)
    init_completed: int = 0
    clone_completed: bool = False
    setup_receipts: dict[str, Receipt] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    inspection: dict[str, Any] = Field(default_factory=dict)
    setup_approvals: list[Approval] = Field(default_factory=list)
    sandbox: SandboxBinding = Field(default_factory=SandboxBinding)
    policy: Policy = Field(default_factory=Policy)
    paused: bool = False
    runs: list[Run] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    trust: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    updated_at: float = Field(default_factory=time.time)

    def active(self) -> Run | None:
        return next(
            (
                r
                for r in self.runs
                if r.status in {"running", "awaiting_approval", "outcome_unknown"}
            ),
            None,
        )

    def run(self, run_id: str) -> Run:
        return next(r for r in self.runs if r.id == run_id)
