#!/usr/bin/env python3
"""Isolated synthetic App + websocket protocol tests; no real App, daemon or model."""
import argparse, copy, json, os, pathlib, subprocess, tempfile, threading, traceback
from websockets.sync.server import unix_serve

parser = argparse.ArgumentParser(description='Synthetic WebSocket and App fixture; no actual Codex App is launched')
parser.add_argument('--launcher', type=pathlib.Path, required=True, help='compiled shared-app-launcher to test')
parser.add_argument('--wrapper', type=pathlib.Path, required=True, help='launch-shared-app.sh to test')
parser.add_argument('--fake-app', type=pathlib.Path, help='precompiled fake_app fixture; otherwise build in the private workdir')
parser.add_argument('--cxx', default='c++', help='C++17 compiler for the fake App, default: c++')
parser.add_argument('--expect', choices=['baseline', 'fixed'], default='fixed')
parser.add_argument('--old-focus', action='store_true', help='only test pre-fix false verification and lost output')
parser.add_argument('--workdir', type=pathlib.Path, help='dedicated private fixture directory; default: new /tmp directory')
args = parser.parse_args()
if args.old_focus and args.expect != 'baseline': parser.error('--old-focus requires --expect baseline')
for path in [args.launcher, args.wrapper] + ([args.fake_app] if args.fake_app else []):
    if not path.is_file(): parser.error('missing test input: ' + str(path))
ROOT = (args.workdir or pathlib.Path(tempfile.mkdtemp(prefix='codex-shared-fixture-'))).resolve()
if args.workdir and ROOT.exists() and any(ROOT.iterdir()):
    parser.error('workdir must be empty so earlier evidence is not overwritten')
ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
if ROOT.stat().st_uid != os.getuid() or ROOT.stat().st_mode & 0o077:
    parser.error('workdir must be owned by the current user and inaccessible to group/other')
LAUNCHER = str(args.launcher.resolve())
WRAPPER = str(args.wrapper.resolve())
if args.fake_app:
    APP = str(args.fake_app.resolve())
else:
    APP = str(ROOT / 'fake_app')
    fixture_cpp = pathlib.Path(__file__).resolve().parent / 'fake_app.cpp'
    subprocess.run([args.cxx, '-std=c++17', '-Wall', '-Wextra', '-O0', str(fixture_cpp), '-o', APP],
                   env={'PATH': '/usr/bin:/bin', 'HOME': str(ROOT)}, check=True)
print('WORKDIR=' + str(ROOT), flush=True)
EXPECT_FIXED = args.expect == 'fixed'
PROFILE = ROOT / 'profile'
PROFILE.mkdir(mode=0o700, exist_ok=True)
DAEMON_DIR = ROOT / 'daemon'
DAEMON_DIR.mkdir(mode=0o700, exist_ok=True)
SOCKET = str(DAEMON_DIR / 'mock.sock')
BROWSER_PARENT = pathlib.Path('/tmp/codex-browser-use')
BROWSER_PARENT.mkdir(mode=0o700, exist_ok=True)
BROWSER_DIR = pathlib.Path(tempfile.mkdtemp(prefix='fixture-', dir=BROWSER_PARENT))
SOCKET_PATHS = []
REPORT = ROOT / ('results-fixed.jsonl' if EXPECT_FIXED else 'results-baseline.jsonl')
REPORT.write_text('')
base_entry = {
    'command': '/fixture/node', 'args': ['app-plugin.js'],
    'cwd': '/fixture/plugin',
    'env': {'CODEX_APP_TOOLS_DEFERRED': '1'},
    'enabled': True, 'tools': {'approve': ['read']},
    'default_tools_approval_mode': 'prompt'
}
base = {'codex_app': base_entry, 'other-service': {'command': '/fixture/unrelated', 'args': ['same']}}
manifest = ROOT / 'app-manifest.json'
manifest.write_text(json.dumps({'mcpServers': {'codex_app': copy.deepcopy(base_entry)}}))

