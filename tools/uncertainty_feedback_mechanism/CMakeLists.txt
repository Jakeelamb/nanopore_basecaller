cmake_minimum_required(VERSION 3.25)
project(targeting_mechanism LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
if(NOT TARGETING_SOURCE_CUT_SHA256 MATCHES "^[0-9a-f]+$")
  message(FATAL_ERROR "An explicit mechanism source census SHA256 is required")
endif()
string(LENGTH "${TARGETING_SOURCE_CUT_SHA256}" TARGETING_SOURCE_CUT_LENGTH)
if(NOT TARGETING_SOURCE_CUT_LENGTH EQUAL 64)
  message(FATAL_ERROR "Mechanism source census SHA256 must contain 64 hex digits")
endif()
find_package(OpenSSL REQUIRED COMPONENTS Crypto)
find_package(ZLIB REQUIRED)
set(TARGETING_JSON_INCLUDE "/home/jake/Projects/tools/clang-uml-src/thirdparty/nlohmann" CACHE PATH "Pinned read-only JSON header directory")
function(targeting_executable name source)
  add_executable(${name} ${source} mechanism.h)
  target_include_directories(${name} SYSTEM PRIVATE "${TARGETING_JSON_INCLUDE}")
  target_compile_definitions(${name} PRIVATE TARGETING_SOURCE_CUT_SHA256="${TARGETING_SOURCE_CUT_SHA256}")
  target_compile_options(${name} PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Werror -fno-fast-math -ffp-contract=off)
  target_link_libraries(${name} PRIVATE OpenSSL::Crypto ZLIB::ZLIB)
endfunction()
targeting_executable(targeting-mechanism main.cpp)
targeting_executable(targeting-mechanism-controls controls.cpp)
enable_testing()
add_test(NAME targeting-mechanism-controls COMMAND targeting-mechanism-controls)

add_custom_target(format-check
  COMMAND /usr/bin/clang-format --dry-run --Werror
    --style=file:${CMAKE_CURRENT_SOURCE_DIR}/.clang-format --sort-includes=false
    ${CMAKE_CURRENT_SOURCE_DIR}/mechanism.h
    ${CMAKE_CURRENT_SOURCE_DIR}/main.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/controls.cpp
  VERBATIM
)
