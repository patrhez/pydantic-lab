# System Diagrams

The system diagrams show component ownership and execution boundaries. UI mockups remain design references. See the [source walkthrough](../implementation.md) for actual routes and persistence contracts.

| Diagram | Editable source | Preview |
| --- | --- | --- |
| System architecture | [Excalidraw](system-architecture.excalidraw) | [PNG](system-architecture.png) |
| CLI agent loop | [Excalidraw](cli-agent-loop.excalidraw) | [PNG](cli-agent-loop.png) |
| Execution and recovery | [Excalidraw](execution.excalidraw) | [PNG](execution.png) |
| CLI workspace mockup | [SVG](cli-workspace.svg) | [PNG](cli-workspace.png) |
| Web workspace mockup | [SVG](web-workspace.svg) | [PNG](web-workspace.png) |
| Web key states mockup | [SVG](web-key-states.svg) | [PNG](web-key-states.png) |
| Run control state flow | [SVG](session-state-flow.svg) | [PNG](session-state-flow.png) |

The architecture diagram separates service state from sandbox files. The execution diagram shows where approval, tool effects, and receipts occur. Log examples are proposed application labels, not framework event names.

Open an `.excalidraw` file in Excalidraw to edit it. Edit an `.svg` mockup in a vector editor or as source. Render the PNG after each change and look at the result. Commit each source and its preview together. Keep labels consistent with the specification.

The conceptual Excalidraw method follows [coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill). Product UI mockups use clean SVG rather than a hand-drawn style. No third-party skill code is vendored in this repository.
