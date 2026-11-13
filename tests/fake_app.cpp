#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <sys/wait.h>

int main(int argc, char** argv) {
    if (argc != 4) return 64;
    std::string profile = argv[1], path = argv[2], trace = argv[3];
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    sockaddr_un address{}; address.sun_family = AF_UNIX;
    if (path.size() >= sizeof(address.sun_path)) return 65;
    std::strcpy(address.sun_path, path.c_str());
    if (bind(fd, reinterpret_cast<sockaddr*>(&address), sizeof(address))) return 66;
    if (chmod(path.c_str(), 0600) || listen(fd, 1)) return 67;
    pid_t holder = -1;
    if (std::getenv("FIXTURE_FOREIGN_OWNER")) {
        holder = fork();
        if (!holder) { usleep(1500000); _exit(0); }
        close(fd);
    }
    std::string lock = profile + "/SingletonLock";
    unlink(lock.c_str());
    if (symlink((std::string("fixture-host-") + std::to_string(getpid())).c_str(), lock.c_str())) return 68;
    const char* url = std::getenv("CODEX_APP_SERVER_WS_URL");
    const char* force = std::getenv("CODEX_APP_SERVER_FORCE_CLI");
    std::ofstream env(trace); env << "URL=" << (url ? url : "<unset>") << '\n' << "FORCE=" << (force ? force : "<unset>") << '\n'; env.close();
    std::cout << "FIXTURE_UNFILTERED_WARNING should remain visible" << std::endl;
    std::cout << "dynamic_app_tools_listening pipePath=" << path << std::endl;
    std::cout << "Host startup critical-path fixture" << std::endl;
    if (std::getenv("FIXTURE_DUPLICATE_MARKER")) {
        usleep(250000);
        std::cout << "dynamic_app_tools_listening pipePath=" << path << std::endl;
        std::cout << "Host startup critical-path fixture" << std::endl;
    }
    usleep(700000);
    if (holder > 0) waitpid(holder, nullptr, 0); else close(fd);
    if (std::getenv("FIXTURE_DISTINCT_STREAMS")) {
        std::cout << "FIXTURE_STDOUT_LINE" << std::endl;
        std::cerr << "FIXTURE_STDERR_LINE" << std::endl;
    }
    if (std::getenv("FIXTURE_PARTIAL_TAIL")) std::cout << "FIXTURE_UNTERMINATED_TAIL" << std::flush;
    unlink(path.c_str());
    return 0;
}
