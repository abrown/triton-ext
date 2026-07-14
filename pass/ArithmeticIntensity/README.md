# Arithmetic Intensity Pass

This pass analyzes the arithmetic intensity of a given Triton function.

## Extensions as Python packages

This pass demonstrates how to distribute an extension as a self-contained Python
package that links against a **Triton wheel** instead of the standalone
LLVM/Triton shared libraries. The compiled plugin (`libarithmetic_intensity.so`)
is bundled *inside* the `triton_arithmetic_intensity` package and loaded on
import via Triton's plugin API, so there is no `TRITON_PLUGIN_PATHS`,
`LD_LIBRARY_PATH`, or `PYTHONPATH` wiring.

### Requirements

- A **Triton wheel built with `TRITON_EXT_ENABLED=1`** (>= the version that adds
  the `passes.plugin.extend_with` binding, upstream [#10775]). Such a wheel
  ships `triton/_C/libtriton.so` (which re-exports the MLIR/LLVM symbols the
  plugin needs) and the `triton/include` C++ headers. Install it into a virtual
  environment using the **same Python** the wheel targets (e.g. cp314):

  ```console
  python -m venv --prompt triton-ext .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  pip install /path/to/triton-3.8.0+git<hash>-cp314-cp314-linux_x86_64.whl
  ```

- An **LLVM/MLIR build for headers, `mlir-tblgen`, and CMake modules**, pointed
  to by `LLVM_INSTALL_DIR`. It is *not* used for linking (libtriton provides the
  symbols), but it **must match the LLVM the wheel was built against** --
  including the `LLVM_ENABLE_ABI_BREAKING_CHECKS` setting, or the plugin will
  crash at load. The reliable source is the LLVM that Triton itself downloaded
  and cached while building the wheel:

  ```console
  export LLVM_INSTALL_DIR=~/.triton/llvm/llvm-<hash>-<os>-<arch>
  ```

### Build and test

Build the extension package separately with pip (each extension builds on its
own); `--no-build-isolation` lets the build see the installed Triton wheel:

```console
LLVM_INSTALL_DIR=~/.triton/llvm/llvm-<hash>-<os>-<arch> \
    pip install -e pass/ArithmeticIntensity --no-build-isolation -v
```

Then run the tests with a plain environment -- no plugin/library path variables
are needed:

```console
python -m pytest -v pass/ArithmeticIntensity/test
```

To produce a redistributable wheel instead:

```console
LLVM_INSTALL_DIR=~/.triton/llvm/llvm-<hash>-<os>-<arch> \
    pip wheel pass/ArithmeticIntensity --no-build-isolation --no-deps -w dist/
```

[#10775]: https://github.com/triton-lang/triton/pull/10775
