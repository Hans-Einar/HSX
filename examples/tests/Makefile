# Auto-generated Makefile for HSX examples/tests

REPO_ROOT := $(abspath $(CURDIR)/../..)
PYTHON ?= $(if $(HSX_PY),$(HSX_PY),python)
CLANG ?= $(if $(HSX_CLANG),$(HSX_CLANG),clang)
VM := $(REPO_ROOT)/platforms/python/host_vm.py
BUILD_DIR ?= build
HXE_BUILDER := $(REPO_ROOT)/python/build_hxe.py
CLANGFLAGS_BASE := -S -emit-llvm -O0 -fno-builtin -fno-ms-compatibility -fno-ms-extensions -target wasm32-unknown-unknown
# Note: Include paths must be quoted at point of use in recipes to handle spaces
LIB_DIR := $(REPO_ROOT)/examples/lib
INCLUDE_DIR := $(REPO_ROOT)/include
RUN_ARGS ?=
MKDIR_CMD = $(PYTHON) -c "import os, sys; os.makedirs(os.path.dirname(os.path.abspath(sys.argv[1])), exist_ok=True)" "$@"

TEST_DIR_GLOBS := $(wildcard test_*/main.c)
TEST_DIRS := $(sort $(dir $(TEST_DIR_GLOBS)))
TESTS := $(patsubst %/,%,$(TEST_DIRS))

LL_ARTIFACTS := $(addsuffix /main.ll,$(addprefix $(BUILD_DIR)/,$(TESTS)))
MVA_ARTIFACTS := $(LL_ARTIFACTS:.ll=.mvasm)
LINKER_TEST := test_linker
LINKER_COMPONENTS := main lib
LINKER_LL := $(addsuffix .ll,$(addprefix $(BUILD_DIR)/$(LINKER_TEST)/,$(LINKER_COMPONENTS)))
LINKER_MVA := $(LINKER_LL:.ll=.mvasm)
LINKER_HXO := $(LINKER_LL:.ll=.hxo)
HXE_ARTIFACTS := $(LL_ARTIFACTS:.ll=.hxe)
.SECONDARY: $(LL_ARTIFACTS) $(MVA_ARTIFACTS) $(HXE_ARTIFACTS) $(LINKER_LL) $(LINKER_MVA) $(LINKER_HXO)

HSX_EXTRA_MVASM_test_stdio_mailbox_c := $(REPO_ROOT)/examples/lib/hsx_mailbox.mvasm $(REPO_ROOT)/examples/lib/hsx_stdio.mvasm
HSX_EXTRA_MVASM_test_mailbox_producer_c := $(REPO_ROOT)/examples/lib/hsx_mailbox.mvasm
HSX_EXTRA_MVASM_test_mailbox_consumer_c := $(REPO_ROOT)/examples/lib/hsx_mailbox.mvasm $(REPO_ROOT)/examples/lib/hsx_stdio.mvasm

.PHONY: all tests run-% clean list

all: $(HXE_ARTIFACTS)

ifeq ($(strip $(TESTS)),)
$(warning No test_* directories with main.c found under $(CURDIR).)
endif

tests: all

list:
	@for t in $(TESTS); do echo $$t; done

run-%: $(BUILD_DIR)/%/main.hxe
	$(PYTHON) "$(VM)" $< $(RUN_ARGS)

$(BUILD_DIR)/$(LINKER_TEST)/main.hxe: $(LINKER_HXO)
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hld.py" -o $@ $^

$(BUILD_DIR)/$(LINKER_TEST)/%.hxo: $(BUILD_DIR)/$(LINKER_TEST)/%.mvasm
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/asm.py" $< -o $@

$(BUILD_DIR)/$(LINKER_TEST)/%.mvasm: $(BUILD_DIR)/$(LINKER_TEST)/%.ll
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hsx-llc.py" $< -o $@

$(BUILD_DIR)/$(LINKER_TEST)/%.ll: $(LINKER_TEST)/%.c
	$(MKDIR_CMD)
	$(CLANG) $(CLANGFLAGS_BASE) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" $< -o $@

$(BUILD_DIR)/%/main.hxe: $(BUILD_DIR)/%/main.mvasm
	$(MKDIR_CMD)
	$(PYTHON) "$(HXE_BUILDER)" --asm "$(REPO_ROOT)/python/asm.py" --linker "$(REPO_ROOT)/python/hld.py" --main "$<" --out "$@" $(foreach lib,$(HSX_EXTRA_MVASM_$*),--extra "$(lib)")

$(BUILD_DIR)/%/main.mvasm: $(BUILD_DIR)/%/main.ll
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hsx-llc.py" $< -o $@

$(BUILD_DIR)/%/main.ll: %/main.c
	$(MKDIR_CMD)
	$(CLANG) $(CLANGFLAGS_BASE) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" $< -o $@

clean:
	$(PYTHON) -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" $(BUILD_DIR)
