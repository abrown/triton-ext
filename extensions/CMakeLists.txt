# Include the support code for all extensions (see `#include "Export*.cpp"`).
include_directories(${TRITON_EXT_SUPPORT_DIR})

# Build all standalone extensions.
file(GLOB EXT_DIRS RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/*")
foreach(EXT_DIR ${EXT_DIRS})
    if(IS_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/${EXT_DIR}")
        # Extensions that ship as self-contained Python packages provide their
        # own standalone build (driven by pip against a Triton wheel). Skip them
        # here so the umbrella build does not also produce a differently-linked
        # copy. See extensions/utlx for an example.
        if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${EXT_DIR}/pyproject.toml")
            message(STATUS "Found triton-ext extension: skipping ${EXT_DIR} "
                           "(self-packaging; build with pip)")
            continue()
        endif()
        triton_ext_should_build_extension("${CMAKE_CURRENT_SOURCE_DIR}/${EXT_DIR}" _should_build)
        if(${_should_build})
            message(STATUS "Found triton-ext extension: building ${EXT_DIR}")
            set(EXT_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}/${EXT_DIR}")
            add_subdirectory(${EXT_DIR} ${EXT_BUILD_DIR})
        else()
            message(STATUS "Found triton-ext extension: skipping ${EXT_DIR} (not enabled)")
        endif()
    endif()
endforeach()
