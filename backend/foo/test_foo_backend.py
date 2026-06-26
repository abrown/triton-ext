"""Test that the foo backend is discoverable by Triton."""

from triton.backends import backends


def test_foo_backend_is_available():
    """The foo backend must appear in Triton's backend registry."""
    print("Registered Triton backends:")
    for name, backend in backends.items():
        print(
            f"  {name}: compiler={backend.compiler.__name__}, driver={backend.driver.__name__}"
        )

    assert "foo" in backends, (
        f"'foo' backend not found in registered backends: {list(backends.keys())}"
    )
    print("\nfoo backend is available.")


if __name__ == "__main__":
    test_foo_backend_is_available()
