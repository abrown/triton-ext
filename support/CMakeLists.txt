project(TritonExtensionSupport)

add_mlir_library(${PROJECT_NAME}
    Export.cpp
    PARTIAL_SOURCES_INTENDED
    SHARED
)

set_target_properties(${PROJECT_NAME} PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY
    "${TRITON_EXT_LIBRARY_DIR}")
