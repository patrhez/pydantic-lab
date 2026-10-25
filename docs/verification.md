# Verification Plan

Status: required checks, not completed results. No executable application exists yet.

## Test levels

| Level | Required evidence |
| --- | --- |
| Unit | Policy decisions, identities, control transitions, trust invalidation, and log fields |
| Framework integration | Real Agent/tool loop with deterministic models; approval, continuation, and compaction |
| Container integration | Actual Docker execution, local bind mounts, session volumes, limits, and network settings |
| Service integration | MySQL transactions, Redis hint loss, SSE replay, and process restart |
| Browser integration | Session list, streaming, approval, queue/steer, Stop/Continue, refresh, and diff |
| Live smoke | Bounded DeepSeek requests using the configured endpoint |

Use temporary repositories and disposable test resources. Default tests must not call paid model APIs. Tests must assert observable behavior, not mirror helper implementations.

## Critical scenarios

1. Queue two messages while one run executes. Confirm FIFO and one active run per session.
2. Steer during a command. Confirm the command settles before the new instruction reaches the model.
3. Steer during approval. Confirm the old operation never executes and old approval responses are rejected.
4. Stop with queued input. Confirm cancellation, persistent pause, and explicit Continue.
5. Restart while awaiting approval and after a settled checkpoint. Confirm correct restoration without duplicate effects.
6. Kill execution after a file change but before its receipt. Confirm `outcome_unknown` and no automatic retry.
7. Edit a file while approval is pending. Confirm the stale operation cannot overwrite it.
8. Lose Redis notifications and reconnect SSE. Confirm MySQL replay preserves order and final state.
9. Run two sessions against the same public Git source. Confirm independent files and concurrency limits.
10. Stop or remove a sandbox container. Confirm reconnection or replacement retains workspace files and restarts MCP transports.
11. Switch the sandbox network setting. Confirm actual isolation changes before the next operation.
12. Change a trusted MCP config or skill support file. Confirm trust must be renewed.
13. Compact a tool-heavy conversation. Confirm valid protocol, original records, and restart behavior.
14. Rebuild frontend/API only. Confirm active agent execution and its sandbox continue.

## Live provider configuration

Read supported literal DeepSeek key and base URL assignments from `~/.zshrc` without executing it. Environment variables take precedence. Do not print values or copy them into Git. Use an explicit opt-in command, bounded requests, and a temporary workspace. Record actual model and package versions with the result.

## Evidence and documentation

After implementation, add exact working commands and results to the status page. List skips and failures. Do not write a success badge or runnable quick start before the corresponding checks pass. Review this matrix against code and guides in each feature change.
