"""Build the ArithmeticIntensity plugin as a Python package.

The compiled plugin (`lib<name>.so`) is produced by CMake (see the sibling
``CMakeLists.txt``) and bundled *inside* the ``triton_arithmetic_intensity``
package so that the package is self-contained: importing it locates and loads
the library via Triton's plugin API, with no ``TRITON_PLUGIN_PATHS`` or
``LD_LIBRARY_PATH`` indirection.

Requirements at build time:
  - a Triton wheel built with ``TRITON_EXT_ENABLED=1`` installed in the active
    environment (provides ``triton/_C/libtriton.so`` and ``triton/include``);
  - an LLVM/MLIR install for headers + ``mlir-tblgen`` + CMake modules, pointed
    to by the ``LLVM_INSTALL_DIR`` environment variable.

Build separately with, e.g.::

    LLVM_INSTALL_DIR=$(realpath ../../llvm-*) \\
        pip install -e . --no-build-isolation -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

HERE = Path(__file__).resolve().parent
PACKAGE = "triton_arithmetic_intensity"

# The extension name is the single source of truth in the manifest; it drives
# both the built library filename (`lib<name>.so`) and the pass name Triton
# registers (`passes.plugin.add_<name>`).
with open(HERE / "triton-ext.toml", "rb") as _f:
    EXT_NAME = tomllib.load(_f)["name"]


def _library_filename() -> str:
    """Platform-specific filename CMake emits for the plugin library."""
    if sys.platform == "darwin":
        return f"lib{EXT_NAME}.dylib"
    if sys.platform == "win32":
        return f"{EXT_NAME}.dll"
    return f"lib{EXT_NAME}.so"


class CMakeExtension(Extension):
    """An ``Extension`` whose sources are built by CMake, not by the compiler."""

    def __init__(self, name: str, sourcedir: str = "") -> None:
        super().__init__(name, sources=[])
        self.sourcedir = str(Path(sourcedir).resolve())


class CMakeBuild(build_ext):
    """Drive the extension's CMake project and drop the library in the package."""

    def get_ext_filename(self, fullname: str) -> str:
        # We produce a plain shared library, not a CPython extension module, so
        # override the default `<name>.<abi>.so` naming. Keep the result
        # package-qualified (e.g. `triton_arithmetic_intensity/lib<name>.so`) so
        # both the wheel and editable-install code paths agree on the location.
        package_parts = fullname.split(".")[:-1]
        return os.path.join(*package_parts, _library_filename())

    def build_extension(self, ext: CMakeExtension) -> None:
        # The library must land in the package directory so it is packaged as
        # data; `get_ext_fullpath` -> `.../triton_arithmetic_intensity/lib<name>.so`.
        package_dir = Path(self.get_ext_fullpath(ext.name)).resolve().parent
        package_dir.mkdir(parents=True, exist_ok=True)

        build_temp = Path(self.build_temp).resolve()
        build_temp.mkdir(parents=True, exist_ok=True)

        cmake_args = [
            f"-DTRITON_EXT_OUTPUT_DIR={package_dir}",
            f"-DCMAKE_BUILD_TYPE={os.environ.get('CMAKE_BUILD_TYPE', 'Release')}",
        ]
        llvm_install_dir = os.environ.get("LLVM_INSTALL_DIR")
        if llvm_install_dir:
            cmake_args.append(
                f"-DLLVM_INSTALL_DIR={Path(llvm_install_dir).resolve()}")
        # Locate the installed Triton wheel using the *current* interpreter so
        # the build matches the environment the package is installed into.
        triton_dir = _find_triton_dir()
        if triton_dir:
            cmake_args.append(f"-DTRITON_WHEEL_DIR={triton_dir}")
        if _has_ninja():
            cmake_args.append("-GNinja")

        subprocess.run(["cmake", ext.sourcedir, *cmake_args],
                       cwd=build_temp,
                       check=True)
        subprocess.run([
            "cmake", "--build", ".", "--config",
            os.environ.get("CMAKE_BUILD_TYPE", "Release")
        ],
                       cwd=build_temp,
                       check=True)


def _find_triton_dir() -> str | None:
    try:
        import triton  # noqa: PLC0415
    except ImportError:
        return None
    return str(Path(triton.__file__).resolve().parent)


def _has_ninja() -> bool:
    try:
        import ninja  # noqa: F401, PLC0415

        return True
    except ImportError:
        from shutil import which

        return which("ninja") is not None


setup(
    ext_modules=[CMakeExtension(f"{PACKAGE}._plugin", sourcedir=".")],
    cmdclass={"build_ext": CMakeBuild},
)
