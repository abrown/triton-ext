import triton._C.libtriton as libtriton
import os

# TODO: checking TRITON_PLUGIN_PATHS is old; eventually we would locate the
# library within this package instead.
LIB = os.getenv("TRITON_PLUGIN_PATHS")
print(f'Extending with: {LIB}')
libtriton.passes.plugin.extend_with(LIB)  # adds passes
# libtriton.passes.ir.extend_dialects_with(LIB)  # adds dialects
# libtriton.passes.ir.builder.extend_with(LIB)  # adds operations
