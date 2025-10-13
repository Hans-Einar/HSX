REPO_ROOT := $(abspath $(CURDIR)/../..)
ifeq ($(origin PYTHON), undefined)
  ifneq ($(HSX_PY),)
    PYTHON := $(HSX_PY)
  else
    PYTHON := $(shell command -v python 2>/dev/null)
    ifeq ($(PYTHON),)
      PYTHON := $(shell command -v python3 2>/dev/null)
    endif
    ifeq ($(PYTHON),)
      PYTHON := python
    endif
  endif
endif
CLANG ?= $(if $(HSX_CLANG),$(HSX_CLANG),clang)
VM := $(REPO_ROOT)/platforms/python/host_vm.py
BUILD_DIR ?= build
CLANGFLAGS ?= -S -emit-llvm -O0 -fno-builtin
RUN_ARGS ?=
MKDIR_CMD = $(PYTHON) -c "import os, sys; os.makedirs(os.path.dirname(os.path.abspath(sys.argv[1])), exist_ok=True)" "$@"

.SECONDARY:

.PHONY: all longrun runlongrun shell runshell clean

all: longrun

longrun: $(BUILD_DIR)/longrun/main.hxe

runlongrun: longrun
	$(PYTHON) "$(VM)" $(BUILD_DIR)/longrun/main.hxe $(RUN_ARGS)


$(BUILD_DIR)/longrun/main.hxe: $(BUILD_DIR)/longrun/main.mvasm
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/asm.py" $< -o $@

$(BUILD_DIR)/longrun/main.mvasm: $(BUILD_DIR)/longrun/main.ll
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hsx-llc.py" $< -o $@

$(BUILD_DIR)/longrun/main.ll: longrun/main.c
	$(MKDIR_CMD)
	$(CLANG) $(CLANGFLAGS) $< -o $@

clean:
	$(PYTHON) -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" $(BUILD_DIR)
