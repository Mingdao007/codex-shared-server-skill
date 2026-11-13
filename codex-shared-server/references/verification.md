# Evidence, acceptance and compatibility

## What to test

| Layer | Useful evidence | Does not establish |
|---|---|---|
| Transport | correct private socket, initialize response | tools, caller identity or context visibility |
| Catalog | MCP connected and expected tools present | successful tool execution |
| Ordinary call | actual read-only project/context result | every signed or privileged flow |
| Retained work | same thread IDs and native Goal/accounting | automatic continuation or owner adoption |
| Restart | same daemon, new genuine pipe, old/new callers work | every relaunch path or daemon crash recovery |
| Production | normal installed entry, actual process/config/call readback | results of an isolated fixture alone |

Use a genuine default ephemeral caller when the installed protocol supports it;
inspect existing threads read-only and unsubscribe the test caller. Do not start
a model turn or a competing writer just to probe. Preserve an ambiguous send's
outcome and read the recipient before resending. Message acceptance, actual
recipient input and substantive continuation are separate observations.

After an authorized App restart, verify original contexts and native Goal identity,
status and cumulative accounting. Avoid creating a replacement Goal or editing its
accounting. The shared backend is not a new grant of device or resource ownership.

## Tested baseline and portable-adapter scope

The original workflow was validated with Linux App build **26.1007.71326**,
bundled CLI **0.162.0-alpha.17.2**, and official daemon **0.167.0**. Those exact
installed versions were observed; this is not a claim about current releases.
The private baseline had real isolated App restart/automatic binding and scoped
rollback tests, followed by production tool calls and retained-context recovery.
Live logs, UUIDs, PIDs, account/session data and private task evidence are excluded
from this repository. Tool counts are observations, never fixed acceptance targets.

The published adapter exposes Node/CLI paths, supports an absent review plugin,
preserves inherited CPU affinity rather than private bench CPU choices, and checks
private socket ownership for snapshot/rollback as well as binding. The portable default path also passed real isolated App restart on that matrix:
same daemon, new pipe, original/new callers, real project calls and restored test
configuration; all owned test processes were reaped. Protocol fixtures separately
exercise configuration preservation, disabled-user entries, private sockets,
rollback and uncertain write outcomes. They are labelled as fixtures. Use the
real installed App procedure to qualify a new build; the original production result does not certify every
public-adapter option or machine.

## Known limits

- The inspected `openai/userVerification` predicate requires local, initialized,
  connected **stdio**. The shared WebSocket route does not satisfy it.
- Signed workspace/browser operations need actual tests; `list_projects` does not
  establish their identity/signature compatibility. Keep vendor peer checks intact.
- Normal entry startup/restart is covered by the original implementation tests;
  internal Electron menu relaunch without inherited stdout is not.
- Multiple independent local App profiles are not a verified topology here.
- Startup log markers, config schemas and plugin layouts can change by version.
  Inspect the installed version before adapting; preserve useful existing work.

## Upstream reading

- [Official App Server documentation](https://learn.chatgpt.com/docs/app-server)
- [Official protocol README](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [Issue 47425](https://github.com/openai/codex/issues/47425): a matching shared-daemon App-tool binding report.
- [Issue 41014](https://github.com/openai/codex/issues/41014): a matching App/private-backend routing report.

The issue links are third-party reports in the upstream tracker, not evidence of
a released fix. The workflow's claims are limited to the installed-code inspection
and explicitly described experiments. No App/vendor code is distributed here.
