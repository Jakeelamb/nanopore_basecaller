file(SHA256 "${FORMATTER}" actual)
if(NOT actual STREQUAL EXPECTED)
    message(FATAL_ERROR "Pinned clang-format changed")
endif()
