#include "context_decision/decision.h"
#include <iostream>
int main() {
    try {
        std::cout << context_decision::controls() << " controls passed\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
