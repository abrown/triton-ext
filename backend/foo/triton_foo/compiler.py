"""Stub compiler for the foo Triton backend."""

from dataclasses import dataclass
from types import ModuleType
from typing import Dict

from triton.backends.compiler import BaseBackend, GPUTarget


@dataclass(frozen=True)
class FooOptions:
    """Compilation options for the foo backend."""
    num_warps: int = 1
    num_ctas: int = 1
    num_stages: int = 1
    debug: bool = False
    backend_name: str = "foo"

    def hash(self) -> str:
        import hashlib
        key = "_".join(f"{k}-{v}" for k, v in sorted(self.__dict__.items()))
        return hashlib.sha256(key.encode()).hexdigest()


class FooBackend(BaseBackend):
    """Minimal stub implementation of BaseBackend for the foo backend."""

    @staticmethod
    def supports_target(target: GPUTarget) -> bool:
        """Accept any target whose backend field is 'foo'."""
        return target.backend == "foo"

    def __init__(self, target: GPUTarget) -> None:
        super().__init__(target)

    def hash(self) -> str:
        """Return a unique identifier for this backend instance."""
        return f"foo-0.1-{self.target.arch}"

    def parse_options(self, options: dict) -> FooOptions:
        """Convert an options dict into a FooOptions object."""
        known = {
            k: options[k]
            for k in FooOptions.__dataclass_fields__ if k in options
        }
        return FooOptions(**known)

    def add_stages(self, stages: dict, options: object) -> None:
        """Register compilation stages (stubs — produce empty bytes at the end)."""
        stages["ttir"] = lambda src, metadata: src
        stages["ttgir"] = lambda src, metadata: src
        stages["llir"] = lambda src, metadata: src
        stages["foo"] = lambda src, metadata: b""

    def load_dialects(self, context) -> None:
        """Load any MLIR dialects needed by this backend (none for the stub)."""
        pass

    def get_module_map(self) -> Dict[str, ModuleType]:
        """Return an empty module map; no device-specific modules."""
        return {}
