# ---------------------------------------------------------------------------
# uTLX — standalone Triton plugin for the TLX dialect.
#
# This extension builds libutlx.so, loadable via TRITON_PLUGIN_PATHS. It
# provides:
#   - The TLX dialect (types, attrs, ops)
#   - TLX transform passes
#   - TLX custom ops for the TritonOpBuilder
#   - TLX conversion patterns (ConvertTritonToTritonGPU plugin pass)
#
# It supports two build modes:
#
#   1. WHEEL MODE (primary) — link ONLY against the Triton shared library shipped
#      inside an installed Triton wheel (`triton/_C/libtriton.so`), which
#      re-exports the MLIR/LLVM symbols it needs (the wheel must be built with
#      `TRITON_EXT_ENABLED=1`). LLVM/MLIR is used only for headers, `mlir-tblgen`,
#      and CMake modules — never for linking. Enable by setting `TRITON_WHEEL_DIR`
#      (or letting it be discovered from the active Python environment) and
#      `LLVM_INSTALL_DIR`. This mirrors `pass/ArithmeticIntensity`.
#
#      cmake -S extensions/utlx -B extensions/utlx/build -G Ninja \
#          -DLLVM_INSTALL_DIR=$(realpath llvm-*) \
#          -DTRITON_WHEEL_DIR=$(python -c "import triton,pathlib;print(pathlib.Path(triton.__file__).parent)")
#      cmake --build extensions/utlx/build   # -> build/lib/libutlx.so
#
#   2. SOURCE/BUILD MODE (legacy) — link against libtriton.so from a Triton
#      source + build tree and an LLVM build tree, with explicit MLIR libraries.
#      Enable by setting TRITON_SOURCE_DIR / TRITON_BUILD_DIR / LLVM_BUILD_DIR.
#
# This file works both standalone (`cmake -S extensions/utlx`) and, for backward
# compatibility, when pulled in by the repository-root umbrella build via
# add_subdirectory (in which case the parent supplies Triton/LLVM locations).
# ---------------------------------------------------------------------------

# Detect whether we are configured as our own top-level project or included by
# the umbrella build via add_subdirectory.
set(UTLX_STANDALONE FALSE)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    set(UTLX_STANDALONE TRUE)
endif()

if(UTLX_STANDALONE)
    cmake_minimum_required(VERSION 3.20)
    project(utlx LANGUAGES C CXX)
    set(CMAKE_CXX_STANDARD 17)
    set(CMAKE_CXX_STANDARD_REQUIRED TRUE)
endif()

# ---------------------------------------------------------------------------
# Resolve the extension name/version from the manifest (triton-ext.toml).
# In the umbrella build the triton_extension() macro already does this and sets
# up the project(); standalone we read it directly like pass/ArithmeticIntensity.
# The name (`utlx`) drives the output library filename (`libutlx.so`).
# ---------------------------------------------------------------------------
get_filename_component(TRITON_EXT_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.."
                       ABSOLUTE)

if(UTLX_STANDALONE)
    find_package(Python3 COMPONENTS Interpreter REQUIRED)
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
    add_compile_definitions(TRITON_EXT_VERSION="${TRITON_EXT_VERSION}")
else()
    # Umbrella build: use the shared helper (sets project() + TRITON_EXT_NAME).
    triton_extension(uTLXPlugin)
endif()

set(UTLX_TARGET ${TRITON_EXT_NAME})
message(STATUS "Building triton-ext extension: ${TRITON_EXT_NAME} "
               "(v${TRITON_EXT_VERSION})")

# ---------------------------------------------------------------------------
# Accept source/build paths from environment if not set via -D
# ---------------------------------------------------------------------------
if(NOT TRITON_WHEEL_DIR AND DEFINED ENV{TRITON_WHEEL_DIR})
    set(TRITON_WHEEL_DIR $ENV{TRITON_WHEEL_DIR})
