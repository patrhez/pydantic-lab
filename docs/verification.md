# Verification Plan

Status: executable checks are available. Observed results are recorded in [implementation status](implementation-status.md). The scenarios below remain the acceptance checklist.

## Test levels

| Level | Required evidence |
| --- | --- |
| Unit | Policy decisions, identities, control transitions, trust invalidation, and log fields |
| Framework integration | Real Agent/tool loop with deterministic models; approval, continuation, and compaction |
| Container integration | Actual Docker execution, local bind mounts, session volumes, limits, and network settings |
| Service integration | MySQL transactions, Redis hint loss, SSE replay, and process restart |
| Browser integration | Session list, streaming, approval, queue/steer, Stop/Continue, refresh, replay, sandbox controls, trust, and diff |
| Live smoke | Bounded DeepSeek requests using the configured endpoint |

Use temporary repositories and disposable test resources. The default test run must not call paid model APIs. Tests must check observable behavior. They must not pass by mirroring the helper they claim to test.

## Critical scenarios

1. Queue two messages while one run executes. Confirm FIFO order and one active run per session.
2. Steer during a command. Confirm the command settles before the new instruction reaches the model.
3. Steer during approval. Confirm the old operation never runs, and that an old approval response is rejected.
4. Stop with queued input. Confirm cancellation, a stored pause, and an explicit Continue.
5. Restart while waiting for approval, and again after a settled checkpoint. Confirm the state is restored correctly, without duplicate effects.
6. Kill execution after a file change and before its receipt. Confirm `outcome_unknown` and no automatic retry.
7. Edit a file while approval is pending. Confirm the stale operation cannot overwrite that file.
8. Drop Redis notifications and reconnect SSE. Confirm MySQL replay keeps order and the final state.
9. Run two sessions against the same public Git source. Confirm the files stay independent and the concurrency limit holds.
10. Stop or remove a sandbox container. Confirm reconnection or replacement keeps the workspace files and restarts MCP transports.
11. Change the sandbox network setting. Confirm the isolation actually changes before the next operation.
12. Change a trusted MCP config or a skill support file. Confirm trust has to be granted again.
13. Compact a conversation that contains many tool calls. Confirm a valid protocol, the original records, and restart behavior.
14. Rebuild only the frontend and API. Confirm the active agent run and its sandbox continue.
15. Refresh during streamed output. Confirm committed chunks replay in order, without duplicate text or a cursor gap.
16. Double-click Allow Once and race Stop with Steer. Confirm one accepted decision, expired stale controls, and no duplicate execution.
17. Try to delete a session while it is running or awaiting approval. Confirm Delete is disabled until Stop completes.
18. Change sandbox networking and trust while a run is active. Confirm the controls are disabled with reasons, then apply and verify changes between runs.
19. Run the CLI in a narrow no-color terminal and in noninteractive mode. Confirm readable states, status `3` on required approval, and a usable resume path.
20. Render the CLI, Web, unknown-outcome, and narrow-screen states. Confirm they meet the interaction acceptance criteria and shared terminology.

21. Request an initialization approval. Confirm the progress view permits a decision while chat is disabled, and restores the request after refresh.
22. Deliver a new approval while typing. Confirm focus and draft remain unchanged and Enter cannot approve it.
23. Pause provider output below 2 KiB with an open Markdown block. Confirm a 100 ms flush and ordered replay of residual text before terminal events.

The detailed interface checks live in [CLI interactions](cli-interactions.md#acceptance-criteria), [Web interactions](web-interactions.md#acceptance-criteria), and [Visual design](visual-design.md#acceptance-criteria).

## Live provider configuration

Read the supported literal DeepSeek key and base URL assignments from `~/.zshrc`. Do not execute that file. Environment variables take precedence. Do not print the values, and do not copy them into Git. Use an explicit opt-in command, a bounded number of requests, and a temporary workspace. Record the actual model and package versions with the result.

## Evidence and documentation

After implementation, add the exact commands that worked, and their results, to the status page. List skips and failures. Add a success badge or a runnable quick start only after the matching checks pass. On each feature change, review this matrix against the code and the guides.

## Executable commands

Build `pydantic-lab-sandbox:local` first, as shown in the root README. Build the agent image before the stdio MCP integration test, which uses that image without controller privileges.

```sh
uv sync --locked
uv run ruff check src tests scripts
uv run pytest -q
RUN_LIVE=1 uv run pytest -q tests/test_live.py -s
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend test -- --run
```

The default Python suite includes real Docker integration. It skips the two paid provider tests and three MySQL concurrency tests unless their opt-in settings are supplied. To run only local unit checks, use `uv run pytest -q -m 'not integration and not live'`.

For service and browser checks, start a deterministic write model:

```sh
LAB_DEMO=1 LAB_DEMO_TOOL=write_file uv run python scripts/compose.py up -d --build
uv run python scripts/service_smoke.py
uv run python scripts/service_smoke.py --chaos
uv run playwright install chromium
uv run python scripts/browser_smoke.py
```

The chaos variant rebuilds API and Web, restarts the agent, and stops Redis temporarily. Run it with other sessions idle. Both scripts create and delete their own disposable session. Browser screenshots go to ignored `.local-data/screenshots/`. Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to use an existing compatible Chromium binary.

Return the agent to real-provider mode after the tests:

```sh
LAB_DEMO=0 uv run python scripts/compose.py up -d --no-deps agent
```

Do not run `down -v` against state you want to keep. Session cleanup belongs to the sandbox manager, because its workspace volumes are independent of Compose volumes.

## MySQL concurrency regression

`tests/test_steps_mysql.py` exercises real MySQL connections. SQLite cannot reproduce InnoDB gap locks. The regression runs six batches of 96 event writes across three independent adapters, including repeated keys. It also runs four native agents with parallel tool calls and checks snapshot deduplication, effect updates, and duplicate run rejection.

With a reachable test database, run:

```sh
LAB_TEST_DATABASE_URL='mysql+pymysql://user:password@host/database' uv run pytest -q tests/test_steps_mysql.py
```

With the local Compose database, run inside a disposable agent container after building the current image:

```sh
docker compose run --rm --no-deps \
  --volume "$PWD/tests:/tests:ro" agent sh -c '
  uv pip install --python /app/.venv/bin/python pytest pytest-asyncio &&
  LAB_TEST_DATABASE_URL="$LAB_DATABASE_URL" /app/.venv/bin/python -m pytest \
    -q -p no:cacheprovider -o asyncio_mode=auto \
    -o markers="integration: database integration" /tests/test_steps_mysql.py
  '
```

The tests create unique run IDs and remove only their own framework records. They make no paid model requests. Repeat the three-test module when changing concurrency or persistence semantics.
