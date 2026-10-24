#include "context_study/oracle.h"
#include <iostream>
int main() {
    try {
        std::cout << context_study::run_controls() << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
