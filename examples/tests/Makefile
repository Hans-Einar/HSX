# Auto-generated Makefile for HSX examples/tests

REPO_ROOT := $(abspath $(CURDIR)/../..)
PYTHON ?= $(if $(HSX_PY),$(HSX_PY),python)
CLANG ?= $(if $(HSX_CLANG),$(HSX_CLANG),clang)
VM := $(REPO_ROOT)/platforms/python/host_vm.py
BUILD_DIR ?= build
CLANGFLAGS ?= -S -emit-llvm -O0 -fno-builtin
RUN_ARGS ?=
MKDIR_CMD = $(PYTHON) -c "import os, sys; os.makedirs(os.path.dirname(os.path.abspath(sys.argv[1])), exist_ok=True)" "$@"

TEST_DIR_GLOBS := $(wildcard test_*/main.c)
TEST_DIRS := $(sort $(dir $(TEST_DIR_GLOBS)))
TESTS := $(patsubst %/,%,$(TEST_DIRS))

LL_ARTIFACTS := $(addsuffix /main.ll,$(addprefix $(BUILD_DIR)/,$(TESTS)))
MVA_ARTIFACTS := $(LL_ARTIFACTS:.ll=.mvasm)
HXE_ARTIFACTS := $(LL_ARTIFACTS:.ll=.hxe)
.SECONDARY: $(LL_ARTIFACTS) $(MVA_ARTIFACTS) $(HXE_ARTIFACTS)

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

$(BUILD_DIR)/%/main.hxe: $(BUILD_DIR)/%/main.mvasm
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/asm.py" $< -o $@

$(BUILD_DIR)/%/main.mvasm: $(BUILD_DIR)/%/main.ll
	$(MKDIR_CMD)
	$(PYTHON) "$(REPO_ROOT)/python/hsx-llc.py" $< -o $@

$(BUILD_DIR)/%/main.ll: %/main.c
	$(MKDIR_CMD)
	$(CLANG) $(CLANGFLAGS) $< -o $@

clean:
	$(PYTHON) -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" $(BUILD_DIR)
