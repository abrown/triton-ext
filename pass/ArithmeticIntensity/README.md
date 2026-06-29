# Arithmetic Intensity Pass

This pass analyzes the arithmetic intensity of a given Triton function.

## WIP: "extensions as packages"

This pass also demonstrates how to distribute an extension as a Python package.
This is a work in progress, relying on unmerged upstream changes--use at your
own risk:

- upstream Triton must contain [#10775]

- upstream Triton must be built as in CI:

  ```console
  export LLVM_INSTALL_DIR=$(realpath ../triton-ext/llvm-*)
  LLVM_INCLUDE_DIRS=$LLVM_INSTALL_DIR/include \
    LLVM_LIBRARY_DIR=$LLVM_INSTALL_DIR/lib \
    LLVM_SYSPATH=$LLVM_INSTALL_DIR \
    TRITON_BUILD_WITH_CLANG_LLD=1 \
    TRITON_EXT_ENABLED=1 \
    MAX_JOBS=8 \
        make dev-install
  make install
  ```

- the upstream Triton installation must also contain the Triton Python package
  (for testing):

  ```cmake
  install(DIRECTORY ${PROJECT_SOURCE_DIR}/python/
    COMPONENT python
    DESTINATION python
    FILES_MATCHING PATTERN "*.so" EXCLUDE
                   PATTERN "*.pyc" EXCLUDE
                   PATTERN "__pycache__" EXCLUDE
  )
  install(CODE "execute_process(COMMAND \"${CMAKE_COMMAND}\" -E create_symlink
          \"../../../lib64/libtriton.so\"
          \"\${CMAKE_INSTALL_PREFIX}/python/triton/_C/libtriton.so\"
          COMMAND_ERROR_IS_FATAL ANY)"
      COMPONENT python
  )
  ```

With the right Triton artifacts built, we install the Python package for this
extension. We make sure to use the same version of Python as the one used to
build Triton (e.g., v3.14.2 here):

```console
python -m venv --prompt triton-ext .venv
source .venv/bin/activate
pip install -r requirements.txt
cd pass/ArithmeticIntensity/
pip install -e . --no-build-isolation -v
```

Now we should be able run the arithmetic intensity tests:

```console
$ BUILD_DIR="build" \
  LLVM_INSTALL_DIR="llvm-62b7cf96-linux-x64" \
  TRITON_INSTALL_DIR="../triton/build/install" \
    python -m pytest -sv pass/ArithmeticIntensity/test
```

[#10775]: https://github.com/triton-lang/triton/pull/10775
