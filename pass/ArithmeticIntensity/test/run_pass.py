#!/usr/bin/env python3
"""
Run the arithmetic-intensity pass on an MLIR file and print the result.

The plugin ships as the installed ``triton_arithmetic_intensity`` package and
loads itself on import, so no ``TRITON_PLUGIN_PATHS``/``LD_LIBRARY_PATH``/
``PYTHONPATH`` wiring is required:

    python run_pass.py <mlir_file>
"""

import sys
from triton._C.libtriton import ir, passes
import triton_arithmetic_intensity  # noqa: F401

if len(sys.argv) != 2:
    print(f"usage: {sys.argv[0]} <mlir_file>", file=sys.stderr)
    sys.exit(2)

mlir_file = sys.argv[1]

ctx = ir.context()
ir.load_dialects(ctx)
mod = ir.parse_mlir_module(mlir_file, ctx)
pm = ir.pass_manager(ctx)
passes.plugin.add_arithmetic_intensity(pm)
pipeline_tag = "test_arithmetic_intensity.py"
pm.run(mod, pipeline_tag)
print(mod.str_nodebug(), end="")
