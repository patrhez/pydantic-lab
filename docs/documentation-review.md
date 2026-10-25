# Documentation Review

Review date: 2026-10-25. Scope: specification, implementation, tests, learning documents, and existing diagrams.

## Result

The core implementation follows the confirmed service, execution, persistence, and sandbox decisions. Native API probes and runtime tests replace the earlier design assumptions. The [status page](implementation-status.md) records remaining presentation and verification work.

The README now provides working commands. The [source walkthrough](implementation.md) explains actual hook placement and adapters. Interaction mockups remain design references, rather than screenshots of every current component.

## Requirement coverage

| Specification area | Learning document | Required verification |
| --- | --- | --- |
| Two interfaces and service boundaries | [Architecture](architecture.md) | Independent service updates |
| MySQL truth and Redis hints | [Architecture](architecture.md), [Persistence](persistence.md) | Lost hints and SSE replay |
| Local bind mount and server session volumes | [Sandboxes](sandboxes.md) | Actual file changes and session isolation |
| Container lifecycle and network | [Sandboxes](sandboxes.md) | Restart, replacement, and network change |
| Queue, steer, Stop, and Continue | [Execution](execution.md) | Ordering, pause, and control races |
| CLI loop components and failure positions | [CLI agent loop](cli-agent-loop.md) | Framework continuation and effect recovery |
| CLI layout and controls | [CLI interactions](cli-interactions.md) | Terminal integration and acceptance criteria |
| Web layout, sessions, and controls | [Web interactions](web-interactions.md) | Browser integration and acceptance criteria |
| Visual tokens and components | [Visual design](visual-design.md) | Contrast, keyboard, narrow-layout, and mockup checks |
| Approval and allowlists | [Execution](execution.md) | Exact-call binding and stale decisions |
| Checkpoints, receipts, and unknown effects | [Persistence](persistence.md) | Process failure at execution boundaries |
| Learning logs and derived diff | [Persistence](persistence.md) | Correlation fields and current workspace diff |
| Compaction | [Integrations](integrations.md) | Valid tool protocol and restart |
| Skills, MCP, and repository instructions | [Integrations](integrations.md) | Trust changes and both transports |
| Single user and single agent | [Decisions](decisions.md) | Configuration and deployment checks |
| Tests and live DeepSeek smoke | [Verification](verification.md) | Recorded commands and results |
| English and commit conventions | [Contribution rules](../CONTRIBUTING.md) | Review each change |

## Decisions and corrections made

- Queue is the default input mode during an active run. Steer requires an explicit mode change.
- The first Ctrl+C during execution sends durable Stop. A second press within three seconds exits.
- Pending approvals have no time-based expiry. Stop, steer, and policy or configuration changes invalidate them.
- `outcome_unknown` offers Continue without retry, Retry once, and Abort. No automatic retry is allowed.
- Active sessions require Stop before Delete. Sandbox network changes require no active run and no pending approval.
- Repository extension trust is durable per category and content identity.
- Web streaming commits buffered output within 100 ms or at the size/Markdown threshold. Terminal and approval/tool boundaries flush residual text first.
- Noninteractive CLI output uses plain one-shot mode and exit status `3` when approval is required.
- CLI resume selects the latest recoverable session for the repository, or asks for an explicit ID when several qualify.
- The sandbox idle wording now agrees: approval without an executing operation is idle, and open stdio transports close as part of the stop.
- `architecture.md` no longer uses the undefined phrase "expired version".
- Approval arrival preserves composer focus. An explicit Review approval action opens the card without approving it.
- Provisioning keeps setup approval controls enabled while chat is disabled. Rejection ends initialization without executing the command.
- The state flow connects Running directly to Completed and Failed. Continue is labelled as starting the next run.
- Acceptance criteria cover setup approval restoration, focus retention, timed flushing, and flush-before-boundary ordering.

## Diagram and mockup review

The three original Excalidraw sources remain editable and have PNG previews. Four new SVG sources provide the CLI workspace, Web workspace, Web key states, and run-control flow. Their PNG previews were rendered with Playwright and Chromium and visually inspected.

The product mockups use the modern developer console direction. They do not use the hand-drawn Excalidraw style. Mockup labels use the shared terms Queue, Steer, Allow Once, Reject Once, Stop, Continue, receipt, checkpoint, and outcome unknown.

## Checks

Completed checks:

- Validated 19 Markdown files and 121 local links, including anchored links and image links. All passed.
- Parsed three Excalidraw scenes and checked unique IDs and binding references in the prior review.
- Parsed four SVG sources as XML.
- Rendered four new PNG previews and checked their dimensions: 1440×960, 1600×1100, 1600×1000, and 1600×920.
- Visually inspected all seven diagram and mockup previews.
- Checked staged whitespace with `git diff --cached --check`.
- Checked prose for sentences over 35 words. None were found.
- Calculated WCAG AA normal-text contrast for the specified light and dark semantic token pairs. All passed.
- Compared the new documents against the specification and the requirement coverage table.

Runtime, Docker, MySQL, Redis-loss, browser, terminal, MCP, and live DeepSeek checks have now run. See [implementation status](implementation-status.md) for evidence. The earlier diagram and contrast checks above describe the design artifacts; they do not certify every rendered product state.

## Implementation corrections

- Current and proposed diffs use an internal read-only inspection endpoint. They are not copied into durable display state.
- Normal agent-service shutdown preserves a pending run. A durable Stop cancels it.
- Approval waits release worker capacity while retaining the session execution slot.
- Docker DNS is resolved again after an independent API replacement.
- Send completion clears only the submitted draft. New text typed during that request remains.
- Trusted package contents are checked again before approved tools execute.
- Linux dependency volumes cover host `.venv` and `node_modules` and survive container restart.
- CLI noninteractive resume instructions include the state directory and demo flags when required.
