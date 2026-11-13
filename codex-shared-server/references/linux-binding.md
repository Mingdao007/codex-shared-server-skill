# Linux shared-backend binding

## What failed and why

Two independent backend processes create different loaded-thread/writer views.
Check where a thread actually lives before claiming it is unavailable. A stale
legacy socket is different from an unhealthy current daemon.

In the tested App, every startup creates an owner-only Unix pipe and advertises
`dynamic_app_tools_listening ... pipePath=...`. The App changes its own process
environment after starting. An already running daemon does not inherit that
change. An old pipe UUID therefore stops being useful after App restart.

The tested plugin-level env did not provide the effective binding. Supported
`config/batchWrite` with `reloadUserConfig=true` and **top-level** `mcp_servers`
entries restored ordinary calls, including a previously loaded test context.
`config/mcpServer/reload` accepted null/no params; it was not an env or per-thread
injection method. Probe the installed schema before carrying this forward.

## Optional authored C++ adapter

This adapter targets Linux `/proc`, Electron `SingletonLock`, the tested startup
log markers and existing `codex_app` / optional `code-review` MCP definitions.
It does not include any vendor App, Node runtime, plugin source or credentials.
A standard C++17 compiler, Boost system/Beast headers and jsoncpp are required.

Build in an ordinary temporary build directory:

```bash
cmake -S scripts -B /tmp/codex-shared-server-build
cmake --build /tmp/codex-shared-server-build -j2
```

Set explicit existing paths; the following names are placeholders, not discovered
values. The socket and its containing directory must be owned by the current
user and grant no group/other access. The adapter never changes permissions.

```bash
export CODEX_SHARED_SERVER_SOCKET="/path/to/private/server.sock"
export CODEX_SHARED_APP_DEFINITION="/path/to/installed/app-plugin/.mcp.json"
export CODEX_SHARED_PROFILE="${XDG_CONFIG_HOME:-$HOME/.config}/Codex"
export CODEX_SHARED_APP_EXECUTABLE="/path/to/real/AppExecutable"
export CODEX_SHARED_NODE="/path/to/bundled/node"
export CODEX_SHARED_CLI="/path/to/bundled/codex"
export CODEX_SHARED_LAUNCHER="/tmp/codex-shared-server-build/shared-app-launcher"
# Optional, only when this installed plugin also needs the inherited runtime:
# export CODEX_SHARED_REVIEW_DEFINITION="/path/to/review-plugin/.mcp.json"
```

First save a private selected-entry snapshot, without publishing it:

```bash
"$CODEX_SHARED_LAUNCHER" --socket "$CODEX_SHARED_SERVER_SOCKET" --snapshot > /path/to/private/selected-before.json
```

`--snapshot` is read-only and rejects unexpected environment keys rather than
copying unknown secrets. It selects the App and review entries only. Preserve
this snapshot and any original desktop/launch entry before an authorized change.

Once the current App can be closed safely, the optional wrapper launches the
original executable with the existing private WebSocket and automatic binding:

```bash
bash scripts/launch-shared-app.sh -- "$CODEX_SHARED_APP_EXECUTABLE"
```

It unsets `CODEX_APP_SERVER_FORCE_CLI` for this explicit shared launch only. It
does not edit shell startup files, install a service, close an existing App or
start/stop the daemon. The launch parent follows the App output stream; menu
relaunch not inheriting that stream is outside its verified lifecycle.

The C++ helper checks UID, executable, profile PID and actual pipe FD ownership
before binding. It reads the installed manifests, preserves current command,
arguments, environment additions and approval rules, and refuses mismatched
commands or an explicitly disabled **user top-level entry**. The vendor manifest
may default to disabled; selecting that installed manifest for this authorized
binding does not make it an explicit user-disable directive. The direct entries have `pluginId=null`;
that is a changed provenance, not a claim of unchanged plugin ownership.

A binding RPC has a 30-second operational timeout to avoid indefinitely hanging
the App stdout reader. This is not a performance/safety threshold. An interrupted
write has an uncertain outcome: read config before retrying. Inspect the
`binding_verified` or `binding_failed` event; an App process running alone is not
proof that its tool binding succeeded.

## Make the normal startup entry use the verified route

A manual wrapper test does not change the desktop's normal launch path. When the
user asks to make sharing the normal workflow, finish that reversible integration:

1. Back up the current user launcher and the desktop entry identified by its
   existing filename/desktop ID. Keep any system entry unchanged.
2. Create a per-user launch script containing the actual configured environment
   paths above and `exec bash /installed/skill/scripts/launch-shared-app.sh --`
   followed by the original App command and forwarded arguments. Store helper
   binaries outside the temporary build directory for a persistent installation.
3. Write a same-ID override under `${XDG_DATA_HOME:-$HOME/.local/share}/applications/`.
   Preserve its Name, Icon, MIME/deep-link fields and placeholders such as `%U`;
   change only `Exec` to the per-user wrapper. Avoid unrelated login/shell changes.
4. At the authorized safe interruption boundary, start from that actual entry,
   verify App process ancestry/env, a genuine new pipe and a real tool call.
   Repeat the normal-entry App restart on the same daemon and check retained
   contexts. A second manual invocation is not this desktop-entry test.

If the requested task is only diagnosis, report this as a proposed integration.
If it is an authorized repair, complete and verify it instead of stopping at an
uninstalled candidate. Rollback restores the saved entry and selected config.

For an explicit CLI connection to this same endpoint, the tested official CLI
accepts `codex --remote "unix://$CODEX_SHARED_SERVER_SOCKET"`. Inspect `codex --help`
on the installed version; do not infer a plain CLI's default daemon selection
from the App environment. Do not resume a thread with another active writer.

## Scoped rollback

Read back current configuration before rollback if another owner may have edited
it. Restore the two selected entries using the private snapshot, then restore the
original startup/desktop entry if that was changed:

```bash
"$CODEX_SHARED_LAUNCHER" --socket "$CODEX_SHARED_SERVER_SOCKET" --restore /path/to/private/selected-before.json
```

The helper verifies the restored values and leaves other MCP/config keys alone.
A pre-change null entry removes that direct override. Keep write/reload failures
and partial results; do not manufacture success from an exit code without readback.
