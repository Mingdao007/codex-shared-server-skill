// App-scoped startup binding; no listener, service, credential access or model call.
#include <boost/asio/local/stream_protocol.hpp>
#include <boost/beast/core.hpp>
#include <boost/beast/websocket.hpp>
#include <json/json.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
namespace net = boost::asio;
namespace websocket = boost::beast::websocket;
using JsonValue = Json::Value;

static std::string read_file(const fs::path& p) {
    std::ifstream in(p, std::ios::binary);
    if (!in) throw std::runtime_error("cannot read " + p.string());
    return {std::istreambuf_iterator<char>(in), {}};
}
static JsonValue parse(const std::string& s) {
    Json::CharReaderBuilder builder;
    JsonValue value; std::string error; std::istringstream in(s);
    if (!Json::parseFromStream(builder, in, &value, &error))
        throw std::runtime_error("invalid JSON response/configuration");
    return value;
}
static std::string json(const JsonValue& value) {
    Json::StreamWriterBuilder b; b["indentation"] = "";
    return Json::writeString(b, value);
}
static void event(const std::string& kind, const JsonValue& detail = JsonValue{}) {
    JsonValue value = detail; value["event"] = kind;
    std::cerr << "shared_app_binding " << json(value) << std::endl;
}

class Rpc {
    net::io_context context;
    websocket::stream<net::local::stream_protocol::socket> socket{context};
    int id = 0;
public:
    explicit Rpc(const std::string& path) {
        socket.next_layer().connect(net::local::stream_protocol::endpoint(path));
        socket.handshake("localhost", "/rpc");
        JsonValue p;
        p["clientInfo"]["name"] = "shared_app_startup_binding";
        p["clientInfo"]["version"] = "1";
        p["capabilities"]["experimentalApi"] = true;
        call("initialize", p);
        JsonValue notification; notification["method"] = "initialized";
        socket.write(net::buffer(json(notification)));
    }
    JsonValue call(const std::string& method, const JsonValue& params) {
        JsonValue request; request["id"] = ++id;
        request["method"] = method; request["params"] = params;
        socket.write(net::buffer(json(request)));
        for (;;) {
            boost::beast::flat_buffer buffer;
            socket.read(buffer);
            auto reply = parse(boost::beast::buffers_to_string(buffer.data()));
            if (reply["id"] != request["id"]) continue;
            if (reply.isMember("error"))
                throw std::runtime_error("RPC " + method + ": " + json(reply["error"]));
            return reply["result"];
        }
    }
};

struct Options {
    std::string socket, definition, review_definition, profile, executable, pipe;
    std::string restore;
    std::string node_path = "/usr/lib/chatgpt/resources/cua_node/bin/node";
    std::string cli_path = "/usr/lib/chatgpt/resources/codex";
    bool bind_only = false, snapshot = false;
    std::vector<std::string> command;
};

static pid_t validate_pipe(const Options& o, const std::string& pipe) {
    struct stat meta{};
    if (pipe.rfind("/tmp/codex-browser-use/", 0) != 0 ||
        lstat(pipe.c_str(), &meta) || !S_ISSOCK(meta.st_mode) ||
        meta.st_uid != getuid() || (meta.st_mode & 0777) != 0600)
        throw std::runtime_error("App pipe is not the expected owner-only socket");
    auto lock = fs::read_symlink(fs::path(o.profile) / "SingletonLock").string();
    auto dash = lock.rfind('-');
    if (dash == std::string::npos || lock.find_first_not_of("0123456789", dash + 1) != std::string::npos)
        throw std::runtime_error("App profile does not identify a main process");
    pid_t pid = std::stoi(lock.substr(dash + 1));
    fs::path proc = fs::path("/proc") / std::to_string(pid);
    if (stat(proc.c_str(), &meta) || meta.st_uid != getuid() ||
        fs::canonical(proc / "exe") != fs::canonical(o.executable))
        throw std::runtime_error("profile owner is not the selected App executable");
    std::set<std::string> owned;
    for (auto const& entry : fs::directory_iterator(proc / "fd")) {
        std::error_code error; auto target = fs::read_symlink(entry.path(), error).string();
        if (!error) owned.insert(target);
    }
    std::istringstream lines(read_file("/proc/net/unix")); std::string line;
    while (std::getline(lines, line)) {
        std::istringstream row(line);
        std::string a,b,c,d,e,f,inode,path;
        if (row >> a >> b >> c >> d >> e >> f >> inode >> path)
            if (path == pipe && owned.count("socket:[" + inode + "]")) return pid;
    }
    throw std::runtime_error("pipe is not owned by the profile's actual App process");
}

