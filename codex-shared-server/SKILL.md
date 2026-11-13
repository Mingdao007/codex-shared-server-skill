---
name: codex-shared-server
description: Diagnose and repair Codex Desktop App and CLI shared-backend routing, dynamic App-tool pipe binding, retained-context visibility, and scoped rollback on Linux.
---

# Codex Shared Server

Deliver a working local App/CLI shared backend using actual process, protocol,
tool-call and retained-context evidence. This is a community workflow with a
Linux adapter, not an official OpenAI integration or a universal compatibility claim.

## Diagnose the actual boundary

1. Identify the running App, its local backend and the CLI/control socket.
   Compare actual processes and socket owners. An App-owned stdio thread can
   be absent from another daemon; one `notLoaded` response is not a global verdict.
2. Read the installed build's transport/config schema and plugin definitions.
   Confirm whether the App accepts `CODEX_APP_SERVER_WS_URL`. Unix sockets here
   carry WebSocket JSON-RPC, not newline-delimited JSON.
3. Test transport, MCP catalog, real tool call and existing-context visibility
   separately. Prefer a read-only tool such as `list_projects`. Catalog presence,
   a successful `initialize`, and an actual useful call are different evidence.
4. If the App's dynamic pipe is missing or stale, read
   [the binding procedure](references/linux-binding.md). Plugin-level env and
   top-level MCP env behaved differently in the tested builds. Discover the
   actual pipe; do not use a saved UUID or substitute another App's identity.

## Apply the smallest supported correction

Use the existing daemon and preserve its callers. Coordinate an App restart
with the owners of active work when needed; authorization for diagnosis alone
is not authorization to interrupt them. Retain thread IDs and native Goal
accounting. A CLI resume is not a second writer for an already active thread.

Read [the Linux adapter](references/linux-binding.md) before building or running
`scripts/shared_app_launcher.cpp`. It observes genuine App startup, verifies
profile/process/pipe ownership and applies the two selected MCP definitions via
supported config APIs. It supplies no daemon, proxy, network listener or auth
shim. Installed Node/CLI/manifest paths are caller-selected.

Snapshot only the entries being changed, retain original command/args and tool
approval settings, then reload and read effective config back. An explicitly
disabled entry stays disabled. If a write's outcome is uncertain, inspect the
effective config before retrying. Permission/identity failures need their own
diagnosis; a different account or endpoint does not erase them.

## Accept and recover

Read [verification and limits](references/verification.md). Confirm the actual
normal startup entry, same daemon PID, a fresh owned pipe after App restart,
real ordinary tool calls and original retained contexts. A fresh default test
caller detects failures hidden by per-thread overrides. Keep isolated tests,
production changes and model calls separate in the result.

Use the selected-entry snapshot for config rollback and original entry files
for launcher rollback. Do not repeat the whole cutover after a successful
transaction. Keep source version, result, failure evidence and remaining
capability limits in the task's existing record.

The tested `openai/userVerification` path remains local-stdio-only. Signed
workspace/browser flows, menu-triggered relaunch and concurrent local App
profiles need their own evidence; ordinary successful calls do not certify them.