endif()
if(NOT TRITON_SOURCE_DIR AND DEFINED ENV{TRITON_SOURCE_DIR})
    set(TRITON_SOURCE_DIR $ENV{TRITON_SOURCE_DIR})
endif()
if(NOT TRITON_BUILD_DIR AND DEFINED ENV{TRITON_BUILD_DIR})
    set(TRITON_BUILD_DIR $ENV{TRITON_BUILD_DIR})
endif()
if(NOT LLVM_INSTALL_DIR AND DEFINED ENV{LLVM_INSTALL_DIR})
    set(LLVM_INSTALL_DIR $ENV{LLVM_INSTALL_DIR})
endif()
if(NOT LLVM_BUILD_DIR AND DEFINED ENV{LLVM_BUILD_DIR})
    set(LLVM_BUILD_DIR $ENV{LLVM_BUILD_DIR})
endif()

# ---------------------------------------------------------------------------
# Determine the build mode. Wheel mode is selected when TRITON_WHEEL_DIR is set
# (explicitly, via env, or discoverable from the active Python interpreter) and
# no explicit source tree is requested.
# ---------------------------------------------------------------------------
if(UTLX_STANDALONE AND NOT TRITON_WHEEL_DIR AND NOT TRITON_SOURCE_DIR
   AND NOT TRITON_INSTALL_DIR)
    # Try to discover a Triton wheel from the active environment.
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
                "import triton, pathlib; print(pathlib.Path(triton.__file__).parent)"
        OUTPUT_VARIABLE TRITON_WHEEL_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE _triton_rc)
    if(NOT _triton_rc EQUAL 0)
        set(TRITON_WHEEL_DIR "")
    endif()
endif()

set(UTLX_WHEEL_MODE FALSE)
if(TRITON_WHEEL_DIR)
    set(UTLX_WHEEL_MODE TRUE)
endif()

# ---------------------------------------------------------------------------
# Locate Triton.
# ---------------------------------------------------------------------------
if(UTLX_WHEEL_MODE)
    get_filename_component(TRITON_WHEEL_DIR "${TRITON_WHEEL_DIR}" ABSOLUTE)
    set(TRITON_WHEEL_INCLUDE_DIR "${TRITON_WHEEL_DIR}/include")
    find_library(UTLX_TRITON_LIB NAMES triton
                 PATHS "${TRITON_WHEEL_DIR}/_C" NO_DEFAULT_PATH REQUIRED)
    if(NOT EXISTS "${TRITON_WHEEL_INCLUDE_DIR}/triton")
        message(FATAL_ERROR
                "Triton wheel is missing C++ headers at ${TRITON_WHEEL_INCLUDE_DIR}; "
                "it must be built with TRITON_EXT_ENABLED=1.")
    endif()
    message(STATUS "uTLX: wheel mode — Triton at ${TRITON_WHEEL_DIR}")
    message(STATUS "uTLX: Triton library at ${UTLX_TRITON_LIB}")
elseif(TRITON_SOURCE_DIR)
    if(NOT UTLX_TRITON_LIB)
        find_library(UTLX_TRITON_LIB NAMES triton
            PATHS "${TRITON_SOURCE_DIR}/python/triton/_C"
            NO_DEFAULT_PATH)
    endif()
    message(STATUS "uTLX: source mode — Triton at ${TRITON_SOURCE_DIR}")
elseif(TRITON_INSTALL_DIR)
    if(NOT UTLX_TRITON_LIB AND NOT TRITON_LIB)
        find_library(UTLX_TRITON_LIB NAMES triton
            PATHS "${TRITON_INSTALL_DIR}/lib" "${TRITON_INSTALL_DIR}/lib64")
    endif()
    message(STATUS "uTLX: install mode — Triton at ${TRITON_INSTALL_DIR}")
else()
    message(FATAL_ERROR
            "uTLX: could not locate Triton. Set TRITON_WHEEL_DIR (wheel mode), "
            "TRITON_SOURCE_DIR (+TRITON_BUILD_DIR), or TRITON_INSTALL_DIR.")
endif()

