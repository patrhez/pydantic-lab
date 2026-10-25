# Pydantic AI Coding Agent Lab

A readable coding agent lab with two interfaces: an inline terminal CLI and a Web workspace. Both use the same Pydantic AI runtime.

The CLI edits your actual repository through a Docker bind mount. The server clones a public Git repository into a separate Docker volume for each session. The frontend, API server, agent server, MySQL, and Redis run as separate Compose services.

![System architecture](docs/diagrams/system-architecture.png)

## Features

- Native file tools, shell controls, deferred approval, and checkpoint persistence.
- Exact-operation approvals, explicit allow rules, execution receipts, and learning logs.
- FIFO Queue, safe-boundary Steer, Stop, Continue, and explicit recovery for unknown outcomes.
- Native context summarization, Skills, repository instructions, and both MCP transports.
- Session list, committed streaming output, SSE replay, current Git diff, and approval previews.
- Independent service updates, persistent workspaces, idle stop, and container replacement.

Versions: Pydantic AI **2.61.0**, Harness **0.61.0**, and FastMCP **4.1.3**. Python dependencies are locked in `uv.lock`. Frontend dependencies are locked in `frontend/package-lock.json`.

## Quick start

Install Python 3.11+, uv, and Docker. Start the Docker daemon. Node 22+ is required only for frontend development outside Docker.

```sh
uv sync --locked
# Build the shared tool image before the application images.
docker build -f docker/sandbox.Dockerfile -t pydantic-lab-sandbox:local .
```

Configure `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and optionally `DEEPSEEK_MODEL`. Environment variables take precedence over `.env` values and supported quoted literal assignments in `~/.zshrc`. The loader does not execute that file. The default model is `deepseek-flash`.

Run the CLI against a repository:

```sh
uv run pydantic-lab --workspace /absolute/path/to/repository
# Deterministic mode: real framework tools and Docker, no paid model requests.
uv run pydantic-lab --demo --workspace /absolute/path/to/repository "List the files"
```

Tab switches Queue and Steer during execution. Use `/allow`, `/reject`, `/diff`, `/trust`, `/stop`, and `/continue`. For unknown outcomes, inspect the workspace and choose `/continue`, `/retry`, or `/abort`. Approval in noninteractive mode exits with status `3` and prints the exact resume command. Local state defaults to `~/.local/share/pydantic-lab`.

Start the Web services with the same provider configuration:

```sh
uv run python scripts/compose.py up -d --build
# Or run a deterministic demo:
LAB_DEMO=1 uv run python scripts/compose.py up -d --build
```

Open [the Web workspace](http://127.0.0.1:8080). The [API reference](http://127.0.0.1:8000/docs) is also local. Create a session with a public Git URL and an optional branch or full commit SHA. Initialization commands require approval before chat becomes available.

Update one service without restarting the agent:

```sh
uv run python scripts/compose.py up -d --build --no-deps web
uv run python scripts/compose.py up -d --build --no-deps api
```

`docker compose down` keeps database and session volumes. Delete a session through the UI to remove its workspace and dependency volumes. Session volumes are created by the sandbox manager, outside Compose's volume list.

## Policies and extensions

Use `--policy examples/policy.json` for the CLI. Server session creation accepts a `policy` object. `LAB_POLICY_JSON` sets the API's default policy for new sessions. Policies are saved with each session. Resume uses that saved policy.

Repository extensions start inactive. Put Skills under `.agents/skills/` or `.claude/skills/`, instructions in `AGENTS.md` or `CLAUDE.md`, and MCP definitions in `.mcp.json`. Inspect their content, then grant trust per category. Content changes require new trust. Trust never approves a tool operation.

See [the extension examples](docs/implementation.md#skills-and-mcp) for stdio dependencies and HTTP placement.

## Verification

```sh
uv run ruff check src tests scripts
uv run pytest -q                         # Includes Docker; paid and explicit MySQL tests skip.
uv run pytest -q -m 'not integration and not live'
RUN_LIVE=1 uv run pytest -q tests/test_live.py -s
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend test -- --run
```

[Verification instructions](docs/verification.md) include disposable Compose restart tests and browser tests. [Implementation status](docs/implementation-status.md) records observed results and remaining limits.

## Learn the implementation

Start with the [source walkthrough](docs/implementation.md), then follow the [CLI loop diagram](docs/cli-agent-loop.md). The [documentation index](docs/README.md) links the specification, architecture, decisions, persistence rules, and interaction contracts.

This release targets one user on local Docker. It has no user management, sub-agents, private Git credentials, or file rollback. Shell allowlists are best-effort guardrails. Writable mounts expose the real files you selected. Provider keys remain in the controller; do not place them in a repository that tools can read.

Write repository content in English. Keep documentation and implementation aligned. Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). See [contribution rules](CONTRIBUTING.md).
