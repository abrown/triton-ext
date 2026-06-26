# triton-foo-backend

A stub out-of-tree Triton backend that demonstrates how to register a custom
backend with Triton's entry-point discovery mechanism.

## Structure

```text
backend/foo/
├── pyproject.toml              # Package metadata and triton.backends entry point
├── README.md                   # This file
├── test_foo_backend.py         # Smoke test: import triton and list backends
└── triton_foo_backend/
    ├── __init__.py             # Empty package marker
    ├── compiler.py             # FooBackend, implementing BaseBackend
    └── driver.py               # FooDriver, implementing DriverBase
```

## How backend discovery works

Triton discovers out-of-tree backends by scanning the `triton.backends` entry
point group (see `triton/backends/__init__.py`). Each entry point has:

- **name** – the backend key (e.g., `foo`), used as the key in
  `triton.backends.backends`.
- **value** – the importable module prefix (e.g., `triton_foo_backend`).

Triton will then import `<value>.compiler` and `<value>.driver` and look for
concrete subclasses of `BaseBackend` and `DriverBase` respectively.

The entry point is declared in `pyproject.toml`:

```toml
[project.entry-points."triton.backends"]
foo = "triton_foo_backend"
```

## Installation

From the repo root, activate the virtual environment and install the package in
editable mode (no build isolation needed because there is no C extension):

```bash
source .venv/bin/activate          # or your venv of choice
cd backend/foo
pip install -e . --no-build-isolation -v
```

Expected output ends with:

```text
Successfully installed triton-foo-backend-0.1.0
```

## Running the test

Triton is not installed as a regular pip package in this project; its Python
source lives under the downloaded artifact directory. Set `PYTHONPATH` and
`LD_LIBRARY_PATH` before running the test:

```bash
source .venv/bin/activate
export TRITON_DIR=<repo-root>/triton-*-linux-x64        # adjust glob as needed
export LLVM_DIR=<repo-root>/llvm-*-linux-x64
export LD_LIBRARY_PATH="$TRITON_DIR/lib:$LLVM_DIR/lib:$LD_LIBRARY_PATH"
export PYTHONPATH="$TRITON_DIR/python"

cd backend/foo
python test_foo_backend.py
```

Expected output:

```text
Registered Triton backends:
  foo: compiler=FooBackend, driver=FooDriver

foo backend is available.
```

### Using pytest

```bash
pytest test_foo_backend.py -v
```

## Implementing a real backend

Replace the stub methods in `compiler.py` and `driver.py`:

| File          | Class        | Key methods to implement                                                                                  |
| ------------- | ------------ | --------------------------------------------------------------------------------------------------------- |
| `compiler.py` | `FooBackend` | `supports_target`, `parse_options`, `add_stages`, `load_dialects`, `get_module_map`, `hash`               |
| `driver.py`   | `FooDriver`  | `is_active`, `get_current_target`, `map_python_to_cpp_type`, `get_active_torch_device`, `get_benchmarker` |

Refer to the in-tree backends for full implementations:

- `triton/python/triton/backends/cpu/`
- `triton/python/triton/backends/nvidia/`
- `triton/python/triton/backends/amd/`