# ---------------------------------------------------------------------------
# Locate LLVM/MLIR (headers, mlir-tblgen, CMake modules). In wheel mode this is
# NOT used for linking — libtriton re-exports the required symbols.
# ---------------------------------------------------------------------------
if(UTLX_WHEEL_MODE)
    if(NOT LLVM_INSTALL_DIR)
        message(FATAL_ERROR "Set LLVM_INSTALL_DIR to an LLVM/MLIR install "
                            "(headers + mlir-tblgen + CMake modules).")
    endif()
    get_filename_component(LLVM_INSTALL_DIR "${LLVM_INSTALL_DIR}" ABSOLUTE)
    find_package(MLIR REQUIRED CONFIG PATHS "${LLVM_INSTALL_DIR}/lib/cmake/mlir")
    message(STATUS "uTLX: MLIR at ${MLIR_DIR}")
else()
    if(LLVM_BUILD_DIR)
        find_package(MLIR QUIET CONFIG PATHS "${LLVM_BUILD_DIR}/lib/cmake/mlir")
        find_package(LLVM QUIET CONFIG PATHS "${LLVM_BUILD_DIR}/lib/cmake/llvm")
    elseif(LLVM_INSTALL_DIR)
        find_package(MLIR QUIET CONFIG PATHS "${LLVM_INSTALL_DIR}/lib/cmake/mlir")
        find_package(LLVM QUIET CONFIG PATHS "${LLVM_INSTALL_DIR}/lib/cmake/llvm")
    endif()
endif()