static fs::path private_socket(const std::string& path) {
    struct stat meta{};
    fs::path socket_path = fs::canonical(path);
    if (stat(socket_path.c_str(), &meta) || !S_ISSOCK(meta.st_mode) ||
        meta.st_uid != getuid() || (meta.st_mode & 0077))
        throw std::runtime_error("shared daemon socket is not private");
    if (stat(socket_path.parent_path().c_str(), &meta) || meta.st_uid != getuid() || (meta.st_mode & 0077))
        throw std::runtime_error("shared daemon socket directory is not private");
    return socket_path;
}

static void bind(const Options& o, const std::string& pipe) {
    auto pid = validate_pipe(o, pipe);
    auto socket_path = private_socket(o.socket);
    Rpc rpc(socket_path.string());
    JsonValue read; read["includeLayers"] = false;
    auto before = rpc.call("config/read", read)["config"]["mcp_servers"];
    JsonValue write, expected;
    std::vector<std::pair<std::string,std::string>> definitions{{"codex_app", o.definition}};
    if (!o.review_definition.empty()) definitions.push_back({"code-review", o.review_definition});
    for (auto const& [name, path] : definitions) {
        auto definition = parse(read_file(path))["mcpServers"][name];
        if (!definition.isObject()) throw std::runtime_error(name + " definition missing");
        auto current = before[name];
        if (!current.isNull()) {
            if (current.isMember("enabled") && current["enabled"] == false)
                throw std::runtime_error("explicitly disabled user MCP entry: " + name);
            if (current["command"] != definition["command"] || current["args"] != definition["args"])
                throw std::runtime_error("existing user MCP command differs: " + name);
            definition = current;
        }
        fs::path cwd = definition.get("cwd", ".").asString();
        if (cwd.is_relative()) definition["cwd"] = fs::weakly_canonical(fs::path(path).parent_path() / cwd).string();
        definition["enabled"] = true;
        if (name == "codex_app") definition["env"]["CODEX_APP_TOOLS_PIPE_PATH"] = pipe;
        definition["env"]["CODEX_MCP_NODE_PATH"] = o.node_path;
        definition["env"]["CODEX_CLI_PATH"] = o.cli_path;
        JsonValue edit;
        edit["keyPath"] = "mcp_servers." + name;
        edit["mergeStrategy"] = "replace"; edit["value"] = definition;
        write["edits"].append(edit); expected[name] = definition;
    }
    write["reloadUserConfig"] = true;
    rpc.call("config/batchWrite", write);
    auto actual = rpc.call("config/read", read)["config"]["mcp_servers"];
    for (const auto& name : expected.getMemberNames()) {
        auto a = actual[name], e = expected[name];
        if (a["command"] != e["command"] || a["args"] != e["args"] ||
            a["enabled"] != e["enabled"] || a["env"] != e["env"] || a["tools"] != e["tools"] ||
            a["default_tools_approval_mode"] != e["default_tools_approval_mode"] || a["cwd"] != e["cwd"])
            throw std::runtime_error("effective config/approval readback differs: " + name);
    }
    JsonValue detail; detail["app_pid"] = pid; detail["pipe"] = pipe;
    detail["original_approval_rules_retained"] = true;
    event("binding_verified", detail);
}

