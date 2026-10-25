#include "prefix_feedback/feedback.h"

#include <iostream>

int main() {
    try {
        std::cout << prefix_feedback::controls() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
