#include "context_model/model.h"
#include <iostream>

int main() {
    try {
        std::cout << context_model::qualify() << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
