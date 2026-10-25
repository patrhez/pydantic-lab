# System Diagrams

These diagrams show planned behavior. They are not a record of an implemented protocol.

| Diagram | Editable source | Preview |
| --- | --- | --- |
| System architecture | [Excalidraw](system-architecture.excalidraw) | [PNG](system-architecture.png) |
| CLI agent loop | [Excalidraw](cli-agent-loop.excalidraw) | [PNG](cli-agent-loop.png) |
| Execution and recovery | [Excalidraw](execution.excalidraw) | [PNG](execution.png) |

The architecture diagram separates service state from sandbox files. The execution diagram shows where approval, tool effects, and receipts occur. Log examples are proposed application labels, not framework event names.

Open an `.excalidraw` file in Excalidraw to edit it. Render the PNG after each change and look at the result. Commit the source and the preview together. Keep labels consistent with the specification.

The visual method follows [coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill). Sources are editable scene files. No third-party skill code is vendored in this repository.
