"""Real noninteractive and pseudo-terminal checks against a bind-mounted workspace."""

import asyncio
import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time

import pytest

from pydantic_lab.sandbox.manager import SandboxManager
from pydantic_lab.storage.control import ControlStore


@pytest.mark.integration
def test_noninteractive_approval_and_narrow_terminal_resume(tmp_path):
    state, workspace = tmp_path / "state", tmp_path / "workspace"
    state.mkdir()
    workspace.mkdir()
    env = {
        **os.environ,
        "NO_COLOR": "1",
        "TERM": "dumb",
        "LAB_DATABASE_URL": f"sqlite:///{state / 'control.db'}",
    }
    base = [
        sys.executable,
        "-c",
        "from pydantic_lab.cli.main import main; main()",
        "--workspace",
        str(workspace),
        "--state-dir",
        str(state),
        "--demo",
        "--demo-tool",
        "write_file",
    ]
    result = subprocess.run(
        [*base, "Write a file"], input="", capture_output=True, text=True, env=env, timeout=40
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "--state-dir" in result.stdout and "approval" in result.stdout
    assert not (workspace / "a").exists()
    store = ControlStore(env["LAB_DATABASE_URL"])
    session = store.list()[0]
    approval = session.runs[0].approvals[0]
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 70, 0, 0))
    process = subprocess.Popen(
        [*base, "resume", session.id],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env=env,
        start_new_session=True,
    )
    os.close(slave)
    transcript = ""

    def until(text):
        nonlocal transcript
        deadline = time.monotonic() + 30
        while text not in transcript and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    transcript += os.read(master, 65536).decode(errors="replace")
                except OSError:
                    break
        assert text in transcript, transcript

    try:
        until("Pending approval")
        os.write(master, f"/allow {approval.id}\n".encode())
        until("run.completed")
        assert (workspace / "a").read_text() == "a"
        os.write(master, b"\x04")
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        asyncio.run(SandboxManager(store).destroy(session.id))
