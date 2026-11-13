# Synthetic shared-server adapter tests

This fixture exercises a supplied Linux C++ launcher and shell wrapper using an
in-process mock WebSocket RPC server and a synthetic C++ App. It does not start
Codex, call a model, read user Codex configuration, or connect to a production
socket. All configuration, process output, plugin definitions and thread-like
state in the tests are synthetic. These tests cannot establish real App/daemon
compatibility, actual MCP tool calls, retained context, identity or signed flows.

Requirements: Linux with `/proc`, a C++17 compiler, Python 3 and a `websockets`
installation that provides `websockets.sync.server.unix_serve` (tested with
version 16.0), plus a previously built launcher and its shell wrapper. The test
inherits the caller's CPU affinity and does not alter it. The fake App binds a
private socket within a newly created `/tmp/codex-browser-use/fixture-*`
directory so that the adapter's ownership checks are exercised. The fixture
removes only its own socket directory when done.

Run the fixture, substituting the two paths for the launcher and wrapper. The
script builds the fake App in its private temporary directory:

```sh
python3 reproduce.py \
  --launcher /absolute/path/to/shared-app-launcher \
  --wrapper /absolute/path/to/launch-shared-app.sh \
  --expect fixed
```

The test creates a private temporary working directory and prints the path of its
`results-fixed.jsonl`. Use `--fake-app` to supply a precompiled fixture or
`--cxx` to select a C++17 compiler. `--workdir` selects a dedicated empty private
directory for retained fixture evidence; never point it at a live profile or
production configuration. A nonzero exit or a Python assertion means the expected
fixture behavior was not met. Results labelled `COUNTEREXAMPLE_CONFIRMED` are
intentional observations in the mock setup: a bare, unwrapped App start does not
inherit the wrapper's routing, and the adapter does not automatically retry the
same pipe after an injected write failure. The latter is not an instruction to
blindly retry: a separate case confirms that an error response can follow an
applied write and that readback detects the applied state.

To reproduce only the two historical defects against an older launcher, use
`--expect baseline --old-focus`; this expects false success for independently
changed command, arguments and enabled state, and loss of synthetic App output.
The test writes `results-baseline.jsonl` in its private workdir. Do not use this
mode to characterize a build for which those defects are already fixed.

The broader fixture covers selected-entry snapshot and restore, including null
and non-null review entries; unrelated entries; new fake pipes on repeated
wrapped starts; explicit disable and mismatched command rejection; unexpected
environment keys; executable and pipe ownership; private-socket checks;
readback mismatches; error-before-write and error-after-write; and forwarding of
synthetic output, including an unterminated final fragment. It observes that the
wrapper merges the child's stdout and stderr into its own stderr.
