#include "context_sample_feedback/sample.h"
#include <iostream>
int main() {
    try {
        const auto count = context_sample_feedback::controls();
        std::cout << "{\"executed\":" << count << ",\"skipped\":0,\"passed\":true}\n";
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
