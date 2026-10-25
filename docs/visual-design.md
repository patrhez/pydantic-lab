# Visual Design Specification

Status: planned. This document defines the visual direction for the CLI and Web UI. It does not describe implemented styles or components. Token names and component contracts are proposed application contracts.

## Direction

Use a **modern developer console** direction:

- A quiet warm-neutral Web workspace.
- Dark terminal, code, and diff surfaces.
- One indigo accent for primary actions and focus.
- Precise borders, compact spacing, and clear text states.
- No glow effects, decorative gradients, oversized cards, or unnecessary shadows.

The design should make execution boundaries easy to see. Approval, Stop, recovery, and unknown outcomes are more important than decoration.

## Principles

1. **State before decoration.** Every status has text, not only color.
2. **One accent.** Indigo identifies the primary action and keyboard focus.
3. **Dense but readable.** The interface fits developer work without compressing controls below accessible sizes.
4. **Terminal first.** Code, commands, diffs, and logs use a monospace font and dark surfaces.
5. **Learning visibility.** Framework boundaries, receipts, checkpoints, and policy decisions remain visible as concise records.
6. **Shared language, native controls.** CLI and Web use the same terms, but each uses the interaction style appropriate to its environment.

## Color tokens

The Web UI uses a light theme by default. A dark theme may follow the same semantic roles. The CLI uses the terminal's theme and maps these roles to standard ANSI colors where possible.

### Web light theme

| Token | Value | Use |
| --- | --- | --- |
| `color.bg` | `#F7F8FA` | Page background |
| `color.surface` | `#FFFFFF` | Cards, composer, panels |
| `color.surface-subtle` | `#F0F3F6` | Secondary panels and table headers |
| `color.terminal-bg` | `#10141A` | Terminal and code surface |
| `color.terminal-panel` | `#171D25` | Tool and diff panels |
| `color.text` | `#182230` | Primary text |
| `color.text-muted` | `#5B6675` | Metadata and secondary text |
| `color.border` | `#D8DEE6` | Hairline borders |
| `color.accent` | `#4F46E5` | Primary action and focus |
| `color.accent-strong` | `#4338CA` | Primary hover and pressed state |
| `color.accent-soft` | `#EEF0FF` | Selected background |
| `color.success` | `#16794C` | Succeeded, trusted, connected |
| `color.warning` | `#A15C07` | Pending, paused, outcome unknown |
| `color.danger` | `#B42318` | Failed, rejected, destructive |
| `color.info` | `#2563EB` | Information and links |
| `color.unknown` | `#7C3AED` | Uncertain recovery state |

### Web dark theme

| Token | Value |
| --- | --- |
| `color.bg` | `#0E1116` |
| `color.surface` | `#151A21` |
| `color.surface-subtle` | `#1B222B` |
| `color.text` | `#E7EBF0` |
| `color.text-muted` | `#9AA6B2` |
| `color.border` | `#303944` |
| `color.terminal-bg` | `#10141A` |
| `color.terminal-panel` | `#171D25` |
| `color.accent` | `#8B85FF` |
| `color.accent-strong` | `#A5B4FC` |
| `color.accent-soft` | `#292B58` |
| `color.success` | `#34D399` |
| `color.warning` | `#F59E0B` |
| `color.danger` | `#F87171` |
| `color.info` | `#60A5FA` |
| `color.unknown` | `#C084FC` |

Keep the same hues in both themes. Verify final contrast with the implemented font sizes and backgrounds.

### CLI color mapping

| Semantic role | Default ANSI mapping |
| --- | --- |
| Primary and focus | Blue |
| Success | Green |
| Pending, paused, and unknown outcome | Yellow |
| Failed, rejected, and destructive | Red |
| Information | Cyan |
| Secondary text | Terminal default dimmed style |

Respect `NO_COLOR`, `TERM=dumb`, and user terminal themes. In no-color mode, use text labels such as `[running]`, `[expired]`, and `[trusted]`.

## Typography

Use no more than two product font families.

| Role | Family | Size | Weight | Line height |
| --- | --- | --- | --- | --- |
| Page title | Geist Sans, Inter, system sans | 24 px | 650 | 32 px |
| Section title | Geist Sans, Inter, system sans | 16 px | 650 | 24 px |
| Body | Geist Sans, Inter, system sans | 14 px | 450 | 22 px |
| Secondary | Geist Sans, Inter, system sans | 13 px | 450 | 20 px |
| Metadata | Geist Sans, Inter, system sans | 12 px | 500 | 18 px |
| Composer | Geist Sans, Inter, system sans | 14 px | 450 | 22 px |
| Code and tool output | Geist Mono, SFMono, monospace | 13 px | 450 | 20 px |
| CLI | Terminal monospace | User setting | Regular | Terminal setting |

