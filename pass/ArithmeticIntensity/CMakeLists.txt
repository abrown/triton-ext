# Standalone, self-contained build for the ArithmeticIntensity pass extension.
#
# Unlike the umbrella build at the repository root, this project builds a single
# self-contained plugin library that:
#   - links ONLY against the Triton shared library shipped inside an installed
#     Triton wheel (`triton/_C/libtriton.so`), which re-exports the MLIR/LLVM
#     symbols it needs (Triton must be built with `TRITON_EXT_ENABLED=1`);
#   - compiles the extension-registration support code (`support/Export.cpp`)
#     directly into the plugin, so there is no separate `libTritonExtensionSupport.so`
#     to ship alongside the wheel.
#
# It still needs an LLVM/MLIR *build* environment for headers, `mlir-tblgen`, and
# the `AddMLIR`/`AddLLVM`/`TableGen` CMake modules; point it at one with
# `LLVM_INSTALL_DIR`. Triton is located from the active Python environment (or
# `-DTRITON_WHEEL_DIR`).
#
# This file is normally driven by `setup.py` (`pip install .`), but it can also
# be configured directly:
#
#   cmake -S pass/ArithmeticIntensity -B build/ai -G Ninja \
#       -DLLVM_INSTALL_DIR=$(realpath llvm-*) \
#       -DTRITON_WHEEL_DIR=$(python -c "import triton,pathlib;print(pathlib.Path(triton.__file__).parent)")
#   cmake --build build/ai

cmake_minimum_required(VERSION 3.20)
project(triton-arithmetic-intensity-ext LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED TRUE)

# The C++ class implementing the pass; this belongs with the code (not the
# manifest). It is threaded into the source via the `TRITON_EXT_CLASS` define.
set(TRITON_EXT_CLASS ArithmeticIntensityPass)

# This extension lives at `<repo>/pass/ArithmeticIntensity/`.
get_filename_component(TRITON_EXT_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.."
                       ABSOLUTE)
set(TRITON_EXT_SUPPORT_DIR "${TRITON_EXT_REPO_ROOT}/support")

find_package(Python3 COMPONENTS Interpreter REQUIRED)

# -----------------------------------------------------------------------------
# Read the extension manifest (`triton-ext.toml`) to obtain the extension name
# and version. The name determines the library filename and the pass name
# registered with Triton (e.g. `passes.plugin.add_arithmetic_intensity`).
# -----------------------------------------------------------------------------
set(_manifest "${CMAKE_CURRENT_SOURCE_DIR}/triton-ext.toml")
set(_manifest_cmake "${CMAKE_CURRENT_BINARY_DIR}/triton-ext-manifest.cmake")
execute_process(
    COMMAND ${Python3_EXECUTABLE}
            "${TRITON_EXT_REPO_ROOT}/ci/print-extension-as-cmake.py" "${_manifest}"
    OUTPUT_FILE "${_manifest_cmake}"
    RESULT_VARIABLE _manifest_rc)
if(NOT _manifest_rc EQUAL 0)
    message(FATAL_ERROR "Failed to parse ${_manifest}")
endif()
include("${_manifest_cmake}")
if(NOT TRITON_EXT_NAME)
    message(FATAL_ERROR "triton-ext.toml missing 'name' in ${_manifest}")
endif()
message(STATUS "Building triton-ext extension: ${TRITON_EXT_NAME} "
               "(v${TRITON_EXT_VERSION}, class ${TRITON_EXT_CLASS})")

# -----------------------------------------------------------------------------
# Locate Triton from an installed wheel: headers under `<triton>/include` and
# the shared library under `<triton>/_C`. `find_library` handles the
# platform-specific library naming (`.so`/`.dylib`/`.dll`).
# -----------------------------------------------------------------------------
if(NOT TRITON_WHEEL_DIR AND DEFINED ENV{TRITON_WHEEL_DIR})
    set(TRITON_WHEEL_DIR "$ENV{TRITON_WHEEL_DIR}")
endif()
if(NOT TRITON_WHEEL_DIR)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
                "import triton, pathlib; print(pathlib.Path(triton.__file__).parent)"
        OUTPUT_VARIABLE TRITON_WHEEL_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE _triton_rc)
    if(NOT _triton_rc EQUAL 0)
        message(FATAL_ERROR
                "Could not import Triton. Install a Triton wheel built with "
                "TRITON_EXT_ENABLED=1, or pass -DTRITON_WHEEL_DIR=<site-packages>/triton")
    endif()
endif()
get_filename_component(TRITON_WHEEL_DIR "${TRITON_WHEEL_DIR}" ABSOLUTE)
set(TRITON_WHEEL_INCLUDE_DIR "${TRITON_WHEEL_DIR}/include")
find_library(TRITON_LIB NAMES triton
             PATHS "${TRITON_WHEEL_DIR}/_C" NO_DEFAULT_PATH REQUIRED)
