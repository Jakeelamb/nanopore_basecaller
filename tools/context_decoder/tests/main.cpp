#include "context_decoder/controls.h"
#include "context_decoder/guarded.h"

#include <exception>
#include <iostream>
int main() {
    try {
        std::cout << context_decoder::run_controls() << '\n';
        std::cout << context_decoder::run_guarded_controls() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
