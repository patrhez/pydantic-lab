# Implementation Status

Status date: 2026-10-25. The core CLI and Web paths run with real Docker tools and pinned public Pydantic APIs.

## Implemented behavior

| Area | Evidence |
| --- | --- |
| Native Agent loop and deferred approval | [Agent composition](../src/pydantic_lab/runtime/agent.py), [runtime tests](../tests/test_runtime.py) |
| Concurrent MySQL events, native parallel tools, and idempotent records | [MySQL regression tests](../tests/test_steps_mysql.py) |
| Native CLI SQLite checkpoints and MySQL StepStore | [Storage adapter](../src/pydantic_lab/storage/steps.py), [StepStore test](../tests/test_steps.py), service smoke |
| Exact approvals, auto-allow, protected paths, failed receipts | [Policy tests](../tests/test_policy.py) |
| Queue, Steer, Stop, Continue, and duplicate requests | [Control tests](../tests/test_controls.py), [worker tests](../tests/test_worker.py) |
| Pending approval, settled result, and uncertain-effect recovery | [SIGKILL tests](../tests/test_recovery.py), [runtime tests](../tests/test_runtime.py) |
| Real bind mount, dependency separation, persistent server volume | [Sandbox tests](../tests/test_sandbox.py) |
| Native Skills, RepoContext, trust hashes, stdio and HTTP MCP | [Extension tests](../tests/test_extensions.py) |
| Native summarization with valid tool-call/result history | [Compaction test](../tests/test_compaction.py) |
| Timed streaming commits and residual flush | [Stream test](../tests/test_stream.py) |
| API validation, setup approval, and control separation | [API tests](../tests/test_api.py) |
| Transient proposed edit preview | [Inspection test](../tests/test_inspection.py) |
| Noninteractive approval and narrow terminal resume | [CLI PTY test](../tests/test_cli.py) |
| Independent deployments, MySQL continuation, Redis loss, SSE replay | [Service smoke](../scripts/service_smoke.py) |
| Web creation, setup, focus, draft, approval, diff, replay, narrow layout | [Browser smoke](../scripts/browser_smoke.py), [UI tests](../frontend/src/interactions.test.tsx) |
| Real DeepSeek read and deferred edit | [Live tests](../tests/test_live.py) |

## Observed results

The Python suite, frontend build, service smoke, browser smoke, and live provider tests have run on this machine.

- Python: `uv run pytest -q` reports **31 passed, 5 skipped**. Two skips are paid provider tests; three require an explicit MySQL test URL.
- Frontend: TypeScript and Vite production build pass. Vitest reports **3 passed**.
- Compose chaos: pending approval survives agent restart. API/Web rebuild leaves agent and sandbox identities unchanged. Redis loss does not lose the result. SSE resumes after its cursor.
- Browser: session creation, initialization approval, focus retention, draft preservation, edit preview, approved write, current diff, refresh recovery, and 390 px layout pass.
- DeepSeek: the explicit live run reports **2 passed** with `deepseek-flash`. It reads a real workspace file and completes a deferred file write after approval. The latter uses two native run segments.
- MySQL concurrency regression: **3 passed in each of 3 consecutive runs**. Coverage includes 1,728 concurrent event write attempts, duplicate keys, native parallel tool loops, snapshot deduplication, effect updates, and duplicate run identity rejection.
- Static checks: Ruff and repository whitespace checks pass.

Framework versions are Pydantic AI 2.61.0, Harness 0.61.0, and FastMCP 4.1.3. Host tests use Python 3.11.15. Container tests use the Python interpreter in the sandbox image. Commands are in [verification](verification.md).

## Material limits

- The CLI renders inline event records and a compact status prompt. The mockup's decorative frame, collapsible trace navigation, and context meter remain presentation work.
- The Web interface uses the specified console direction. The entire interaction acceptance matrix has not been separately automated. Screen-reader behavior and all keyboard combinations have not been audited.
- The Web theme is light. The dark palette remains a design reference.
- Redis hints are published. This release reads durable state by polling; it does not subscribe to hints.
- Root repository instructions and the documented repository extension paths are supported. There is no global extension-directory editor.
- Trust is reused for the same repository identity, category, and content signature. A different repository requires its own decision.
- The schema uses JSON session payloads and native record JSON. It has no migration tool, retention job, or large-history performance target.
- The single agent-service instance holds a filesystem lock. It has no distributed ownership or multi-instance failover.
- Remote HTTP MCP destinations are selected through trusted configuration. Docker offline mode applies only to sandbox processes.
- Compaction and failure boundaries use deterministic providers in integration tests. Live DeepSeek tests cover reading and deferred editing, not every failure scenario.
- Recovery never rolls files back and never promises exactly-once external effects. A missing receipt requires inspection.

These limits do not change the specification. The interaction documents remain the acceptance contract for further presentation and verification work.

## MySQL deadlock correction

A user run exposed a StepStore deadlock while two `tool_call_completed` events were written concurrently. InnoDB's deadlock report showed both transactions holding gap locks and waiting to insert into the same index gap. The adapter used a locking read before inserting a missing idempotency key.

The adapter now uses one atomic upsert for events, snapshots, and effects. The unique key arbitrates competing writers. Immutable records keep their original payload; effects update their result. Run registration still rejects a duplicate identity. No schema or isolation-level change is required.

The old implementation failed the real MySQL concurrency regression. The fixed implementation passed three consecutive runs. The default SQLite suite and the two bounded paid smoke tests also passed. The agent service was rebuilt with this correction.
