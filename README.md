# Codex Shared Server

A reusable **Codex skill** and optional authored **Linux C++ adapter** for making
Codex Desktop App and CLI use the same local backend while keeping existing work.

[简体中文](README.zh-CN.md)

## What ships

- `codex-shared-server/SKILL.md`: diagnose actual backend ownership, stale App-tool
  pipes, catalogs versus useful calls, retained contexts, and scoped recovery.
- `references/`: the observed mechanism, supported-config procedure, verification
  layers, tested versions and explicit compatibility limits.
- `scripts/`: C++17 dynamic-pipe binder, CMake build and explicit launch wrapper.

This is a community integration, not an official OpenAI product. It ships no App,
plugin runtime, authentication file, proprietary source or private experiment data.

## Install and use

Use your Codex skill installer to install the **`codex-shared-server/` directory
from this repository**, or copy that directory into your configured skills root.
Installing a skill does not change the App, daemon, desktop entry or permissions.

Ask Codex:

> Use $codex-shared-server to check whether my App and CLI share the same backend,
> resolve the actual routing issue, and preserve my active tasks.

Other useful requests:

- “CLI says notLoaded but the App is working. Check actual ownership.”
- “App tools disappeared after restart. Identify and rebind the genuine pipe.”
- “Verify retained contexts and roll back only the entries this change touched.”

The workflow starts read-only. If the Linux adapter fits the installed build,
[build and configure it](codex-shared-server/references/linux-binding.md) with the
**actual installed paths**. It does not discover credentials, start a daemon,
restart the live App, modify login files or install a background service for you.
Coordinate any required interruption with the owners of current work.

## Evidence and scope

The originating implementation passed real isolated App restart, same-daemon
retained-context tests, selected-entry rollback, then production ordinary tool
calls and original-context recovery. The portable adapter has separately scoped
package tests. See [verification](codex-shared-server/references/verification.md).

Observed versions: Linux App **26.1007.71326**, bundled CLI **0.162.0-alpha.17.2**,
official daemon **0.167.0**. These are a historical tested matrix, not current
release recommendations or a guarantee for all Linux installs.

`openai/userVerification` remained stdio-only. Signed workspace/browser flows,
internal-menu relaunch and concurrent App profiles were not all verified. Real
ordinary calls do not establish full feature parity. No identity checks are
bypassed, and a network or permission denial is not permission to switch routes.

## Privacy

Only reusable instructions and authored portable helper source are published.
Live configs, sockets/UUIDs, host paths, credentials, session/Goal data, screenshots
and operating logs stay local. Treat your own diagnostics and rollback snapshots
as private too. The helper uses the existing owner-only local Unix socket and
creates no public listener, proxy or persistent service.

## Repository layout

```text
README.md
README.zh-CN.md
LICENSE
CHANGELOG.md
codex-shared-server/
  SKILL.md
  agents/openai.yaml
  references/linux-binding.md
  references/verification.md
  scripts/CMakeLists.txt
  scripts/shared_app_launcher.cpp
  scripts/launch-shared-app.sh
```

MIT licensed. Boost/jsoncpp and the installed Codex software retain their own
licenses; their code and binaries are not vendored here.
