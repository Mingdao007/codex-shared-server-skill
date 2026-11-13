#!/usr/bin/env bash
set -eu
: "${CODEX_SHARED_SERVER_SOCKET:?set the existing private daemon socket}"
: "${CODEX_SHARED_APP_DEFINITION:?set the installed App MCP manifest}"
: "${CODEX_SHARED_PROFILE:?set the existing App profile}"
: "${CODEX_SHARED_APP_EXECUTABLE:?set the actual App executable}"
: "${CODEX_SHARED_NODE:?set the installed bundled Node executable}"
: "${CODEX_SHARED_CLI:?set the installed bundled CLI executable}"
: "${CODEX_SHARED_LAUNCHER:?set the compiled C++ launcher}"
[[ "${1:-}" != -- ]] || shift
if [[ $# -eq 0 ]]; then printf 'usage: %s -- original-App-command [args ...]\n' "$0" >&2; exit 64; fi
socket_target=$(readlink -f -- "$CODEX_SHARED_SERVER_SOCKET")
[[ -S "$socket_target" ]] || { printf 'existing daemon socket unavailable\n' >&2; exit 69; }
# Validate before launching the App; a snapshot is read-only and discarded here.
"$CODEX_SHARED_LAUNCHER" --socket "$socket_target" --snapshot >/dev/null
unset CODEX_APP_SERVER_FORCE_CLI
export CODEX_APP_SERVER_WS_URL="ws+unix://localhost${socket_target}:/rpc"
args=(--socket "$socket_target" --definition "$CODEX_SHARED_APP_DEFINITION"
      --profile "$CODEX_SHARED_PROFILE" --app-executable "$CODEX_SHARED_APP_EXECUTABLE"
      --node-path "$CODEX_SHARED_NODE" --cli-path "$CODEX_SHARED_CLI")
if [[ -n "${CODEX_SHARED_REVIEW_DEFINITION:-}" ]]; then args+=(--review-definition "$CODEX_SHARED_REVIEW_DEFINITION"); fi
exec "$CODEX_SHARED_LAUNCHER" "${args[@]}" -- "$@"
