cmake_minimum_required(VERSION 3.25)
project(context_decoder VERSION 0.1.0 LANGUAGES CXX)
include(CTest)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
find_package(OpenSSL REQUIRED COMPONENTS Crypto)
find_program(CONTEXT_CLANG_FORMAT NAMES clang-format REQUIRED)
set(CONTEXT_CPP_SOURCES
    include/context_decoder/decoder.h
    include/context_decoder/io.h
    include/context_decoder/controls.h
    src/decoder.cpp
    src/io.cpp
    src/json.cpp
    src/main.cpp
    tests/controls.cpp
    tests/main.cpp)
file(GLOB_RECURSE CONTEXT_ACTUAL_CPP RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}" CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/include/*.h" "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/*.cpp")
set(CONTEXT_EXPECTED_CPP ${CONTEXT_CPP_SOURCES})
list(SORT CONTEXT_ACTUAL_CPP)
list(SORT CONTEXT_EXPECTED_CPP)
if(NOT CONTEXT_ACTUAL_CPP STREQUAL CONTEXT_EXPECTED_CPP)
    message(FATAL_ERROR "Explicit owned C++ source census is incomplete")
endif()
set(CONTEXT_SOURCE_CLOSURE ${CONTEXT_CPP_SOURCES}
    CMakeLists.txt .clang-format context_inputs.py verify_formatter.cmake
    process_guard.py process_supervisor.py process-guard-provenance.json evidence.py
    ../../scripts/context-feedback.py
    ../../config/context-feedback-dev-v1.json
    ../../tests/test_context_feedback.py ../../scripts/record-command.sh
    /home/jake/Projects/nanopore_basecaller-retrieval/tools/catalogue_bridge/verify-receipt.py)
set(CONTEXT_WITNESS "#pragma once\n#include <cstdint>\nnamespace context_decoder {\nstruct CompiledSource { const char* path; const char* sha256; std::uintmax_t size; };\ninline constexpr CompiledSource compiled_sources[] = {\n")
foreach(relative IN LISTS CONTEXT_SOURCE_CLOSURE)
    if(IS_ABSOLUTE "${relative}")
        set(absolute "${relative}")
    else()
        get_filename_component(absolute "${CMAKE_CURRENT_SOURCE_DIR}/${relative}" ABSOLUTE)
    endif()
    file(SHA256 "${absolute}" digest)
    file(SIZE "${absolute}" byte_count)
    string(APPEND CONTEXT_WITNESS "{\"${absolute}\",\"${digest}\",${byte_count}},\n")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${absolute}")
endforeach()
file(SHA256 "${CONTEXT_CLANG_FORMAT}" format_digest)
string(APPEND CONTEXT_WITNESS "};\ninline constexpr const char* pinned_clang_format = \"${CONTEXT_CLANG_FORMAT}\";\ninline constexpr const char* pinned_clang_format_sha256 = \"${format_digest}\";\ninline constexpr const char* compiler_path = \"${CMAKE_CXX_COMPILER}\";\n}\n")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/compiled_sources.h" "${CONTEXT_WITNESS}")
add_library(context_decoder STATIC src/decoder.cpp src/io.cpp src/json.cpp tests/controls.cpp)
target_include_directories(context_decoder PUBLIC include PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
target_link_libraries(context_decoder PUBLIC OpenSSL::Crypto)
target_compile_options(context_decoder PUBLIC -Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off)
add_executable(context-decoder src/main.cpp)
target_include_directories(context-decoder PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
target_link_libraries(context-decoder PRIVATE context_decoder)
set(FORMAT_ABSOLUTE_SOURCES)
foreach(relative IN LISTS CONTEXT_CPP_SOURCES)
    list(APPEND FORMAT_ABSOLUTE_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/${relative}")
endforeach()
add_custom_target(format-check
    COMMAND "${CMAKE_COMMAND}" "-DFORMATTER=${CONTEXT_CLANG_FORMAT}" "-DEXPECTED=${format_digest}"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/verify_formatter.cmake"
    COMMAND "${CONTEXT_CLANG_FORMAT}" --dry-run --Werror ${FORMAT_ABSOLUTE_SOURCES}
    COMMAND_EXPAND_LISTS VERBATIM)
if(BUILD_TESTING)
    add_executable(context-decoder-tests tests/main.cpp)
    target_link_libraries(context-decoder-tests PRIVATE context_decoder)
    add_test(NAME independent_decoder_controls COMMAND context-decoder-tests)
    set_tests_properties(independent_decoder_controls PROPERTIES TIMEOUT 30)
endif()
