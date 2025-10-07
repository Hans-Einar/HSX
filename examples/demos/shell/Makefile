REPO_ROOT := $(abspath $(CURDIR)/../../..)
PYTHON ?= $(if $(HSX_PY),$(HSX_PY),python)
CLANG ?= $(if $(HSX_CLANG),$(HSX_CLANG),clang)
BUILD_DIR ?= build
CLANGFLAGS ?= -S -emit-llvm -O0 -fno-builtin
MKDIR_CMD = $(PYTHON) -c "import os, sys; os.makedirs(os.path.dirname(os.path.abspath(sys.argv[1])), exist_ok=True)" "$@"

PAYLOAD_SRC := $(wildcard payloads/*/main.c)
PAYLOADS := $(patsubst payloads/%/main.c,%,$(PAYLOAD_SRC))
PAYLOAD_LL := $(addsuffix /main.ll,$(addprefix $(BUILD_DIR)/payloads/,$(PAYLOADS)))
PAYLOAD_MVA := $(PAYLOAD_LL:.ll=.mvasm)
PAYLOAD_HXE := $(PAYLOAD_LL:.ll=.hxe)

.SECONDARY: $(PAYLOAD_LL) $(PAYLOAD_MVA)

.PHONY: all payloads shell run clean

all: $(BUILD_DIR)/shell.hxe $(PAYLOAD_HXE)

payloads: $(PAYLOAD_HXE)

shell: $(BUILD_DIR)/shell.hxe

run: all
	$(PYTHON) "$(REPO_ROOT)/platforms/python/host_vm.py" $(BUILD_DIR)/shell.hxe --exec-root "$(abspath $(BUILD_DIR)/payloads)" --no-preload $(RUN_ARGS)

$(BUILD_DIR)/shell.hxe: shell.mvasm
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/asm.py" $< -o $@

$(BUILD_DIR)/payloads/%/main.hxe: $(BUILD_DIR)/payloads/%/main.mvasm
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/asm.py" $< -o $@

$(BUILD_DIR)/payloads/%/main.mvasm: $(BUILD_DIR)/payloads/%/main.ll
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hsx-llc.py" $< -o $@

$(BUILD_DIR)/payloads/%/main.ll: payloads/%/main.c
	$(MKDIR_CMD)
	$(CLANG) $(CLANGFLAGS) $< -o $@

clean:
	$(PYTHON) -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" $(BUILD_DIR)
