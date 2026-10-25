#include "context_prefix/prefix.h"
#include <iostream>
int main() {
    try {
        context_prefix::check_compiled_sources();
        context_prefix::initialise_cpu_threads();
        std::cout << context_prefix::run_controls() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
