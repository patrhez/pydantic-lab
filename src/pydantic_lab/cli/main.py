"""Inline terminal interface with input independent of the running agent."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
import shlex
import sys
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from pydantic_lab.application.controls import Controls
from pydantic_lab.application.runner import Runner
from pydantic_lab.config import Settings
from pydantic_lab.models import Policy, Session, identity
from pydantic_lab.runtime.extensions import discover
from pydantic_lab.sandbox.manager import SandboxManager
from pydantic_lab.storage.control import Conflict, ControlStore


def parser():
    p = argparse.ArgumentParser(description="A coding agent in a Docker workspace")
    p.add_argument("prompt", nargs="*")
    p.add_argument("--workspace", type=Path, default=Path.cwd())
    p.add_argument("--state-dir", type=Path, default=Path.home() / ".local/share/pydantic-lab")
    p.add_argument("--policy", type=Path)
    p.add_argument("--image", default=None)
    p.add_argument("--demo", action="store_true")
    p.add_argument(
        "--demo-tool", choices=["list_directory", "write_file"], default="list_directory"
    )
    return p


async def run(args):
    os.environ["PYDANTIC_AI_NO_BANNER"] = "1"
    os.environ["LAB_STATE_DIR"] = str(args.state_dir.resolve())
    settings = Settings.load()
    settings.demo = args.demo
    settings.demo_tool = args.demo_tool
    store = ControlStore(settings.database_url)
    controls = Controls(store)
    manager = SandboxManager(store)
    repository = str(args.workspace.resolve())
    console = Console(no_color=bool(os.environ.get("NO_COLOR")) or os.environ.get("TERM") == "dumb")
    resume = args.prompt and args.prompt[0] == "resume"
    if resume:
        candidates = [
            s
            for s in store.list()
            if s.mode == "local"
            and s.repository == repository
            and (s.active() or s.paused or any(r.status == "queued" for r in s.runs))
        ]
        wanted = args.prompt[1] if len(args.prompt) > 1 else None
        if not wanted and len(candidates) != 1:
            for s in candidates:
                console.print(f"{s.id}  {s.status}  {s.title}")
            console.print("Choose: pydantic-lab resume <session_id>")
            return 2
        session = store.get(wanted) if wanted else candidates[0]
        if session.mode != "local" or session.repository != repository:
            raise Conflict("Session belongs to another workspace")
    else:
        session = Session(
            title=Path(repository).name, mode="local", repository=repository, initialized=True
        )
        session.sandbox.image = args.image or settings.image
        session.policy = (
            Policy.model_validate_json(args.policy.read_text()) if args.policy else settings.policy
        )
        store.create(session)
    sid = session.id
    lock = (settings.state_dir / f"{sid}.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    runner = Runner(settings, store, manager, detach_on_approval=not interactive)
    mode = "queue"
    last_interrupt = 0.0
    cursor = store.snapshot(sid)["cursor"] if resume else 0
    task = None
    running = True
    draft = ""
    console.print(f"Pydantic Lab | session {sid} | {repository}")

    def render_events():
        nonlocal cursor
        for item in store.replay(sid, cursor):
            cursor = item["id"]
            kind = item["kind"]
            if kind == "assistant.delta":
                console.print(item["text"], end="", markup=False, highlight=False)
            elif kind == "approval.requested":
                a = item["approval"]
                console.print(f"\n[approval {a['id']}] {a['tool']}", markup=False)
                console.print(json.dumps(a["arguments"], indent=2), markup=False)
                console.print("/allow <id> | /reject <id> | /diff", markup=False)
            elif kind != "sandbox.attached":
                data = {
                    k: v for k, v in item.items() if k not in {"id", "timestamp", "kind", "text"}
                }
                console.print(f"\n[{kind}] {json.dumps(data)[:1500]}", markup=False)

    if resume:
        for run in session.runs:
            for approval in run.approvals:
                if approval.status == "pending":
                    console.print(f"Pending approval {approval.id}: {approval.tool}")
                    console.print(json.dumps(approval.arguments, indent=2), markup=False)
                    console.print("/allow <id> | /reject <id> | /diff")

    async def scheduler():
        nonlocal task
        while running:
            current = store.get(sid)
            if not task or task.done():
                if task:
                    await task
                active = current.active()
                eligible = active if active and active.status != "outcome_unknown" else None
                if not interactive and active and active.status == "awaiting_approval":
                    eligible = None
                if not eligible and not current.paused and not active:
                    eligible = next((r for r in current.runs if r.status == "queued"), None)
                if eligible:
                    task = asyncio.create_task(runner.execute(sid, eligible.id))
            render_events()
            await asyncio.sleep(0.1)

    async def command(text):
        nonlocal mode
        current = store.get(sid)
        words = text.split()
        name = words[0]
        if name in {"/allow", "/reject"}:
            approvals = [a for r in current.runs for a in r.approvals if a.status == "pending"]
            requested = (
                words[1] if len(words) > 1 else approvals[0].id if len(approvals) == 1 else None
            )
            if not requested:
                raise Conflict("Specify one pending approval ID")
            controls.decide(sid, requested, name == "/allow", identity())
        elif name == "/stop":
            controls.stop(sid, identity())
        elif name in {"/continue", "/retry", "/abort"}:
            active = current.active()
            if active and active.status == "outcome_unknown":
                console.print("The first attempt may have changed files. No rollback is available.")
                confirmation = await prompt.prompt_async("Type CONFIRM after inspection: ")
                controls.recover(
                    sid,
                    {"/continue": "continue", "/retry": "retry", "/abort": "abort"}[name],
                    confirmation == "CONFIRM",
                    identity(),
                )
            elif name == "/continue":
                controls.continue_queue(sid, identity())
            else:
                raise Conflict("No unknown operation to resolve")
        elif name == "/diff":
            console.print(json.dumps(await manager.diff(sid), indent=2), markup=False)
        elif name == "/trust":
            if current.active():
                raise Conflict("Finish or Stop the run before changing trust")
            found = await discover(await manager.ensure(sid))
            for category, package in found.items():
                console.print(f"{category}: {', '.join(package['files'])}", markup=False)
                for path, content in package["contents"].items():
                    console.print(f"\n{path}\n{content}", markup=False)
                response = await prompt.prompt_async(f"Type TRUST {category} to activate: ")
                if response == f"TRUST {category}":
                    store.mutate(
                        sid,
                        lambda s, e: (
                            s.trust.update({category: package["identity"]}),
                            e("trust.granted", category=category),
                        ),
                    )
        else:
            raise Conflict(
                "Unknown command. Use /allow, /reject, /diff, /trust, /stop, or /continue"
            )

    keys = KeyBindings()

    @keys.add("tab")
    def toggle(event):
        nonlocal mode
        active = store.get(sid).active()
        if active and not active.stop_requested:
            mode = "steer" if mode == "queue" else "queue"

    @keys.add("c-c")
    def interrupt(event):
        nonlocal last_interrupt
        now = time.monotonic()
        active = store.get(sid).active()
        buffer = event.app.current_buffer
        if active and active.status != "outcome_unknown":
            if now - last_interrupt < 3:
                event.app.exit(exception=KeyboardInterrupt())
            else:
                controls.stop(sid, identity())
                last_interrupt = now
                event.app.invalidate()
        elif not active and buffer.text:
            buffer.reset()
            console.print("Draft cleared")
            last_interrupt = now
        else:
            event.app.exit(exception=KeyboardInterrupt())

    prompt = PromptSession(key_bindings=keys) if interactive else None
    scheduler_task = asyncio.create_task(scheduler())
    try:
        initial = " ".join(args.prompt) if not resume else ""
        if not interactive:
            if not initial and not resume:
                initial = sys.stdin.read().strip()
            if initial:
                controls.send(sid, initial, "queue", identity())
            elif not resume:
                raise Conflict("Provide a prompt or use resume")
            async with asyncio.timeout(600):
                while True:
                    await asyncio.sleep(0.15)
                    current = store.get(sid)
                    active = current.active()
                    if active and active.status == "awaiting_approval" and task and task.done():
                        resume_command = [
                            "pydantic-lab",
                            "--workspace",
                            repository,
                            "--state-dir",
                            str(settings.state_dir),
                        ]
                        if settings.demo:
                            resume_command.extend(["--demo", "--demo-tool", settings.demo_tool])
                        resume_command.extend(["resume", sid])
                        render_events()
                        console.print("\n" + shlex.join(resume_command), markup=False)
                        return 3
                    if active and active.status == "outcome_unknown":
                        console.print(f"Inspect the workspace, then resume {sid}")
                        return 4
                    if current.runs and all(
                        r.status in {"completed", "failed", "cancelled"} for r in current.runs
                    ):
                        return 0 if current.runs[-1].status == "completed" else 1
        if initial:
            controls.send(sid, initial, "queue", identity())
        with patch_stdout():
            while True:
                try:
                    current = store.get(sid)
                    active = current.active()
                    shown_mode = mode if active and not active.stop_requested else "queue"

                    def prompt_label():
                        latest = store.get(sid)
                        active_now = latest.active()
                        visible_mode = (
                            mode if active_now and not active_now.stop_requested else "queue"
                        )
                        queued = sum(r.status == "queued" for r in latest.runs)
                        return f"{latest.status} | queued:{queued} | {latest.sandbox.state} | {visible_mode} > "

                    text = await prompt.prompt_async(prompt_label, default=draft)
                    draft = text
                    if not text.strip():
                        continue
                    if text.startswith("/"):
                        await command(text)
                    elif active and active.status == "outcome_unknown":
                        console.print("Inspect with /diff; choose /continue, /retry, or /abort.")
                    else:
                        controls.send(sid, text, shown_mode, identity())
                    draft = ""
                except KeyboardInterrupt:
                    now = time.monotonic()
                    current = store.get(sid)
                    if (
                        now - last_interrupt < 3
                        or not current.active()
                        or current.active().status == "outcome_unknown"
                    ):
                        break
                    controls.stop(sid, identity())
                    last_interrupt = now
                except EOFError:
                    if not store.get(sid).active():
                        break
                    console.print("Use /stop before exiting an active run.")
                except (Conflict, ValueError) as error:
                    console.print(str(error), markup=False)
    finally:
        running = False
        scheduler_task.cancel()
        await asyncio.gather(scheduler_task, return_exceptions=True)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        render_events()
        if not store.get(sid).active() or not interactive:
            await manager.stop(sid)
        lock.close()
    return 0


def main():
    try:
        raise SystemExit(asyncio.run(run(parser().parse_args())))
    except (Conflict, ValueError, BlockingIOError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
