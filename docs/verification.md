# Verification Plan

Status: required checks, not completed results. There is no executable application yet.

## Test levels

| Level | Required evidence |
| --- | --- |
| Unit | Policy decisions, identities, control transitions, trust invalidation, and log fields |
| Framework integration | Real Agent/tool loop with deterministic models; approval, continuation, and compaction |
| Container integration | Actual Docker execution, local bind mounts, session volumes, limits, and network settings |
| Service integration | MySQL transactions, Redis hint loss, SSE replay, and process restart |
| Browser integration | Session list, streaming, approval, queue/steer, Stop/Continue, refresh, and diff |
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

## Live provider configuration

Read the supported literal DeepSeek key and base URL assignments from `~/.zshrc`. Do not execute that file. Environment variables take precedence. Do not print the values, and do not copy them into Git. Use an explicit opt-in command, a bounded number of requests, and a temporary workspace. Record the actual model and package versions with the result.

## Evidence and documentation

After implementation, add the exact commands that worked, and their results, to the status page. List skips and failures. Add a success badge or a runnable quick start only after the matching checks pass. On each feature change, review this matrix against the code and the guides.