// A stalled maintenance RPC must not hang the App's stdout reader indefinitely.
// Timeout bounds maintenance waiting, not application performance. No blind retry.
static bool bounded_bind(const Options& o, const std::string& pipe) {
    pid_t child = fork();
    if (child < 0) throw std::runtime_error("fork binding worker failed");
    if (child == 0) {
        signal(SIGALRM, SIG_DFL); alarm(30);
        try { bind(o, pipe); _exit(0); }
        catch (const std::exception& e) {
            JsonValue d; d["error"] = e.what(); event("binding_failed", d); _exit(1);
        }
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
    if (WIFSIGNALED(status)) {
        JsonValue d; d["signal"] = WTERMSIG(status);
        d["outcome"] = "uncertain; read configuration before retrying";
        event("binding_interrupted", d);
    }
    return WIFEXITED(status) && WEXITSTATUS(status) == 0;
}

static volatile sig_atomic_t stop_signal = 0;
static void stop(int sig) { stop_signal = sig; }

int main(int argc, char** argv) {
    try {
        Options o;
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--") { for (++i; i < argc; ++i) o.command.push_back(argv[i]); break; }
            if (arg == "--bind-only") { o.bind_only = true; continue; }
            if (arg == "--snapshot") { o.snapshot = true; continue; }
            if (i + 1 >= argc) throw std::runtime_error("missing argument value");
            auto value = std::string(argv[++i]);
            if (arg == "--socket") o.socket = value;
            else if (arg == "--definition") o.definition = value;
            else if (arg == "--review-definition") o.review_definition = value;
            else if (arg == "--profile") o.profile = value;
            else if (arg == "--app-executable") o.executable = value;
            else if (arg == "--pipe") o.pipe = value;
            else if (arg == "--node-path") o.node_path = value;
            else if (arg == "--cli-path") o.cli_path = value;
            else if (arg == "--restore") o.restore = value;
            else throw std::runtime_error("unknown option " + arg);
        }
        if (o.snapshot || !o.restore.empty()) {
            if (o.socket.empty()) throw std::runtime_error("socket required");
            alarm(30);
            Rpc rpc(private_socket(o.socket).string());
            JsonValue request; request["includeLayers"] = false;
            auto current = rpc.call("config/read", request)["config"]["mcp_servers"];
            if (o.snapshot) {
                JsonValue saved;
                for (const std::string name : {"codex_app", "code-review"}) {
                    const JsonValue selected = current[name];
                    for (const auto& key : selected["env"].getMemberNames())
                        if (key != "CODEX_APP_TOOLS_PIPE_PATH" && key != "CODEX_MCP_NODE_PATH" &&
                            key != "CODEX_CLI_PATH" && key != "CODEX_APP_TOOLS_DEFERRED")
                            throw std::runtime_error("snapshot requires checking additional MCP env before copying");
                    saved[name] = selected;
                }
                std::cout << json(saved) << std::endl;
            } else {
                auto saved = parse(read_file(o.restore));
                JsonValue write;
                for (const std::string name : {"codex_app", "code-review"}) {
                    if (!saved.isMember(name)) throw std::runtime_error("rollback entry missing");
                    JsonValue edit; edit["keyPath"] = "mcp_servers." + name;
                    edit["value"] = saved[name]; edit["mergeStrategy"] = "replace";
                    write["edits"].append(edit);
                }
                write["reloadUserConfig"] = true;
                rpc.call("config/batchWrite", write);
                auto actual = rpc.call("config/read", request)["config"]["mcp_servers"];
                for (const std::string name : {"codex_app", "code-review"})
                    if (actual[name] != saved[name]) throw std::runtime_error("rollback readback mismatch");
                event("rollback_verified");
            }
            return 0;
        }
        if (o.socket.empty() || o.definition.empty() || o.profile.empty() || o.executable.empty())
            throw std::runtime_error("socket, App definition, profile and app-executable are required");
        if (o.bind_only) return bounded_bind(o, o.pipe) ? 0 : 1;
        if (o.command.empty()) throw std::runtime_error("App launch command is required");
        int output[2]; if (pipe(output)) throw std::runtime_error("pipe failed");
        pid_t child = fork(); if (child < 0) throw std::runtime_error("App fork failed");
        if (!child) {
            close(output[0]); dup2(output[1], STDOUT_FILENO); dup2(output[1], STDERR_FILENO);
            close(output[1]);
            std::vector<char*> args;
            for (auto& s : o.command) args.push_back(s.data());
            args.push_back(nullptr);
            execvp(args[0], args.data()); _exit(127);
        }
        close(output[1]);
        struct sigaction sa{}; sa.sa_handler = stop;
        sigaction(SIGTERM, &sa, nullptr); sigaction(SIGINT, &sa, nullptr);
        std::string pending, selected, line; bool ready = false;
        char buffer[4096];
        for (;;) {
            if (stop_signal) { kill(child, stop_signal); break; }
            auto count = read(output[0], buffer, sizeof(buffer));
            if (count < 0) { if (errno == EINTR) continue; break; }
            if (count == 0) break;
            line.append(buffer, count);
            for (;;) {
                auto end = line.find('\n'); if (end == std::string::npos) break;
                auto entry = line.substr(0, end); line.erase(0, end + 1);
                std::cerr << entry << std::endl;
                auto start = entry.find("dynamic_app_tools_listening");
                if (start != std::string::npos) {
                    auto key = entry.find("pipePath=", start);
                    if (key != std::string::npos) {
                        key += 9; auto last = entry.find_first_of(" \t\r", key);
                        auto path = entry.substr(key, last - key);
                        if (path != pending) { pending = path; ready = false; }
                    }
                }
                if (entry.find("Host startup critical-path") != std::string::npos) ready = true;
                if (ready && !pending.empty() && selected != pending) {
                    selected = pending; bounded_bind(o, pending);
                }
            }
        }
        if (!line.empty()) std::cerr << line << std::flush;
        close(output[0]); int status = 0;
        while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
        return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    } catch (const std::exception& e) {
        JsonValue d; d["error"] = e.what(); event("launcher_failed", d); return 1;
    }
}
