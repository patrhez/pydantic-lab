"""Transient workspace reads. Derived diffs are never written to control storage."""

from __future__ import annotations

import difflib

from pydantic_ai.workspaces import Workspace

from pydantic_lab.runtime.extensions import discover
from pydantic_lab.storage.control import Conflict


async def inspect_workspace(worker, sid, kind, approval_id=None):
    session = worker.store.get(sid)
    if session.status in {"deleted", "deleting", "provisioning"}:
        raise Conflict("Workspace inspection is unavailable in this state")
    if kind == "diff":
        return await worker.sandbox.diff(sid)
    backend = await worker.sandbox.ensure(sid)
    if kind == "extensions":
        return await discover(backend)
    approval = next((a for r in session.runs for a in r.approvals if a.id == approval_id), None)
    if not approval or approval.status != "pending":
        raise Conflict("Approval is no longer pending")
    if approval.tool not in {"edit_file", "write_file"}:
        return {"diff": "No file preview for this operation"}
    workspace = Workspace(backend)
    path = approval.arguments["path"]
    try:
        before = (await workspace.read_bytes(path)).decode("utf-8")
    except FileNotFoundError:
        before = ""
    if approval.tool == "write_file":
        after = approval.arguments["content"]
    else:
        replacements = approval.arguments.get("replacements") or [
            {
                "old_text": approval.arguments.get("old_text", ""),
                "new_text": approval.arguments.get("new_text", ""),
            }
        ]
        after = before
        for replacement in replacements:
            old, new = replacement["old_text"], replacement["new_text"]
            if not old or after.count(old) != 1:
                raise Conflict(
                    "File content changed or replacement is ambiguous; request a new edit"
                )
            after = after.replace(old, new, 1)
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
            lineterm="\n",
        )
    )
    return {"diff": diff[:100000], "truncated": len(diff) > 100000}
