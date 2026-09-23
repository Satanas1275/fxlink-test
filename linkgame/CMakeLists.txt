cmake_minimum_required(VERSION 3.15)
project(LinkGame C ASM)

include(GenerateG1A)
find_package(Gint 2.9 REQUIRED)

set(SOURCES
  src/main.c
  src/syscalls.S
)

add_executable(linkgame ${SOURCES})
target_compile_options(linkgame PRIVATE -Wall -Wextra -Os -g -flto)
target_link_libraries(linkgame Gint::Gint)

if("${FXSDK_PLATFORM_LONG}" STREQUAL fx9860G)
  generate_g1a(TARGET linkgame OUTPUT "linkgame.g1a"
    NAME "LinkGame" ICON assets-fx/icon.png)
endif()