message(STATUS "Found Triton wheel at: ${TRITON_WHEEL_DIR}")
message(STATUS "Found Triton library at: ${TRITON_LIB}")
if(NOT EXISTS "${TRITON_WHEEL_INCLUDE_DIR}/triton")
    message(FATAL_ERROR
            "Triton wheel is missing C++ headers at ${TRITON_WHEEL_INCLUDE_DIR}; "
            "it must be built with TRITON_EXT_ENABLED=1.")
endif()

# -----------------------------------------------------------------------------
# Locate LLVM/MLIR for headers, TableGen, and CMake modules (NOT for linking:
# the required symbols are re-exported by libtriton). Point at an LLVM install
# with `LLVM_INSTALL_DIR`.
# -----------------------------------------------------------------------------
if(NOT LLVM_INSTALL_DIR AND DEFINED ENV{LLVM_INSTALL_DIR})
    set(LLVM_INSTALL_DIR "$ENV{LLVM_INSTALL_DIR}")
endif()
if(NOT LLVM_INSTALL_DIR)
    message(FATAL_ERROR "Set LLVM_INSTALL_DIR to an LLVM/MLIR install "
                        "(headers + mlir-tblgen + CMake modules).")
endif()
get_filename_component(LLVM_INSTALL_DIR "${LLVM_INSTALL_DIR}" ABSOLUTE)
find_package(MLIR REQUIRED CONFIG PATHS "${LLVM_INSTALL_DIR}/lib/cmake/mlir")
message(STATUS "Found MLIR at: ${MLIR_DIR}")

list(APPEND CMAKE_MODULE_PATH "${MLIR_CMAKE_DIR}")
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(TableGen)
include(AddLLVM)
include(AddMLIR)

# Include search paths. These must be set before `mlir_tablegen` so that
# TableGen can resolve `include "mlir/..."` from the MLIR include tree.
include_directories(SYSTEM ${MLIR_INCLUDE_DIRS} ${LLVM_INCLUDE_DIRS}
                           ${TRITON_WHEEL_INCLUDE_DIR})
include_directories(${TRITON_EXT_SUPPORT_DIR} ${CMAKE_CURRENT_BINARY_DIR})
add_definitions(${LLVM_DEFINITIONS})

# -----------------------------------------------------------------------------
# TableGen the pass declarations (uses mlir-tblgen from the LLVM install).
# -----------------------------------------------------------------------------
set(PASS_TABLEGEN_OUTPUT "TritonExt${TRITON_EXT_CLASS}IncGen")
set(LLVM_TARGET_DEFINITIONS Passes.td)
mlir_tablegen(Passes.h.inc -gen-pass-decls -name Extension)
add_public_tablegen_target(${PASS_TABLEGEN_OUTPUT})

# -----------------------------------------------------------------------------
# Build the self-contained plugin library.
# -----------------------------------------------------------------------------

add_library(${TRITON_EXT_NAME} SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/ArithmeticIntensity.cpp
    ${TRITON_EXT_SUPPORT_DIR}/Export.cpp)
add_dependencies(${TRITON_EXT_NAME} ${PASS_TABLEGEN_OUTPUT})

# Match LLVM's RTTI/exception settings to keep the ABI compatible.
if(NOT LLVM_ENABLE_RTTI)
    target_compile_options(${TRITON_EXT_NAME} PRIVATE
        $<$<COMPILE_LANGUAGE:CXX>:-fno-rtti>)
endif()

target_compile_definitions(${TRITON_EXT_NAME} PRIVATE
    TRITON_EXT_NAME=${TRITON_EXT_NAME}
    TRITON_EXT_CLASS=${TRITON_EXT_CLASS}
    TRITON_EXT_VERSION="${TRITON_EXT_VERSION}"
    # The plugin is loaded into a libtriton whose LLVM may have been built with
    # a different LLVM_ENABLE_ABI_BREAKING_CHECKS setting. Disable the link-time
    # enforcement symbol (llvm::{Enable,Disable}ABIBreakingChecks) so the plugin
    # resolves cleanly against the host's libtriton.
    LLVM_DISABLE_ABI_BREAKING_CHECKS_ENFORCING=1)

# Link ONLY against libtriton, which provides the MLIR/LLVM symbols. Use
# --no-as-needed so the DT_NEEDED entry is retained even though the extension
# resolves the symbols at load time from the already-loaded libtriton.
target_link_libraries(${TRITON_EXT_NAME} PRIVATE
    "$<$<PLATFORM_ID:Linux>:-Wl,--no-as-needed>"
    ${TRITON_LIB}
    "$<$<PLATFORM_ID:Linux>:-Wl,--as-needed>"
    "$<$<PLATFORM_ID:Darwin>:-undefined dynamic_lookup>")

# Emit a plain, unversioned `lib<name>.so` so the Python package can locate it.
set_target_properties(${TRITON_EXT_NAME} PROPERTIES PREFIX "lib")
if(DEFINED TRITON_EXT_OUTPUT_DIR)
    set_target_properties(${TRITON_EXT_NAME} PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${TRITON_EXT_OUTPUT_DIR}")
endif()