Do not use a monospace family for general prose. Do not use a serif family in the product workspace. Documentation diagrams may use a serif title only when it matches the diagram style.

## Spacing, borders, and shape

Use a 4 px spacing scale.

| Token | Value | Use |
| --- | --- | --- |
| `space.1` | 4 px | Icon and label gap |
| `space.2` | 8 px | Compact control padding |
| `space.3` | 12 px | Form field gap |
| `space.4` | 16 px | Card padding |
| `space.5` | 20 px | Section gap |
| `space.6` | 24 px | Panel padding |
| `space.8` | 32 px | Page section gap |
| `space.10` | 40 px | Major layout gap |

Use 1 px borders. Use 6 px radius for buttons and inputs, 8 px for cards, and 10 px for panels and dialogs. Do not use fully rounded cards. Pills are allowed only for compact status chips.

Use no shadow on normal cards. A modal or overlay may use one subtle shadow: `0 8px 24px rgba(16, 20, 26, 0.16)`.

Focus uses a 2 px `color.accent` outline with a 2 px offset. The outline must remain visible on light and dark surfaces.

## Semantic states

| State | Web treatment | CLI treatment |
| --- | --- | --- |
| Running | Blue dot plus `Running` | `[running]` plus elapsed time |
| Queued | Neutral chip plus queue position | `[queued Q2]` |
| Steer recorded | Indigo chip plus safe-boundary hint | `[steer recorded]` |
| Awaiting approval | Warning border plus expanded card | Expanded approval block |
| Expired approval | Neutral strike title plus reason | `[expired: reason]` |
| Succeeded | Green check plus `Succeeded` | `[succeeded]` |
| Failed | Red icon plus `Failed` and safe error | `[failed]` |
| Stopped | Neutral icon plus `Stopped` | `[stopped]` |
| Outcome unknown | Warning panel plus explicit decision buttons | Expanded `[outcome_unknown]` block |
| Trusted | Green text plus content identity summary | `[trusted]` |
| Changed trust | Warning text plus new-trust action | `[changed: trust required]` |

Color never carries meaning alone.

## Core components

### Buttons

| Variant | Use | Required states |
| --- | --- | --- |
| Primary | Allow Once, Continue, Create session | Default, hover, pressed, focus, loading, disabled |
| Secondary | Diff, Inspect, Retry discovery | Default, hover, pressed, focus, disabled |
| Danger | Stop, Abort, Delete | Default, hover, pressed, focus, loading, disabled |
| Ghost | Expand trace, session drawer | Default, hover, pressed, focus, disabled |

Buttons have 10 px vertical and 14 px horizontal padding. Minimum height is 36 px on desktop and 44 px on touch layouts. Loading replaces the label only when the state name remains available to assistive technology.

### Queue/Steer selector

Use a two-segment control. The selected segment uses `color.accent-soft`, an indigo border, and text. The control shows a short hint:

- Queue: `Runs after the current run`.
- Steer: `Applies at the next safe boundary`.

The CLI uses `mode: queue` or `mode: steer` in the header and composer hint. Tab switches modes only while a run is active or awaiting approval.

### Message and composer

Assistant and user messages are separated by spacing and metadata, not large bubbles. User messages show a compact mode label when submitted during a run. Assistant Markdown uses standard headings, lists, tables, and code blocks.

The composer is a bordered surface with a visible mode hint. Disabled composers show the reason in text.

### Tool trace item

A tool group has a status label, tool name, duration when known, and disclosure control. The expanded area contains arguments, output, receipt, and related checkpoint references. Technical values use the code font.

The CLI renders the same group as an indented block with a one-line summary when collapsed.

### Approval card

The approval card is the most prominent component in the transcript. It uses a warning top border, clear operation identity, and two buttons:

- Primary: `Allow Once`.
- Secondary: `Reject Once`.

A new card preserves the current focus and composer draft. An explicit Review approval action moves focus into it without submitting a decision.

An expired card keeps its original operation visible. It disables both buttons and shows the invalidation reason.

### Diff panel

Diffs use a dark code surface. Added lines use a success-tinted background. Removed lines use a danger-tinted background. Line numbers use muted text. File headers show path, change type, and line counts.

The panel title is `Current workspace diff`. A note says that the view can include user edits made before or during the run.

### Sandbox and extension rows

Use definition rows instead of dense tables inside the inspector. Each row has a label, value, and optional action. Lifecycle actions show disabled reasons while a run is active.