# ---------------------------------------------------------------------------
# TableGen for the TLX dialect
# ---------------------------------------------------------------------------
set(UTLX_DIALECT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/tlx/dialect")
set(UTLX_DIALECT_INCLUDE_DIR "${UTLX_DIALECT_DIR}/include")
set(UTLX_TABLEGEN_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/tlx/dialect/include")

# Ensure the output directories exist
file(MAKE_DIRECTORY "${UTLX_TABLEGEN_OUTPUT_DIR}/IR")
file(MAKE_DIRECTORY "${UTLX_TABLEGEN_OUTPUT_DIR}/Transforms")

# Find mlir-tblgen
if(NOT MLIR_TABLEGEN_EXE)
    if(LLVM_BUILD_DIR)
        find_program(MLIR_TABLEGEN_EXE mlir-tblgen
            PATHS "${LLVM_BUILD_DIR}/bin"
            NO_DEFAULT_PATH)
    endif()
    if(NOT MLIR_TABLEGEN_EXE AND LLVM_INSTALL_DIR)
        find_program(MLIR_TABLEGEN_EXE mlir-tblgen
            PATHS "${LLVM_INSTALL_DIR}/bin"
            NO_DEFAULT_PATH)
    endif()
    if(NOT MLIR_TABLEGEN_EXE)
        find_program(MLIR_TABLEGEN_EXE mlir-tblgen)
    endif()
endif()

if(NOT MLIR_TABLEGEN_EXE)
    message(FATAL_ERROR "Could not find mlir-tblgen. Set LLVM_BUILD_DIR or LLVM_INSTALL_DIR.")
endif()

# Collect tablegen include paths
set(UTLX_TBLGEN_INCLUDES
    "-I${UTLX_DIALECT_INCLUDE_DIR}/IR"
    "-I${UTLX_DIALECT_INCLUDE_DIR}"
)
# MLIR/LLVM tablegen includes
if(LLVM_BUILD_DIR)
    list(APPEND UTLX_TBLGEN_INCLUDES
        "-I${LLVM_BUILD_DIR}/include"
    )
endif()
if(LLVM_INSTALL_DIR)
    list(APPEND UTLX_TBLGEN_INCLUDES
        "-I${LLVM_INSTALL_DIR}/include"
    )
endif()
foreach(dir ${LLVM_INCLUDE_DIRS})
    list(APPEND UTLX_TBLGEN_INCLUDES "-I${dir}")
endforeach()
foreach(dir ${MLIR_INCLUDE_DIRS})
    list(APPEND UTLX_TBLGEN_INCLUDES "-I${dir}")
endforeach()
# Triton tablegen includes
if(UTLX_WHEEL_MODE)
    list(APPEND UTLX_TBLGEN_INCLUDES "-I${TRITON_WHEEL_INCLUDE_DIR}")
elseif(TRITON_SOURCE_DIR)
    list(APPEND UTLX_TBLGEN_INCLUDES
        "-I${TRITON_SOURCE_DIR}/include"
        "-I${TRITON_SOURCE_DIR}"
    )
    if(TRITON_BUILD_DIR)
        list(APPEND UTLX_TBLGEN_INCLUDES
            "-I${TRITON_BUILD_DIR}/include"
        )
    endif()
elseif(TRITON_INSTALL_DIR)
    list(APPEND UTLX_TBLGEN_INCLUDES "-I${TRITON_INSTALL_DIR}/include")
endif()

# Helper function for running mlir-tblgen
function(utlx_tablegen input output generator)
    set(extra_args ${ARGN})
    get_filename_component(input_abs "${input}" ABSOLUTE)
    add_custom_command(
        OUTPUT "${output}"
        COMMAND "${MLIR_TABLEGEN_EXE}" ${generator} ${extra_args}
                ${UTLX_TBLGEN_INCLUDES} "${input_abs}"
                -o "${output}"
        DEPENDS "${input_abs}"
        COMMENT "Running mlir-tblgen ${generator} on ${input}"
        VERBATIM
    )
endfunction()

# --- IR TableGen ---
set(IR_TD_DIR "${UTLX_DIALECT_INCLUDE_DIR}/IR")
set(IR_OUT_DIR "${UTLX_TABLEGEN_OUTPUT_DIR}/IR")

# Dialect
utlx_tablegen("${IR_TD_DIR}/TLXDialect.td" "${IR_OUT_DIR}/Dialect.h.inc"
    "-gen-dialect-decls" "-dialect=tlx")
utlx_tablegen("${IR_TD_DIR}/TLXDialect.td" "${IR_OUT_DIR}/Dialect.cpp.inc"
    "-gen-dialect-defs" "-dialect=tlx")

# Types
utlx_tablegen("${IR_TD_DIR}/TLXTypes.td" "${IR_OUT_DIR}/TLXTypes.h.inc"
    "-gen-typedef-decls")
utlx_tablegen("${IR_TD_DIR}/TLXTypes.td" "${IR_OUT_DIR}/TLXTypes.cpp.inc"
    "-gen-typedef-defs")
utlx_tablegen("${IR_TD_DIR}/TLXTypes.td" "${IR_OUT_DIR}/TLXTypesEnums.h.inc"
    "-gen-enum-decls")
utlx_tablegen("${IR_TD_DIR}/TLXTypes.td" "${IR_OUT_DIR}/TLXTypesEnums.cpp.inc"
    "-gen-enum-defs")

# Ops
utlx_tablegen("${IR_TD_DIR}/TLXOps.td" "${IR_OUT_DIR}/Ops.h.inc"
    "-gen-op-decls")
utlx_tablegen("${IR_TD_DIR}/TLXOps.td" "${IR_OUT_DIR}/Ops.cpp.inc"
    "-gen-op-defs")

# AttrDefs
utlx_tablegen("${IR_TD_DIR}/TLXAttrDefs.td" "${IR_OUT_DIR}/TLXAttrDefs.h.inc"
    "-gen-attrdef-decls")
utlx_tablegen("${IR_TD_DIR}/TLXAttrDefs.td" "${IR_OUT_DIR}/TLXAttrDefs.cpp.inc"
    "-gen-attrdef-defs")

# --- Transforms TableGen ---
set(TRANSFORMS_TD_DIR "${UTLX_DIALECT_INCLUDE_DIR}/Transforms")
set(TRANSFORMS_OUT_DIR "${UTLX_TABLEGEN_OUTPUT_DIR}/Transforms")

utlx_tablegen("${TRANSFORMS_TD_DIR}/Passes.td" "${TRANSFORMS_OUT_DIR}/Passes.h.inc"
    "-gen-pass-decls")

# Collect all tablegen outputs into a custom target
set(UTLX_TABLEGEN_OUTPUTS
    "${IR_OUT_DIR}/Dialect.h.inc"
    "${IR_OUT_DIR}/Dialect.cpp.inc"
    "${IR_OUT_DIR}/TLXTypes.h.inc"
    "${IR_OUT_DIR}/TLXTypes.cpp.inc"
    "${IR_OUT_DIR}/TLXTypesEnums.h.inc"
    "${IR_OUT_DIR}/TLXTypesEnums.cpp.inc"
    "${IR_OUT_DIR}/Ops.h.inc"
    "${IR_OUT_DIR}/Ops.cpp.inc"
    "${IR_OUT_DIR}/TLXAttrDefs.h.inc"
    "${IR_OUT_DIR}/TLXAttrDefs.cpp.inc"
    "${TRANSFORMS_OUT_DIR}/Passes.h.inc"
)
add_custom_target(uTLXTableGen DEPENDS ${UTLX_TABLEGEN_OUTPUTS})

# ---------------------------------------------------------------------------
# Plugin sources
# ---------------------------------------------------------------------------
set(UTLX_PLUGIN_SOURCES
    # Plugin entry point
    uTLXPlugin.cpp
    uTLXConversionPatterns.cpp
    # Dialect IR
    tlx/dialect/lib/IR/Dialect.cpp
    tlx/dialect/lib/IR/Ops.cpp
    tlx/dialect/lib/IR/Traits.cpp
    tlx/dialect/lib/IR/Types.cpp
    # Dialect Transforms
    tlx/dialect/lib/Transforms/Fixup.cpp
    tlx/dialect/lib/Transforms/PropagateLayout.cpp
    tlx/dialect/lib/Transforms/InsertRequireLayout.cpp
    tlx/dialect/lib/Transforms/RewriteLocalAlias.cpp
    tlx/dialect/lib/Transforms/ResolvePlaceholderLayouts.cpp
    tlx/dialect/lib/Transforms/PrintTTGIRToTLX.cpp
    tlx/dialect/lib/Transforms/StorageAliasSizeDefinition.cpp
    tlx/dialect/lib/Transforms/StorageAliasAllocation.cpp
    tlx/dialect/lib/Transforms/StorageAliasLowering.cpp
    tlx/dialect/lib/Transforms/BufferOffsetCalculation.cpp
    # Analysis
    tlx/dialect/lib/Analysis/LayoutPropagation.cpp
    # New/modified op wrappers (runtime op creation)
    ops/NewOps.cpp
    # Ported passes - NVIDIA
    passes/nvidia/PruneUnusedBarriers.cpp
    passes/nvidia/PingPong.cpp
    # Ported passes - AMD
    # NOTE: AMD barrier passes require patched triton (ReadBarrierPhaseOp,
    # ArriveBarrierOp with expectedCount). Uncomment when
    # triton-tlx-core-changes patch is applied:
    # passes/amd/LowerBarrierOps.cpp
    # passes/amd/BarrierOpConversion.cpp
)

add_library(${UTLX_TARGET} SHARED ${UTLX_PLUGIN_SOURCES})
add_dependencies(${UTLX_TARGET} uTLXTableGen)

# ---------------------------------------------------------------------------
# Include directories
# ---------------------------------------------------------------------------
set(UTLX_INCLUDE_DIRS
    # For #include "IR/Dialect.h" (relative from lib/IR/*.cpp)
    # Source headers: found via tlx/dialect/include/
    "${UTLX_DIALECT_INCLUDE_DIR}"
    # Generated headers: found via tablegen output
    "${UTLX_TABLEGEN_OUTPUT_DIR}"
    # For #include "tlx/dialect/include/IR/..." (source headers)
    "${CMAKE_CURRENT_SOURCE_DIR}"
    # For #include "tlx/dialect/include/IR/..." (generated headers)
    "${CMAKE_CURRENT_BINARY_DIR}"
)

if(UTLX_WHEEL_MODE)
    list(APPEND UTLX_INCLUDE_DIRS "${TRITON_WHEEL_INCLUDE_DIR}")
elseif(TRITON_SOURCE_DIR)
    list(APPEND UTLX_INCLUDE_DIRS
        "${TRITON_SOURCE_DIR}/include"
        "${TRITON_SOURCE_DIR}"
        "${TRITON_SOURCE_DIR}/third_party/amd/include"
        "${TRITON_SOURCE_DIR}/third_party"
        "${TRITON_SOURCE_DIR}/third_party/nvidia/include"
    )
    if(TRITON_BUILD_DIR)
        list(APPEND UTLX_INCLUDE_DIRS
            "${TRITON_BUILD_DIR}/include"
            "${TRITON_BUILD_DIR}/third_party"
        )
    endif()
elseif(TRITON_INSTALL_DIR)
    list(APPEND UTLX_INCLUDE_DIRS "${TRITON_INSTALL_DIR}/include")
endif()

# LLVM/MLIR include dirs
list(APPEND UTLX_INCLUDE_DIRS ${LLVM_INCLUDE_DIRS} ${MLIR_INCLUDE_DIRS})

target_include_directories(${UTLX_TARGET} SYSTEM PRIVATE ${UTLX_INCLUDE_DIRS})

# ---------------------------------------------------------------------------
# Optional AMDGPU support (requires third_party headers from triton source)
# ---------------------------------------------------------------------------
set(_AMDGPU_HEADER_FOUND FALSE)
foreach(_dir ${UTLX_INCLUDE_DIRS})
    if(EXISTS "${_dir}/Dialect/TritonAMDGPU/IR/Dialect.h")
        set(_AMDGPU_HEADER_FOUND TRUE)
        break()
    endif()
endforeach()
if(_AMDGPU_HEADER_FOUND)
    message(STATUS "AMDGPU dialect header found — enabling UTLX_HAS_AMDGPU")
    target_compile_definitions(${UTLX_TARGET} PRIVATE UTLX_HAS_AMDGPU)
else()
    message(STATUS "AMDGPU dialect header not found — AMD support disabled")
endif()

# ---------------------------------------------------------------------------
# Link libraries
# ---------------------------------------------------------------------------
if(NOT UTLX_TRITON_LIB AND TRITON_LIB)
    set(UTLX_TRITON_LIB ${TRITON_LIB})
endif()
if(NOT UTLX_TRITON_LIB)
    message(FATAL_ERROR "Could not find libtriton.so. Set TRITON_WHEEL_DIR, "
                        "TRITON_SOURCE_DIR, or TRITON_INSTALL_DIR.")
endif()

if(UTLX_WHEEL_MODE)
    # Link ONLY against libtriton, which re-exports the MLIR/LLVM symbols. Use
    # --no-as-needed so the DT_NEEDED entry is retained even though the plugin
    # resolves the symbols at load time from the already-loaded libtriton.
    target_link_libraries(${UTLX_TARGET} PRIVATE
        "$<$<PLATFORM_ID:Linux>:-Wl,--no-as-needed>"
        ${UTLX_TRITON_LIB}
        "$<$<PLATFORM_ID:Linux>:-Wl,--as-needed>"
        "$<$<PLATFORM_ID:Darwin>:-undefined dynamic_lookup>")

    # The plugin is loaded into a libtriton whose LLVM was built with
    # LLVM_ENABLE_ABI_BREAKING_CHECKS=1 (asserts build). That flag toggles ilist
    # sentinel tracking, which changes the mangled type of every ilist_iterator
    # (pervasive in MLIR). If the plugin is compiled with a different value it
    # references symbols (e.g. RewriterBase::inlineBlockBefore(... node_options<
    # Operation, false, ...>)) that libtriton does not export, producing a
    # runtime "undefined symbol" load failure.
    #
    # The LLVM install's abi-breaking.h hardcodes the value with an
    # unconditional `#define`, so a plain -DLLVM_ENABLE_ABI_BREAKING_CHECKS=1
    # would be clobbered (and merely warn about redefinition). Instead, generate
    # a patched copy of the header with the value forced to 1 and shadow it on
    # the include path (searched BEFORE the LLVM install) so the plugin's ABI
    # matches the host libtriton.
    set(_utlx_abi_src "${LLVM_INSTALL_DIR}/include/llvm/Config/abi-breaking.h")
    set(_utlx_abi_override_dir "${CMAKE_CURRENT_BINARY_DIR}/abi-override")
    if(EXISTS "${_utlx_abi_src}")
        file(READ "${_utlx_abi_src}" _utlx_abi_contents)
        string(REPLACE
            "#define LLVM_ENABLE_ABI_BREAKING_CHECKS 0"
            "#define LLVM_ENABLE_ABI_BREAKING_CHECKS 1"
            _utlx_abi_contents "${_utlx_abi_contents}")
        file(WRITE "${_utlx_abi_override_dir}/llvm/Config/abi-breaking.h"
             "${_utlx_abi_contents}")
        target_include_directories(${UTLX_TARGET} BEFORE SYSTEM PRIVATE
            "${_utlx_abi_override_dir}")
        message(STATUS "uTLX: forcing LLVM_ENABLE_ABI_BREAKING_CHECKS=1 to match "
                       "host libtriton (shadow header at ${_utlx_abi_override_dir})")
    else()
        message(WARNING "uTLX: could not find ${_utlx_abi_src}; cannot force "
                        "LLVM_ENABLE_ABI_BREAKING_CHECKS. Plugin may fail to load "
                        "with an undefined-symbol error.")
    endif()

    # Disable the link-time enforcement symbol so the plugin does not also
    # require the EnableABIBreakingChecks marker to be resolvable.
    target_compile_definitions(${UTLX_TARGET} PRIVATE
        LLVM_DISABLE_ABI_BREAKING_CHECKS_ENFORCING=1)
else()
    # Source/install mode: link libtriton plus the explicit MLIR libraries from
    # the LLVM build/install tree.
    target_link_libraries(${UTLX_TARGET} PRIVATE
        ${UTLX_TRITON_LIB}
        MLIRPass
        MLIRAnalysis
        MLIRTransforms
        MLIRIR
        MLIRSupport
        LLVMSupport
    )
endif()

# ---------------------------------------------------------------------------
# Build properties
# ---------------------------------------------------------------------------
# Emit a plain, unversioned `libutlx.so`.
set_target_properties(${UTLX_TARGET} PROPERTIES
    PREFIX "lib"
    CXX_STANDARD 17
)

# Output directory: honor TRITON_EXT_OUTPUT_DIR, else the umbrella library dir,
# else <build>/lib (so build_wheel.sh finds build/lib/libutlx.so).
if(DEFINED TRITON_EXT_OUTPUT_DIR)
    set_target_properties(${UTLX_TARGET} PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${TRITON_EXT_OUTPUT_DIR}")
elseif(DEFINED TRITON_EXT_LIBRARY_DIR)
    set_target_properties(${UTLX_TARGET} PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${TRITON_EXT_LIBRARY_DIR}")
else()
    set_target_properties(${UTLX_TARGET} PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
endif()

# Match LLVM's RTTI setting to keep the ABI compatible.
if(DEFINED LLVM_ENABLE_RTTI AND NOT LLVM_ENABLE_RTTI)
    target_compile_options(${UTLX_TARGET} PRIVATE
        $<$<COMPILE_LANGUAGE:CXX>:-fno-rtti>)
endif()

target_compile_options(${UTLX_TARGET} PRIVATE
    -fvisibility=hidden
    -fno-exceptions
    -fno-rtti
    -Wno-deprecated-declarations
)
