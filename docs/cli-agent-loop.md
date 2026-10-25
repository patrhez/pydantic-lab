# Inside the CLI Agent Loop

Status: planned. This guide explains the component positions. It does not replace the framework loop or claim verified hook timing.

![CLI agent loop, approval, checkpoints, and recovery](diagrams/cli-agent-loop.png)

Open the [Excalidraw source](diagrams/cli-agent-loop.excalidraw) to inspect or edit the diagram.

## What owns the loop

Pydantic AI owns the repeated model request, response handling, tool dispatch, and tool-result processing. The CLI controller supplies the model, capabilities, workspace, policy, and persistence adapters. The controller also handles input while the framework runs.

Do not implement a second handwritten model/tool loop around the framework. Use public hooks and continuation APIs for controls and recovery. One logical application run can span several native continuation calls, especially when an approval is deferred.

## Follow one tool call

1. **Accept input.** The CLI persists the user turn. Queue creates a later turn; steer targets the active run. It does not cancel that run.
2. **Prepare the next model request.** Check Stop, consume eligible steer input, and compact context if required. Keep tool-call/result pairs valid.
3. **Call the model.** Send effective history to DeepSeek from the CLI process. Stream display output to the terminal. The execution sandbox does not receive the model key.
4. **Dispatch the response.** The framework validates tool arguments. If the response is a final answer, record completion and let the scheduler consider queued work.
5. **Evaluate permission.** Enforce sandbox restrictions and explicit denials. An explicit auto-allow rule can permit execution. Otherwise a mutation or command waits for human approval.
6. **Wait for HITL when required.** Use native deferred approval support. Save the exact pending request and protocol state. Allow Once applies only to that operation. Reject Once returns a refusal.
7. **Execute.** Recheck the approved arguments and file content. Record that execution started, then call the tool inside DockerSandbox. Local edits affect the real repository through its bind mount.
8. **Record the result.** Save a receipt with operation identity, known outcome, and required result data. Return the result to the framework. Reuse native effect tracking where it meets the contract.
9. **Save a settled checkpoint.** StepPersistence records a valid message boundary after the tool batch settles. Continue with the next model request, or finish the run.

The sequence locates responsibilities. It does not require every tool or final response to produce an identical set of database writes. Probe the selected framework release to confirm native hooks, snapshot timing, and result storage.

## Where HITL and approval differ

HITL means human intervention in execution. Execution approval is the HITL path required here: the agent proposes an exact operation and waits for Allow Once or Reject Once.

Repository trust is a separate decision before loading Skills, MCP configuration, or repository instructions. Trust does not approve future tool calls. A file-change preview is also distinct from a completion notification. See [execution events](execution.md#file-events).

If steer arrives during approval, expire unexecuted requests, resolve the pending tool protocol, and inject the new instruction before the next model request. Keep the logical run. A callback that only waits in memory cannot implement restart-safe HITL by itself.

## Where checkpoints and receipts differ

A checkpoint saves the framework's continuable context. A receipt records what happened to one operation. The application must also preserve pending approvals, consumed control messages, scheduling pause, and sandbox binding.

An approval wait is not automatically a settled checkpoint. Preserve the pending protocol through supported serialization and continuation APIs. Do not infer this capability from the existence of a history snapshot alone.

A receipt can exist before a newer settled checkpoint. Recovery must reconcile its tool result with the saved framework history. It must not execute the operation again just because that checkpoint is older. Conversely, a started effect without a receipt is not proof that the operation failed.

## What recovery does

On restart, load the latest valid checkpoint and application control state. Reconnect the sandbox and inspect the effect records before resuming.

| Failure point | Recovery action |
| --- | --- |
| Before execution, while approval is pending | Restore the request unless Stop or steer invalidated it |
| During a model request | Retry from the valid saved boundary; another provider charge is possible |
| After an effect with a complete recorded result | Reconcile the result and reuse the completed effect |
| After a mutation or command starts, with no confirmed result | Set `outcome_unknown`, pause, and request user inspection |
| After Stop | Keep the run cancelled and the queue paused; Continue resumes queued work |

Recovery does not roll back the repository. The sandbox restricts execution access; it does not make a file change and a receipt atomic. See [persistence and recovery](persistence.md) for the complete rules.

## What the logs teach

Correlate the logical run, native run, tool call, approval, and checkpoint IDs. Log the permission source, pending decision, execution start, receipt, checkpoint save/load, and recovery decision. This shows which part belongs to the framework and which part belongs to the application.

Current diff remains an on-demand view of Git and workspace files. It is not the recovery journal. The [verification plan](verification.md) includes approval restart, stale decisions, steer boundaries, and the effect-without-receipt failure case.
