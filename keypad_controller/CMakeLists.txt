cmake_minimum_required(VERSION 3.15)
project(GamePad)

include(GenerateG1A)
include(GenerateG3A)
include(GenerateHH2Bin)
include(Fxconv)
find_package(Gint 2.9 REQUIRED)

set(SOURCES
  src/main.c
)

set(ASSETS)

set(ASSETS_fx)

set(ASSETS_cg)

add_executable(gamepad ${SOURCES} ${ASSETS} ${ASSETS_${FXSDK_PLATFORM}})
target_compile_options(gamepad PRIVATE -Wall -Wextra -Os -g -flto)
target_link_libraries(gamepad Gint::Gint)

if("${FXSDK_PLATFORM_LONG}" STREQUAL fx9860G)
  generate_g1a(TARGET gamepad OUTPUT "gamepad.g1a"
    NAME "GamePad" ICON assets-fx/icon.png)
elseif("${FXSDK_PLATFORM_LONG}" STREQUAL fxCG50)
  generate_g3a(TARGET gamepad OUTPUT "gamepad.g3a"
    NAME "GamePad" ICONS assets-cg/icon-uns.png assets-cg/icon-sel.png)
elseif("${FXSDK_PLATFORM_LONG}" STREQUAL fx9860G_G3A)
  generate_g3a(TARGET gamepad OUTPUT "gamepad-fx.g3a"
    NAME "GamePad-fx" ICONS assets-cg/icon-uns.png assets-cg/icon-sel.png)
elseif("${FXSDK_PLATFORM_LONG}" STREQUAL fxCP)
  generate_hh2_bin(TARGET gamepad OUTPUT "gamepad-hh2.bin")
endif()
