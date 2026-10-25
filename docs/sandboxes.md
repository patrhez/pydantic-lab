# Sandboxes and Workspaces

Status: planned. Use the official DockerSandbox capability. Check its lifecycle and transport behavior against the selected release.

## Local files and server files

```text
CLI:     actual repository -> bind mount -> /workspace
Server:  public Git clone  -> named volume -> /workspace
```

A bind mount exposes the original files. An edit inside the container shows up immediately in the host editor and in Git. Container tools must use their own dependency locations. Do not reuse the host Python environment or Node native modules. Set that separation in the mount and environment configuration.

A server workspace starts from a public Git URL and a selected branch or commit. Record the resolved commit. Each session gets its own volume, even when two sessions use the same repository URL.

## Binding and lifecycle

MySQL maps the session to a stable logical sandbox ID, a container reference, a workspace volume, and an image and configuration identity. Container labels help find those resources after a crash. The stored binding remains authoritative.

1. Record a provisioning intent with a stable sandbox ID.
2. Create the volume and container, or find them if they already exist.
3. Initialize the repository and the approved dependencies.
4. Record the binding once it is usable.
5. On restart, compare the record with the Docker resources and finish any partial work.

Stop an idle container and keep its volume. Start the container again when it is needed. If the container is missing, create a replacement that uses the same volume and the recorded configuration. Changes in the container layer can disappear. Put the base tools in the image, and make dependency setup repeatable.

Stopping the container also ends sandbox processes and stdio MCP connections. Close the client transports, release their handles, and reconnect after the container starts again. Do not stop a container while an operation is executing. A session that is waiting for approval counts as idle only when no operation and no transport still needs the container.

Session deletion must stop scheduling before it cleans up resources. Record cleanup that did not finish, so a later retry can finish it. Tell the user that deleting the workspace cannot be undone.

## Network and control access

Use the network for approved initialization, then switch to offline execution. A database flag is not a Docker network change. The sandbox manager must apply the network setting, reconnect transports, and verify the setting before a tool runs. Recreate the container if the change requires it, and keep the workspace volume.

Remote HTTP MCP requests run from the agent service under a separate destination policy. The tool container's offline network does not constrain them. The UI must show these two settings separately.

Keep tool containers non-privileged. Set CPU, memory, process, and output limits. Mount only the selected workspace and the dependency or cache volumes the tools need. Do not mount host credentials or the Docker socket into a tool container. Keep model keys in the controller process.

The sandbox manager has privileged Docker control. A socket mount gives that manager broad control of the host. The mount is not a boundary that contains a compromised manager. Keep this access off the runtime's tool surface.

Container isolation does not protect files that were mounted writable on purpose. It also does not roll files back. See the official [DockerSandbox security model](https://pydantic.dev/docs/ai/harness/docker-sandbox/#security-model).
