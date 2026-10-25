# Design Decisions

Status: agreed product choices; implementation details remain subject to framework verification.

| Decision | Reason | Cost or limit |
| --- | --- | --- |
| One standalone lab with two interfaces | Compare the same behavior without sibling shared packages | Interface adapters still need separate tests |
| Use public framework features first | Learn Pydantic AI rather than a replacement loop | Pin versions and verify extension points |
| Separate API and agent deployments | UI and API changes must not stop execution | Requires durable coordination |
| Use MySQL as server truth | Preserve sessions, controls, and checkpoints across restart | Requires transactions and a store adapter |
| Use Redis for hints only | Lost notifications must not lose work | Readers need polling or replay fallback |
| Use DockerSandbox in both modes | Keep file and command execution consistent | Commands use Linux tools |
| Bind-mount the local repository | Let users inspect and edit the same files | Approved tools can damage mounted files |
| Give each server session a volume | Keep sessions independent and files persistent | Requires cleanup and resource limits |
| Clone public Git repositories | Provide a clear server workspace source | Private credentials and pushing are out of scope |
| Stop idle containers, keep volumes | Reduce idle resource use | Processes and stdio connections must restart |
| Default to offline execution | Make network access explicit | Install dependencies during controlled setup |
| Use one agent, no delegates | Focus on execution and recovery | No parallel sub-agent research |
| Serialize runs per session | Prevent conflicting workspace writes | A pending approval blocks queued runs |
| Inject steer at a safe boundary | Change direction without replacing the logical run | A running tool finishes first |
| Invalidate pending approvals on steer | Old plans must not execute after a new instruction | The pending tool protocol needs explicit resolution |
| Stop cancels and pauses the queue | Stop must not immediately launch another run | Users must select Continue |
| Default mutations to approval | Expose execution decisions for learning | More prompts unless users configure auto-allow rules |
| Reuse native checkpoint storage | Avoid a second recovery engine | Application controls still need persistence |
| Pause unknown effects | Avoid blind repetition of external effects | Users may need to inspect the workspace |
| Compute diff on demand | Current changes are derived from files and Git | No historical per-edit diff replay |
| Compact model context, keep records | Limit context without deleting conversation evidence | Summaries may omit detail |
| Trust repository extensions explicitly | A repository must not activate its own programs | Configuration changes can require new approval |
| Support stdio and HTTP MCP | Cover local programs and independent services | Two transport lifecycles require tests |
| Single local user | Keep scope on agent execution | No remote-user access controls |

## Technology defaults awaiting verification

Use Python with uv, FastAPI, React/TypeScript with Vite, and Docker Compose. Select compatible Pydantic AI and Harness versions after executable probes. Use a framework local file or SQLite backend; do not choose a custom local checkpoint schema first.

## How decisions change

Update this record and the specification together. Explain the changed condition and its effect. Keep abandoned experiments out of the main guides unless they explain a current limit.
