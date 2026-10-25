#include "context_uncertainty/uncertainty.h"
#include <iostream>

int main() {
    try {
        std::cout << context_uncertainty::controls() << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