class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()
    def reset(self, data=None):
        with self.lock:
            self.config = copy.deepcopy(base if data is None else data)
            self.requests = []
            self.fail_next_write = False
            self.error_after_write = False
            self.mutate_after_write = None
    def response(self, request):
        with self.lock:
            method = request.get('method')
            self.requests.append(copy.deepcopy(request))
            if method == 'initialize':
                return {'result': {'fixture': True}}
            if method == 'config/read':
                return {'result': {'config': {'mcp_servers': copy.deepcopy(self.config)}}}
            if method == 'config/batchWrite':
                if self.fail_next_write:
                    self.fail_next_write = False
                    return {'error': {'code': -32000, 'message': 'injected transient write failure'}}
                for edit in request['params']['edits']:
                    assert edit['keyPath'].startswith('mcp_servers.')
                    key = edit['keyPath'][len('mcp_servers.'):]
                    if edit['value'] is None: self.config.pop(key, None)
                    else: self.config[key] = copy.deepcopy(edit['value'])
                if self.mutate_after_write:
                    self.mutate_after_write(self.config)
                    self.mutate_after_write = None
                if self.error_after_write:
                    self.error_after_write = False
                    return {'error': {'code': -32001, 'message': 'injected failure after fixture applied write'}}
                return {'result': {'status': 'ok'}}
            raise ValueError('unexpected fixture RPC ' + str(method))
    def snapshot(self):
        with self.lock: return copy.deepcopy(self.config), copy.deepcopy(self.requests)
state = State()

def handler(ws):
    try:
        for raw in ws:
            request = json.loads(raw)
            if 'id' not in request: continue
            response = state.response(request)
            response['id'] = request['id']
            ws.send(json.dumps(response))
    except Exception:
        # Beast may close without a WebSocket close frame; record it in fixture log.
        with (ROOT / 'mock-errors.log').open('a') as f: f.write(traceback.format_exc() + '\n')

server = unix_serve(handler, SOCKET)
os.chmod(SOCKET, 0o600)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

count = 0

def proc(args, env=None):
    if env is None: env = {'PATH': '/usr/bin:/bin', 'HOME': str(ROOT)}
    result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=8)
    return {'args': args, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}

def snapshot(): return proc([LAUNCHER, '--socket', SOCKET, '--snapshot'])

def restore(path): return proc([LAUNCHER, '--socket', SOCKET, '--restore', str(path)])

def launch(*, flags=None, exe=APP):
    global count
    count += 1
    path = str(BROWSER_DIR / ('p' + str(count)))
    SOCKET_PATHS.append(path)
    envtrace = ROOT / ('env-' + str(count) + '.txt')
    envtrace.unlink(missing_ok=True)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(ROOT),
           'CODEX_SHARED_SERVER_SOCKET': SOCKET,
           'CODEX_SHARED_APP_DEFINITION': str(manifest),
           'CODEX_SHARED_PROFILE': str(PROFILE),
           'CODEX_SHARED_APP_EXECUTABLE': exe,
           'CODEX_SHARED_NODE': '/fixture/bundled/node',
           'CODEX_SHARED_CLI': '/fixture/bundled/codex',
           'CODEX_SHARED_LAUNCHER': LAUNCHER,
           'CODEX_APP_SERVER_FORCE_CLI': 'fixture-forced'}
    env.update(flags or {})
    result = proc(['bash', WRAPPER, '--', APP, str(PROFILE), path, str(envtrace)], env)
    result['fake_app_pipe'] = path
    result['fake_app_env'] = envtrace.read_text() if envtrace.exists() else None
    return result

def nwrite(requests): return sum(x.get('method') == 'config/batchWrite' for x in requests)

def emit(name, outcome, details):
    result = {'test': name, 'outcome': outcome, 'details': details}
    with REPORT.open('a') as f: f.write(json.dumps(result, sort_keys=True) + '\n')
    print(name + ': ' + outcome, flush=True)

