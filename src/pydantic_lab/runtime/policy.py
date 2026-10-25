"""A narrow permission adapter around native tools and deferred approvals."""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import time
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import ApprovalRequired
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest, UserPromptPart
from pydantic_core import to_jsonable_python

from pydantic_lab.models import Approval, Receipt
from pydantic_lab.storage.control import Conflict, ControlStore

READ_TOOLS = {
    "read_file",
    "list_directory",
    "search_files",
    "find_files",
    "file_info",
    "load_capability",
    "inventory_agent_context",
}


def digest(tool: str, arguments: dict) -> str:
    return hashlib.sha256(
        json.dumps([tool, arguments], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def dump_messages(messages):
    return ModelMessagesTypeAdapter.dump_python(messages, mode="json")


@dataclass
class ExecutionPolicy(AbstractCapability):
    store: ControlStore
    session_id: str
    run_id: str
    max_requests: int = 40

    async def before_model_request(self, ctx, request_context):
        session = self.store.get(self.session_id)
        if session.trust:
            from pydantic_lab.runtime.extensions import discover

            found = await discover(ctx.workspace.backend)
            for category, signature in session.trust.items():
                if found.get(category, {}).get("identity") != signature:
                    raise Conflict("Repository extensions changed. Review trust before continuing.")

        def consume(session, emit):
            run = session.run(self.run_id)
            if run.stop_requested:
                raise asyncio.CancelledError()
            if run.request_count >= self.max_requests:
                raise Conflict("Logical run model-request limit reached")
            run.request_count += 1
            waiting = [item for item in run.steers if not item.consumed]
            history = list(request_context.messages)
            for item in waiting:
                history.append(ModelRequest(parts=[UserPromptPart(item.content)]))
                item.consumed = True
                emit("steer.consumed", run_id=run.id, message_id=item.id)
            run.pending_history = dump_messages(history)
            run.frontier_at = time.time()
            return history

        messages = self.store.mutate(self.session_id, consume)
        ctx.messages[:] = messages
        return replace(request_context, messages=messages)

    async def wrap_tool_execute(self, ctx, *, call, tool_def, args, handler):
        session = self.store.get(self.session_id)
        run = session.run(self.run_id)
        if run.stop_requested:
            raise asyncio.CancelledError()
        if session.trust:
            from pydantic_lab.runtime.extensions import discover

            found = await discover(ctx.workspace.backend)
            if any(found.get(k, {}).get("identity") != v for k, v in session.trust.items()):

                def expire(s, emit):
                    for pending in s.run(self.run_id).approvals:
                        if pending.status in {"pending", "allowed"}:
                            pending.status = "expired"
                            pending.reason = "Repository extension content changed"
                    emit("trust.changed", run_id=self.run_id)

                self.store.mutate(self.session_id, expire)
                return "Operation cancelled: extension content changed. Review trust before continuing."
        name = tool_def.name
        signature = digest(name, args)
        prior = run.receipts.get(call.tool_call_id)
        if prior:
            if prior.digest != signature:
                raise Conflict("A tool call ID was reused with different arguments")
            if prior.status in {"succeeded", "failed", "reconciled"}:
                return prior.result
            if prior.status in {"started", "outcome_unknown"}:
                raise Conflict("Inspect the unresolved operation before retrying")
        path = args.get("path")
        if path:
            resolved = await ctx.workspace.realpath(path)
            if not (resolved == "/workspace" or resolved.startswith("/workspace/")):
                return "Denied: path is outside the workspace."
            relative = str(PurePosixPath(resolved).relative_to("/workspace"))
            if any(fnmatch.fnmatch(relative, pattern) for pattern in session.policy.denied_paths):
                return "Denied: protected path."
        automatic = name in READ_TOOLS or any(
            fnmatch.fnmatch(name, pattern) for pattern in session.policy.auto_allow
        )
        approval = next(
            (
                a
                for a in reversed(run.approvals)
                if a.call_id == call.tool_call_id and a.digest == signature
            ),
            None,
        )
        if not automatic:
            if approval and approval.status == "expired":
                return f"Operation cancelled: {approval.reason}."
            if approval and approval.status == "rejected":
                return "The user rejected this operation."
            if approval and approval.policy_revision != session.policy.revision:
                return "Operation cancelled: policy changed."
            if not approval:
                file_hash = None
                if path and name in {"edit_file", "write_file"}:
                    try:
                        file_hash = hashlib.sha256(await ctx.workspace.read_bytes(path)).hexdigest()
                    except FileNotFoundError:
                        file_hash = "missing"
                approval = Approval(
                    call_id=call.tool_call_id,
                    tool=name,
                    arguments=args,
                    digest=signature,
                    policy_revision=session.policy.revision,
                    file_hash=file_hash,
                )

                def request(s, emit):
                    current = s.run(self.run_id)
                    if current.stop_requested or any(not i.consumed for i in current.steers):
                        approval.status = "expired"
                        approval.reason = "Run control changed the plan"
                    current.approvals.append(approval)
                    emit(
                        "approval.requested",
                        run_id=self.run_id,
                        approval=approval.model_dump(mode="json"),
                    )

                self.store.mutate(self.session_id, request)
            if approval.status != "allowed" or not ctx.tool_call_approved:
                raise ApprovalRequired()
            if approval.file_hash:
                try:
                    current_hash = hashlib.sha256(await ctx.workspace.read_bytes(path)).hexdigest()
                except FileNotFoundError:
                    current_hash = "missing"
                if current_hash != approval.file_hash:
                    return "File changed while approval was pending. Re-read it and propose a new operation."

        def started(s, emit):
            current = s.run(self.run_id)
            if current.stop_requested:
                raise asyncio.CancelledError()
            if approval:
                actual = next(a for a in current.approvals if a.id == approval.id)
                if actual.status != "allowed":
                    raise Conflict("The approval has expired")
            current.receipts[call.tool_call_id] = Receipt(
                call_id=call.tool_call_id, tool=name, digest=signature, status="started"
            )
            emit(
                "execution.started",
                run_id=self.run_id,
                call_id=call.tool_call_id,
                tool=name,
                permission="automatic" if automatic else "allow_once",
                policy_revision=session.policy.revision,
            )

        self.store.mutate(self.session_id, started)
        started_at = time.monotonic()
        try:
            result = await handler(args)
        except (ApprovalRequired, asyncio.CancelledError):
            raise
        except Exception as error:
            self._complete(
                call.tool_call_id,
                "failed",
                f"{type(error).__name__}: {str(error)[:1000]}",
                started_at,
            )
            raise
        status = "succeeded"
        if (
            name == "run_command"
            and isinstance(result, str)
            and ("[exit code:" in result or "timed out" in result.lower())
        ):
            status = "failed"
        self._complete(
            call.tool_call_id, status, to_jsonable_python(result, fallback=str), started_at
        )
        return result

    def _complete(self, call_id, status, result, started_at):
        def save(session, emit):
            receipt = session.run(self.run_id).receipts[call_id]
            receipt.status = status
            receipt.result = result
            receipt.duration_ms = int((time.monotonic() - started_at) * 1000)
            emit(
                "execution.completed",
                run_id=self.run_id,
                call_id=call_id,
                status=status,
                duration_ms=receipt.duration_ms,
                summary=str(result)[:1000],
            )

        self.store.mutate(self.session_id, save)
