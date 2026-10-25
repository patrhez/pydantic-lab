# Sandboxes and Workspaces

Status: planned. Use the official DockerSandbox capability; verify its lifecycle and transport behavior with the selected release.

## Local files and server files

```text
CLI:     actual repository -> bind mount -> /workspace
Server:  public Git clone  -> named volume -> /workspace
```

A bind mount exposes the original files. A container edit is immediately visible in the host editor and Git. Container tools must use their own dependency locations; do not reuse host Python environments or Node native modules. This requires mount and environment configuration, not just documentation.

A server workspace starts from a public Git URL and selected branch or commit. Record the resolved commit. Each session gets an independent volume, even when two sessions use the same repository URL.

## Binding and lifecycle

MySQL maps the session to a stable logical sandbox ID, container reference, workspace volume, and image/configuration identity. Container labels help locate resources after a crash. The stored binding remains authoritative.

1. Record a provisioning intent with a stable sandbox ID.
2. Create or find its volume and container.
3. Initialize the repository and approved dependencies.
4. Record the usable binding.
5. On restart, compare the record with Docker resources and reconcile partial work.

Stop an idle container without deleting its volume. Start it when needed. If the container is missing, create a replacement with the same volume and recorded configuration. Container-layer changes can disappear. Put base tools in the image and make dependency setup repeatable.

Stop also ends sandbox processes and stdio MCP connections. Close client transports, release their handles, and reconnect after restart. Do not stop a container with an executing operation. Waiting for human approval is idle only when no operation or transport activity requires it.

Session deletion must stop scheduling before resource cleanup. Record incomplete cleanup so a later retry can finish. Show that workspace deletion is permanent.

## Network and control access

Use networking for approved initialization, then switch to offline execution. Do not treat a database flag as a Docker network change. The sandbox manager must apply the network setting, reconnect transports, and verify it before a tool runs. Recreate a container if required; preserve the workspace volume.

Remote HTTP MCP requests run from the agent service under a separate destination policy. They are not constrained by the tool container's offline network. The UI must distinguish these settings.

Keep tool containers non-privileged. Set CPU, memory, process, and output limits. Mount only the selected workspace and required dependency/cache volumes. Do not mount host credentials or the Docker socket into them. Keep model keys in the controller process.

The sandbox manager has privileged Docker control. A socket mount gives it broad host control; it is not a security boundary against a compromised manager. Keep this access out of the runtime's tool surface.

Container isolation does not protect files intentionally mounted writable. It also does not provide file rollback. See the official [DockerSandbox security model](https://pydantic.dev/docs/ai/harness/docker-sandbox/#security-model).
