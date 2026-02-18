
LLVM_DIR ?= $(shell ci/pick-local-artifact.py llvm)
TRITON_DIR ?= $(shell ci/pick-local-artifact.py triton)
TRITON_BUILD_DIR ?= $(shell find $(TRITON_DIR)/build -maxdepth 1 -name "cmake.*" -type d | head -1)
BUILD_DIR ?= build

.PHONY: build
build:
	mkdir -p ${BUILD_DIR}
	LLVM_DIR="$(LLVM_DIR)" \
	TRITON_DIR="$(TRITON_DIR)" \
	TRITON_BUILD_DIR="$(TRITON_BUILD_DIR)" \
		cmake -S . -B ${BUILD_DIR} -G Ninja
	cmake --build ${BUILD_DIR}

.PHONY: test
test:
	ninja -C ${BUILD_DIR} check-triton-lit-tests

.PHONY: clean
clean:
	rm -rf ${BUILD_DIR}