Extension rows show category, trust state, content identity summary, and Inspect or Trust. Keep execution approval outside this component.

### Recovery banner

Use a warning panel for recovery. It lists the checkpoint, pending approvals, queue, sandbox, and unresolved effects. `outcome_unknown` uses an expanded panel with three labelled decisions: `Continue without retry`, `Retry once`, and `Abort`.

### Dialogs, banners, and toasts

- Use dialogs for Delete, Rebuild, unknown-outcome decisions, and trust review.
- Use inline banners for reconnect, recovery, and initialization failure.
- Use toasts only for transient acceptance feedback. Do not use a toast as the only record of an approval, Stop, or recovery state.

### Empty, loading, and error states

Empty states use one sentence and one primary action. Loading states use skeleton rows that match the final layout. Error states name the failed operation and provide a safe next action. Do not use full-page spinners after a session has content.

## CLI presentation

The CLI uses the same tokens conceptually, but renders through the terminal:

- Header and status line use dimmed separators.
- Transcript records use indentation instead of cards.
- Approval and recovery blocks use expanded plain-text sections.
- Receipts, checkpoints, and compaction records use one-line summaries.
- Long output truncates with the omitted line or byte count.
- Narrow terminals stack metadata instead of truncating targets.

The CLI does not use terminal cursor movement to rewrite history. It may update a spinner or elapsed-time line in place.

## Shared terminology

Use exactly these user-facing terms in both interfaces:

| Term | Use |
| --- | --- |
| Session | Conversation, controls, and workspace binding |
| Run | One logical agent execution |
| Queue | FIFO follow-up that becomes a later run |
| Steer | Input for the current logical run at a safe boundary |
| Allow Once | Approve one exact operation once |
| Reject Once | Return one refusal to the agent |
| Stop | Cancel the active run and pause queued scheduling |
| Continue | Resume eligible queued work; use `Continue without retry` for unknown-outcome inspection |
| Expired | Approval invalidated by Stop, steer, or a policy/configuration change |
| Receipt | Known result for one operation |
| Checkpoint | Saved execution boundary |
| Outcome unknown | Started operation without a confirmed result |
| Sandbox | Tool execution environment |
| Workspace | Files available to tools |
| Trusted | Configuration content approved for loading |
| Changed | Trusted content no longer matches its recorded identity |

Do not introduce synonyms such as interrupt, pause run, approve always, or rollback for these concepts.

## Diagrams and mockups

Editable sources and rendered previews are stored together:

| Artifact | Editable source | Preview |
| --- | --- | --- |
| CLI workspace mockup | [SVG](diagrams/cli-workspace.svg) | [PNG](diagrams/cli-workspace.png) |
| Web workspace mockup | [SVG](diagrams/web-workspace.svg) | [PNG](diagrams/web-workspace.png) |
| Web key states mockup | [SVG](diagrams/web-key-states.svg) | [PNG](diagrams/web-key-states.png) |
| Run control state flow | [SVG](diagrams/session-state-flow.svg) | [PNG](diagrams/session-state-flow.png) |

The SVG files are static, editable product design sources. Render and inspect previews after any source change. Keep product mockups in the product visual style; reserve the hand-drawn Excalidraw style for conceptual system diagrams.

## Accessibility requirements

- Text contrast meets WCAG AA.
- Focus is visible on every interactive element.
- Status has text or an icon in addition to color.
- Motion is limited to state fades and spinner rotation. Honor reduced-motion settings.
- Tool output and diffs remain operable by keyboard.
- Dialogs trap focus and return it to the opener.
- CLI output remains meaningful in a no-color terminal and when read as plain text.

## Acceptance criteria

| ID | Criterion |
| --- | --- |
| VIS-AC-01 | Every semantic state has a text label and does not depend on color alone |
| VIS-AC-02 | Light-theme normal text and interactive colors pass WCAG AA contrast against their backgrounds |
| VIS-AC-03 | Primary, secondary, danger, and ghost buttons expose default, hover, pressed, focus, loading where applicable, and disabled states |
| VIS-AC-04 | Queue and Steer use one segmented Web control and one terminal mode indicator with the same terms |
| VIS-AC-05 | Approval is visually more prominent than ordinary tool output, while `outcome_unknown` is visually distinct from a known failure |
| VIS-AC-06 | Web and CLI mockups use the shared terminology table without invented synonyms |
| VIS-AC-07 | Each editable diagram or mockup source has a rendered preview committed in the same change |
| VIS-AC-08 | Narrow Web and CLI layouts preserve operation targets and decision labels without horizontal clipping of the primary content |
