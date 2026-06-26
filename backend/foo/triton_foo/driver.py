"""Stub driver for the foo Triton backend."""

from triton.backends.driver import DriverBase
from triton.backends.compiler import GPUTarget


class FooDriver(DriverBase):
    """Minimal stub implementation of DriverBase for the foo backend."""

    @staticmethod
    def is_active() -> bool:
        """Return True unconditionally so the backend is always available."""
        return True

    def map_python_to_cpp_type(self, ty: str) -> str:
        """Map a Triton type string to a C++ type string."""
        type_map = {
            "i1": "int32_t",
            "i8": "int8_t",
            "i16": "int16_t",
            "i32": "int32_t",
            "i64": "int64_t",
            "u8": "uint8_t",
            "u16": "uint16_t",
            "u32": "uint32_t",
            "u64": "uint64_t",
            "fp16": "float",
            "bf16": "float",
            "fp32": "float",
            "fp64": "double",
        }
        if ty.startswith("*"):
            return "void*"
        return type_map.get(ty, ty)

    def get_current_target(self) -> GPUTarget:
        """Return a GPUTarget representing the foo backend."""
        return GPUTarget("foo", "foo-arch-v1", 1)

    def get_active_torch_device(self):
        """Return None; foo has no real torch device."""
        return None

    def get_benchmarker(self):
        """Return a no-op benchmarker."""

        def _bench(kernel_call, *, quantiles, **kwargs):
            return [0.0] * len(quantiles)

        return _bench
