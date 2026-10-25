file(SHA256 "${FORMATTER}" ACTUAL)
if(NOT ACTUAL STREQUAL EXPECTED)
    message(FATAL_ERROR "Pinned formatter changed")
endif()
