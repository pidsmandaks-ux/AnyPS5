#include "prx/libc/include/General.hpp"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

namespace {
void SetEnv(const char* name, const std::string& value) {
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}
void UnsetEnv(const char* name) {
#ifdef _WIN32
    _putenv_s(name, "");
#else
    unsetenv(name);
#endif
}
}

int main() {
    const auto file = std::filesystem::temp_directory_path() / "anyps5_diagnostics_test.log";
    std::error_code error;
    std::filesystem::remove(file, error);
    SetEnv("ANYPS5_DIAGNOSTICS", "1");
    SetEnv("ANYPS5_DIAGNOSTICS_FILE", file.string());
    UnsetEnv("ANYPS5_DIAGNOSTICS_ALL");

    if (!AnyPs5DiagnosticsEnabled_nid_no_patch()) return 1;
    AnyPs5Diagnostic_nid_no_patch("test", "entry", "first");
    AnyPs5Diagnostic_nid_no_patch("test", "entry", "second");

    std::ifstream input(file);
    if (!input) return 2;
    std::string line;
    std::size_t lines = 0;
    bool first = false, second = false;
    while (std::getline(input, line)) {
        if (line.find("category=test") == std::string::npos) return 3;
        if (line.find("name=entry") == std::string::npos) return 4;
        first = first || line.find("detail=first") != std::string::npos;
        second = second || line.find("detail=second") != std::string::npos;
        ++lines;
    }
    std::filesystem::remove(file, error);
    return lines == 2 && first && second ? 0 : 5;
}
