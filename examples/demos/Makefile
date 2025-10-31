REPO_ROOT := $(shell cd '$(CURDIR)/../..' && pwd)
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
# Note: Paths must be quoted at point of use in recipes to handle spaces
LIB_DIR := $(REPO_ROOT)/examples/lib
INCLUDE_DIR := $(REPO_ROOT)/include

HSX_EXTRA_MVASM_mailbox_producer := \
	$(REPO_ROOT)/examples/lib/hsx_mailbox.mvasm \
	$(REPO_ROOT)/examples/lib/hsx_stdio.mvasm
HSX_EXTRA_MVASM_mailbox_consumer := \
	$(REPO_ROOT)/examples/lib/hsx_mailbox.mvasm \
	$(REPO_ROOT)/examples/lib/hsx_stdio.mvasm

.SECONDARY:

.PHONY: all longrun runlongrun mailbox_producer mailbox_consumer run_mailbox_producer run_mailbox_consumer shell runshell clean

all: longrun mailbox_producer mailbox_consumer

longrun: $(BUILD_DIR)/longrun/main.hxe

runlongrun: longrun
	$(PYTHON) "$(VM)" $(BUILD_DIR)/longrun/main.hxe $(RUN_ARGS)


$(BUILD_DIR)/longrun/main.hxe: $(BUILD_DIR)/longrun/main.mvasm
	$(MKDIR_CMD)
	$(PYTHON) -c "import subprocess, sys; subprocess.run([sys.executable, '$(REPO_ROOT)/python/build_hxe.py', '--asm', '$(REPO_ROOT)/python/asm.py', '--linker', '$(REPO_ROOT)/python/hld.py', '--main', '$<', '--out', '$@'], check=True)"

$(BUILD_DIR)/longrun/main.mvasm: $(BUILD_DIR)/longrun/main.ll
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hsx-llc.py" $< -o $@

$(BUILD_DIR)/longrun/main.ll: longrun/main.c
	$(MKDIR_CMD)
	$(CLANG) $(CLANGFLAGS) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" $< -o $@

mailbox_producer: $(BUILD_DIR)/mailbox/producer.hxe

mailbox_consumer: $(BUILD_DIR)/mailbox/consumer.hxe

run_mailbox_producer: mailbox_producer
	$(PYTHON) "$(VM)" $(BUILD_DIR)/mailbox/producer.hxe $(RUN_ARGS)

run_mailbox_consumer: mailbox_consumer
	$(PYTHON) "$(VM)" $(BUILD_DIR)/mailbox/consumer.hxe $(RUN_ARGS)

$(BUILD_DIR)/mailbox/producer.hxe: $(BUILD_DIR)/mailbox/producer.mvasm
	$(MKDIR_CMD)
	$(PYTHON) -c "import subprocess, sys; subprocess.run([sys.executable, '$(REPO_ROOT)/python/build_hxe.py', '--asm', '$(REPO_ROOT)/python/asm.py', '--linker', '$(REPO_ROOT)/python/hld.py', '--main', '$<', '--out', '$@'] + [item for pair in [['--extra', lib] for lib in [$(foreach lib,$(HSX_EXTRA_MVASM_mailbox_producer),'$(lib)',)]] for item in pair], check=True)"

$(BUILD_DIR)/mailbox/producer.mvasm: $(BUILD_DIR)/mailbox/producer.ll
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hsx-llc.py" $< -o $@

$(BUILD_DIR)/mailbox/producer.ll: mailbox/producer.c
	$(MKDIR_CMD)
	$(CLANG) $(CLANGFLAGS) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" $< -o $@

$(BUILD_DIR)/mailbox/consumer.hxe: $(BUILD_DIR)/mailbox/consumer.mvasm
	$(MKDIR_CMD)
	$(PYTHON) -c "import subprocess, sys; subprocess.run([sys.executable, '$(REPO_ROOT)/python/build_hxe.py', '--asm', '$(REPO_ROOT)/python/asm.py', '--linker', '$(REPO_ROOT)/python/hld.py', '--main', '$<', '--out', '$@'] + [item for pair in [['--extra', lib] for lib in [$(foreach lib,$(HSX_EXTRA_MVASM_mailbox_consumer),'$(lib)',)]] for item in pair], check=True)"

$(BUILD_DIR)/mailbox/consumer.mvasm: $(BUILD_DIR)/mailbox/consumer.ll
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hsx-llc.py" $< -o $@

$(BUILD_DIR)/mailbox/consumer.ll: mailbox/consumer.c
	$(MKDIR_CMD)
	$(CLANG) $(CLANGFLAGS) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" $< -o $@

clean:
	$(PYTHON) -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" $(BUILD_DIR)