try:
    if args.old_focus:
        for field, value in [('command', '/fixture/mutated'), ('args', ['mutated']), ('enabled', False)]:
            state.reset()
            state.mutate_after_write = lambda c, field=field, value=value: c['codex_app'].update({field: value})
            result = launch(); config, _ = state.snapshot()
            assert config['codex_app'][field] == value
            assert 'binding_verified' in result['stderr'] and 'binding_failed' not in result['stderr'], result
            emit('individual_changed_' + field + '_false_verified', 'COUNTEREXAMPLE_CONFIRMED', {'result': result, 'fixture_effective': config['codex_app']})
        state.reset()
        result = launch(flags={'FIXTURE_DISTINCT_STREAMS': '1', 'FIXTURE_PARTIAL_TAIL': '1'})
        assert 'binding_verified' in result['stderr']
        for marker in ['FIXTURE_STDOUT_LINE', 'FIXTURE_STDERR_LINE', 'FIXTURE_UNTERMINATED_TAIL']:
            assert marker not in result['stderr'] and marker not in result['stdout'], result
        emit('ordinary_app_output_discarded', 'COUNTEREXAMPLE_CONFIRMED', {'fake_app_emitted': ['FIXTURE_STDOUT_LINE', 'FIXTURE_STDERR_LINE', 'FIXTURE_UNTERMINATED_TAIL'], 'result': result})
        print('RESULTS=' + str(REPORT), flush=True)
        raise SystemExit(0)

    state.reset()
    initial = snapshot()
    assert initial['returncode'] == 0, initial
    original = json.loads(initial['stdout'])
    assert original['codex_app'] == base_entry and original['code-review'] is None
    saved = ROOT / 'selected-before.json'; saved.write_text(initial['stdout']); os.chmod(saved, 0o600)
    a = launch()
    c1, req1 = state.snapshot()
    assert a['returncode'] == 0 and 'binding_verified' in a['stderr'], a
    assert c1['codex_app']['env']['CODEX_APP_TOOLS_PIPE_PATH'] == a['fake_app_pipe']
    assert c1['codex_app']['env']['CODEX_APP_TOOLS_DEFERRED'] == '1'
    assert c1['codex_app']['command'] == base_entry['command'] and c1['codex_app']['args'] == base_entry['args']
    assert c1['codex_app']['tools'] == base_entry['tools'] and c1['other-service'] == base['other-service']
    assert a['fake_app_env'] == 'URL=ws+unix://localhost' + SOCKET + ':/rpc\nFORCE=<unset>\n'
    emit('normal_wrapper_binding', 'PASS', {'result': a, 'effective_fixture_config': c1, 'requests': req1})

    b = launch()
    c2, req2 = state.snapshot()
    assert 'binding_verified' in b['stderr'] and c2['codex_app']['env']['CODEX_APP_TOOLS_PIPE_PATH'] == b['fake_app_pipe']
    assert a['fake_app_pipe'] != b['fake_app_pipe'] and nwrite(req2) == 2
    emit('mock_app_restart_new_pipe_same_mock_daemon', 'PASS', {'first_pipe': a['fake_app_pipe'], 'second': b, 'writes': nwrite(req2)})

    direct_path = str(BROWSER_DIR / 'direct')
    SOCKET_PATHS.append(direct_path)
    direct_trace = ROOT / 'env-direct.txt'
    direct = proc([APP, str(PROFILE), direct_path, str(direct_trace)], {'PATH': '/usr/bin:/bin', 'HOME': str(ROOT)})
    direct['fake_app_env'] = direct_trace.read_text()
    direct_config, direct_req = state.snapshot()
    assert direct['returncode'] == 0 and direct['fake_app_env'] == 'URL=<unset>\nFORCE=<unset>\n'
    assert direct_config['codex_app']['env']['CODEX_APP_TOOLS_PIPE_PATH'] == b['fake_app_pipe'] and nwrite(direct_req) == 2
    emit('unwrapped_normal_entry_has_no_persistent_binding', 'COUNTEREXAMPLE_CONFIRMED', {'previous_wrapped_pipe': b['fake_app_pipe'], 'direct_pipe': direct_path, 'direct': direct, 'config_after': direct_config, 'total_writes_unchanged': nwrite(direct_req)})

    rr = restore(saved)
    after, req = state.snapshot()
    assert rr['returncode'] == 0 and 'rollback_verified' in rr['stderr'], rr
    assert after['codex_app'] == base_entry and after['other-service'] == base['other-service'] and 'code-review' not in after
    emit('fixture_rollback_preserves_unrelated_and_null', 'PASS', {'result': rr, 'config': after, 'last_request': req[-2:]})

    review_entry = {'command': '/fixture/review-node', 'args': ['review.js'], 'cwd': '/fixture/review', 'env': {'CODEX_APP_TOOLS_DEFERRED': 'review'}, 'enabled': True, 'tools': {'approve': ['review']}, 'default_tools_approval_mode': 'prompt'}
    review_manifest = ROOT / 'review-manifest.json'
    review_manifest.write_text(json.dumps({'mcpServers': {'code-review': review_entry}}))
    with_review = copy.deepcopy(base); with_review['code-review'] = copy.deepcopy(review_entry)
    state.reset(with_review)
    review_snapshot = snapshot(); assert review_snapshot['returncode'] == 0
    review_saved = ROOT / 'review-before.json'; review_saved.write_text(review_snapshot['stdout']); os.chmod(review_saved, 0o600)
    review_launch = launch(flags={'CODEX_SHARED_REVIEW_DEFINITION': str(review_manifest)})
    review_bound, review_req = state.snapshot()
    assert 'binding_verified' in review_launch['stderr']
    assert review_bound['code-review']['env']['CODEX_MCP_NODE_PATH'] == '/fixture/bundled/node'
    assert review_bound['code-review']['env']['CODEX_CLI_PATH'] == '/fixture/bundled/codex'
    assert review_bound['code-review']['env']['CODEX_APP_TOOLS_DEFERRED'] == 'review'
    assert review_bound['code-review']['tools'] == review_entry['tools']
    review_rollback = restore(review_saved); review_after, _ = state.snapshot()
    assert review_rollback['returncode'] == 0 and review_after == with_review
    emit('optional_review_binding_and_nonnull_rollback', 'PASS', {'launch': review_launch, 'bound': review_bound, 'rollback': review_rollback, 'restored': review_after, 'write_requests': [r for r in review_req if r.get('method') == 'config/batchWrite']})

    state.reset(); state.config['codex_app']['enabled'] = False
    disabled = launch(); config, req = state.snapshot()
    assert 'explicitly disabled' in disabled['stderr'] and 'binding_failed' in disabled['stderr'] and nwrite(req) == 0
    emit('disabled_entry_refuses_write', 'PASS', {'result': disabled, 'writes': nwrite(req)})

    state.reset(); state.config['codex_app']['command'] = '/fixture/other'
    mismatch = launch(); _, req = state.snapshot()
    assert 'existing user MCP command differs' in mismatch['stderr'] and nwrite(req) == 0
    emit('mismatched_command_refuses_write', 'PASS', {'result': mismatch, 'writes': nwrite(req)})

    state.reset(); state.config['codex_app']['env']['FIXTURE_EXTRA'] = 'fixture-value'
    extra = launch(); _, req = state.snapshot()
    assert extra['returncode'] != 0 and 'snapshot requires checking additional MCP env' in extra['stderr'] and extra['fake_app_env'] is None and nwrite(req) == 0
    emit('extra_env_snapshot_blocks_wrapper_before_launch', 'PASS', {'result': extra, 'writes': nwrite(req)})

    state.reset()
    badexe = launch(exe='/usr/bin/false'); _, req = state.snapshot()
    assert 'profile owner is not the selected App executable' in badexe['stderr'] and nwrite(req) == 0
    emit('wrong_app_executable_refuses_write', 'PASS', {'result': badexe, 'writes': nwrite(req)})

    state.reset()
    wrongowner = launch(flags={'FIXTURE_FOREIGN_OWNER': '1'}); _, req = state.snapshot()
    assert 'pipe is not owned by the profile' in wrongowner['stderr'] and nwrite(req) == 0, wrongowner
    emit('foreign_pipe_owner_refuses_write', 'PASS', {'result': wrongowner, 'writes': nwrite(req)})

    state.reset()
    state.mutate_after_write = lambda c: c['codex_app'].update({'command': '/fixture/wrong', 'args': ['changed'], 'enabled': False})
    changed = launch(); changed_config, req = state.snapshot()
    assert changed_config['codex_app']['command'] == '/fixture/wrong' and not changed_config['codex_app']['enabled']
    if EXPECT_FIXED:
        assert 'binding_failed' in changed['stderr'] and 'binding_verified' not in changed['stderr'], changed
        emit('changed_command_args_enabled_detected', 'PASS', {'result': changed, 'fixture_effective': changed_config['codex_app'], 'requests': req})
    else:
        assert 'binding_verified' in changed['stderr'] and 'binding_failed' not in changed['stderr'], changed
        emit('false_verified_changed_command_args_enabled', 'COUNTEREXAMPLE_CONFIRMED', {'result': changed, 'fixture_effective': changed_config['codex_app'], 'requests': req})

    for field, value in [('command', '/fixture/mutated'), ('args', ['mutated']), ('enabled', False)]:
        state.reset()
        state.mutate_after_write = lambda c, field=field, value=value: c['codex_app'].update({field: value})
        single = launch(); single_config, _ = state.snapshot()
        assert single_config['codex_app'][field] == value
        if EXPECT_FIXED:
            assert 'binding_failed' in single['stderr'] and 'binding_verified' not in single['stderr'], single
            emit('individual_changed_' + field + '_detected', 'PASS', {'result': single, 'fixture_effective': single_config['codex_app']})
        else:
            assert 'binding_verified' in single['stderr'] and 'binding_failed' not in single['stderr'], single
            emit('individual_changed_' + field + '_false_verified', 'COUNTEREXAMPLE_CONFIRMED', {'result': single, 'fixture_effective': single_config['codex_app']})

    state.reset(); state.fail_next_write = True
    retry = launch(flags={'FIXTURE_DUPLICATE_MARKER': '1'}); retried_config, req = state.snapshot()
    assert retry['returncode'] == 0 and 'binding_failed' in retry['stderr'] and nwrite(req) == 1
    assert retry['stderr'].count('dynamic_app_tools_listening') == 2 and retried_config['codex_app'] == base_entry
    emit('same_pipe_transient_error_no_retry', 'COUNTEREXAMPLE_CONFIRMED', {'result': retry, 'write_count': nwrite(req), 'fixture_config': retried_config, 'requests': req})

    state.reset(); state.error_after_write = True
    uncertain = launch(flags={'FIXTURE_DUPLICATE_MARKER': '1'}); uncertain_config, req = state.snapshot()
    assert 'binding_failed' in uncertain['stderr'] and nwrite(req) == 1
    assert uncertain_config['codex_app']['env']['CODEX_APP_TOOLS_PIPE_PATH'] == uncertain['fake_app_pipe']
    inspect_after = snapshot()
    assert inspect_after['returncode'] == 0 and json.loads(inspect_after['stdout'])['codex_app']['env']['CODEX_APP_TOOLS_PIPE_PATH'] == uncertain['fake_app_pipe']
    emit('error_after_write_requires_readback_before_retry', 'PASS', {'result': uncertain, 'snapshot_after': inspect_after, 'fixture_config': uncertain_config, 'write_count': nwrite(req)})

    state.reset(); state.mutate_after_write = lambda c: c['codex_app']['env'].update({'CODEX_CLI_PATH': '/fixture/incorrect'})
    badenv = launch(); _, req = state.snapshot()
    assert 'binding_failed' in badenv['stderr'] and 'readback differs' in badenv['stderr']
    emit('changed_env_readback_fails', 'PASS', {'result': badenv, 'write_count': nwrite(req)})

    state.reset(); state.mutate_after_write = lambda c: c['codex_app'].update({'command': '/fixture/rollback-mutated'})
    badrestore = restore(saved)
    assert badrestore['returncode'] != 0 and 'rollback readback mismatch' in badrestore['stderr']
    emit('rollback_readback_mismatch_fails', 'PASS', {'result': badrestore})

    state.reset(); os.chmod(SOCKET, 0o660)
    private = snapshot(); os.chmod(SOCKET, 0o600)
    assert private['returncode'] != 0 and 'shared daemon socket is not private' in private['stderr']
    emit('nonprivate_socket_rejected_before_rpc', 'PASS', {'result': private})

    if EXPECT_FIXED:
        assert 'FIXTURE_UNFILTERED_WARNING' in a['stderr'] or 'FIXTURE_UNFILTERED_WARNING' in a['stdout'], a
        emit('ordinary_app_output_forwarded', 'PASS', {'fake_app_emitted': 'FIXTURE_UNFILTERED_WARNING should remain visible', 'launcher_stdout': a['stdout'], 'launcher_stderr': a['stderr']})
    else:
        assert 'FIXTURE_UNFILTERED_WARNING' not in a['stderr'] and 'FIXTURE_UNFILTERED_WARNING' not in a['stdout']
        emit('ordinary_app_output_discarded', 'COUNTEREXAMPLE_CONFIRMED', {'fake_app_emitted': 'FIXTURE_UNFILTERED_WARNING should remain visible', 'launcher_stdout': a['stdout'], 'launcher_stderr': a['stderr']})

    if EXPECT_FIXED:
        state.reset()
        streams = launch(flags={'FIXTURE_DISTINCT_STREAMS': '1', 'FIXTURE_PARTIAL_TAIL': '1'})
        assert 'binding_verified' in streams['stderr']
        assert 'FIXTURE_STDOUT_LINE' in streams['stderr'] and 'FIXTURE_STDERR_LINE' in streams['stderr']
        assert 'FIXTURE_UNTERMINATED_TAIL' in streams['stderr'] and 'FIXTURE_UNTERMINATED_TAIL' not in streams['stdout']
        emit('unterminated_final_output_forwarded_streams_merged', 'PASS_WITH_NOTED_LIMIT', {'result': streams, 'fake_app_emitted_stdout': ['FIXTURE_STDOUT_LINE\n', 'FIXTURE_UNTERMINATED_TAIL'], 'fake_app_emitted_stderr': ['FIXTURE_STDERR_LINE\n']})
finally:
    server.shutdown(); thread.join(timeout=2)
    for path in SOCKET_PATHS:
        try: os.unlink(path)
        except FileNotFoundError: pass
    try: BROWSER_DIR.rmdir()
    except FileNotFoundError: pass
    try: os.unlink(SOCKET)
    except FileNotFoundError: pass
print('RESULTS=' + str(REPORT), flush=True)
