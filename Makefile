# Shortcuts for building the project; the true build system is CMake, but this records common commands.

TRITON_INSTALL_DIR ?= $(shell ci/pick-local-artifact.py triton)
LLVM_INSTALL_DIR ?= $(shell ci/pick-local-artifact.py llvm)
$(if $(and $(TRITON_INSTALL_DIR),$(LLVM_INSTALL_DIR)),,$(error Missing artifact directories))
BUILD_DIR ?= build
EXTRA_CMAKE_ARGS ?=

default: build

.PHONY: configure
configure:
	mkdir -p ${BUILD_DIR}
	LLVM_INSTALL_DIR="$(LLVM_INSTALL_DIR)" \
	TRITON_INSTALL_DIR="$(TRITON_INSTALL_DIR)" \
		cmake -S . -B ${BUILD_DIR} -G Ninja ${EXTRA_CMAKE_ARGS}

.PHONY: build
build: configure
	cmake --build ${BUILD_DIR}

.PHONY: test
test: test-lit test-unit test-packages

# Self-packaging extensions (link against a Triton wheel; see
# pass/ArithmeticIntensity/README.md). These build + install themselves via pip
# and load their bundled plugin library on import, so they need a Triton wheel
# built with TRITON_EXT_ENABLED=1 installed in the environment and an
# LLVM_INSTALL_DIR whose ABI matches that wheel (e.g. Triton's cached LLVM under
# ~/.triton/llvm). If Triton is not importable, the tests skip gracefully.
PACKAGE_EXTENSIONS ?= pass/ArithmeticIntensity

.PHONY: test-packages
test-packages:
	@if python -c "import triton" >/dev/null 2>&1; then \
		for ext in $(PACKAGE_EXTENSIONS); do \
			echo "Building + installing packaged extension: $$ext"; \
			LLVM_INSTALL_DIR="$(LLVM_INSTALL_DIR)" \
				python -m pip install -e "$$ext" --no-build-isolation || exit 1; \
			python -m pytest -v "$$ext/test" || exit 1; \
		done; \
	else \
		echo "Skipping test-packages: no Triton wheel installed (import triton failed)"; \
	fi

.PHONY: test-lit
test-lit:
	ninja -C ${BUILD_DIR} check-lit-tests

.PHONY: test-unit
test-unit:
	BUILD_DIR="${BUILD_DIR}" \
	LLVM_INSTALL_DIR="$(LLVM_INSTALL_DIR)" \
	TRITON_INSTALL_DIR="$(TRITON_INSTALL_DIR)" \
		python -m pytest -v \
			--ignore=extensions/utlx --ignore=backend \
			--ignore=pass/ArithmeticIntensity \
			--ignore=triton-efabbe1b-linux-x64 --ignore=$(TRITON_INSTALL_DIR)

.PHONY: clean
clean:
	rm -rf ${BUILD_DIR}

.PHONY: clean-all
clean-all: clean
	rm -rf triton-* llvm-*
