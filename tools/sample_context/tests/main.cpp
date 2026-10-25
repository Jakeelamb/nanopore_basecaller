#include "sample_context/context.h"
#include <iostream>
int main() {
    try {
        std::cout << sample_context::controls() << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
