# Auto-generated Makefile for HSX examples/tests (hardened for spaces)

# ---------- OS detection ----------
ifeq ($(OS),Windows_NT)
  IS_WINDOWS := 1
else
  IS_WINDOWS :=
endif

# ---------- REPO_ROOT ----------
ifeq ($(IS_WINDOWS),1)
  # Robust absolutt sti, tåler mellomrom
  REPO_ROOT := $(shell powershell -NoProfile -Command  "[System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath '$(CURDIR)\..\..').Path)")
else
  REPO_ROOT := $(abspath $(CURDIR)/../..)
endif

# ---------- Tools ----------
PYTHON ?= $(if $(HSX_PY),$(HSX_PY),python)
CLANG  ?= $(if $(HSX_CLANG),$(HSX_CLANG),clang)

VM          := $(REPO_ROOT)/platforms/python/host_vm.py
BUILD_DIR   ?= build
HXE_BUILDER := $(REPO_ROOT)/python/build_hxe.py

# NB: -target beholdes som hos deg
CLANGFLAGS_BASE := -S -emit-llvm -O0 -fno-builtin -fno-ms-compatibility -fno-ms-extensions -target wasm32-unknown-unknown
CLANGFLAGS     := $(CLANGFLAGS_BASE)

# Inkludérstier (siteres der de brukes)
LIB_DIR     := $(REPO_ROOT)/examples/lib
INCLUDE_DIR := $(REPO_ROOT)/include

RUN_ARGS ?=
DEBUG ?= 0
DEBUG_PREFIX_MAP_ENV := $(or $(HSX_DEBUG_PREFIX_MAP),$(DEBUG_PREFIX_MAP))

ifeq ($(DEBUG),1)
  BUILD_DIR := build/debug
  # Allow hsx-cc-build --debug to force full DWARF info for locals/watches
  ifeq ($(strip $(HSX_CC_FORCE_FULL_DEBUG)),1)
    CLANGFLAGS += -g
  else
    # Legacy fallback when invoking make debug directly
    CLANGFLAGS += -gline-tables-only
  endif
  ifneq ($(strip $(DEBUG_PREFIX_MAP_ENV)),)
    CLANGFLAGS += -fdebug-prefix-map=$(DEBUG_PREFIX_MAP_ENV)
  endif
endif

# Kryssplattform mkdir som tåler mellomrom i $@
MKDIR_CMD = "$(PYTHON)" -c "import os,sys; p=os.path.abspath(sys.argv[1]); os.makedirs(os.path.dirname(p),exist_ok=True)" "$@"

# ---------- Tests discovery ----------
TEST_DIR_GLOBS := $(wildcard test_*/main.c)
TEST_DIRS      := $(sort $(dir $(TEST_DIR_GLOBS)))
TESTS          := $(patsubst %/,%,$(TEST_DIRS))

LL_ARTIFACTS   := $(addsuffix /main.ll,$(addprefix $(BUILD_DIR)/,$(TESTS)))
MVA_ARTIFACTS  := $(LL_ARTIFACTS:.ll=.mvasm)
HXE_ARTIFACTS  := $(LL_ARTIFACTS:.ll=.hxe)

LINKER_TEST       := test_linker
LINKER_COMPONENTS := main lib
LINKER_LL         := $(addsuffix .ll,$(addprefix $(BUILD_DIR)/$(LINKER_TEST)/,$(LINKER_COMPONENTS)))
LINKER_MVA        := $(LINKER_LL:.ll=.mvasm)
LINKER_HXO        := $(LINKER_LL:.ll=.hxo)
LINKER_DBG        := $(LINKER_LL:.ll=.dbg)

.SECONDARY: $(LL_ARTIFACTS) $(MVA_ARTIFACTS) $(HXE_ARTIFACTS) $(LINKER_LL) $(LINKER_MVA) $(LINKER_HXO)

# Ekstrabibliotek for spesifikke tester
HSX_EXTRA_MVASM_test_stdio_mailbox_c    := examples/lib/hsx_mailbox.mvasm examples/lib/hsx_stdio.mvasm
HSX_EXTRA_MVASM_test_mailbox_producer_c := examples/lib/hsx_mailbox.mvasm
HSX_EXTRA_MVASM_test_mailbox_consumer_c := examples/lib/hsx_mailbox.mvasm examples/lib/hsx_stdio.mvasm

.PHONY: all tests run-% clean list print-root debug

# ---------- Utility ----------
print-root:
	@echo REPO_ROOT="$(REPO_ROOT)"
	@echo PYTHON   ="$(PYTHON)"
	@echo CLANG    ="$(CLANG)"

# ---------- Default ----------
all: $(HXE_ARTIFACTS)

debug:
	$(MAKE) DEBUG=1 all

ifeq ($(strip $(TESTS)),)
$(warning No test_* directories with main.c found under $(CURDIR).)
endif

tests: all

list:
	@for t in $(TESTS); do echo $$t; done

run-%: $(BUILD_DIR)/%/main.hxe
	"$(PYTHON)" "$(VM)" "$<" $(RUN_ARGS)

# ---------- Linker test pipeline ----------
$(BUILD_DIR)/$(LINKER_TEST)/main.hxe: $(LINKER_HXO)
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/hld.py" -o "$@" \
		$(foreach f,$^,"$(f)") \
		$(if $(DEBUG),$(foreach dbg,$(LINKER_DBG),--debug-info "$(dbg)") --emit-sym "$(@:.hxe=.sym)",)

$(BUILD_DIR)/$(LINKER_TEST)/%.hxo: $(BUILD_DIR)/$(LINKER_TEST)/%.mvasm
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/asm.py" "$<" -o "$@"

$(BUILD_DIR)/$(LINKER_TEST)/%.mvasm: $(BUILD_DIR)/$(LINKER_TEST)/%.ll
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/hsx-llc.py" "$<" -o "$@" \
		$(if $(DEBUG),--emit-debug "$(@:.mvasm=.dbg)",)

$(BUILD_DIR)/$(LINKER_TEST)/%.ll: $(LINKER_TEST)/%.c
	$(MKDIR_CMD)
	"$(CLANG)" $(CLANGFLAGS) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" "$<" -o "$@"

# ---------- Generic test pipeline ----------
$(BUILD_DIR)/%/main.hxe: $(BUILD_DIR)/%/main.mvasm
	$(MKDIR_CMD)
	"$(PYTHON)" "$(HXE_BUILDER)" \
		--asm "$(REPO_ROOT)/python/asm.py" \
		--linker "$(REPO_ROOT)/python/hld.py" \
		--main "$<" \
		--out "$@" \
		$(foreach lib,$(HSX_EXTRA_MVASM_$*), --extra "$(REPO_ROOT)/$(lib)") \
		$(if $(DEBUG),--debug-info "$(@:.hxe=.dbg)"$(if $(strip $(HSX_EXTRA_MVASM_$*)),, --emit-sym "$(@:.hxe=.sym)"),)

$(BUILD_DIR)/%/main.mvasm: $(BUILD_DIR)/%/main.ll
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/hsx-llc.py" "$<" -o "$@" \
		$(if $(DEBUG),--emit-debug "$(@:.mvasm=.dbg)",)

$(BUILD_DIR)/%/main.ll: %/main.c
	$(MKDIR_CMD)
	"$(CLANG)" $(CLANGFLAGS) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" "$<" -o "$@"

# ---------- Clean ----------
.PHONY: clean

clean:
	@ "$(PYTHON)" -c "import shutil, os; shutil.rmtree(r'$(BUILD_DIR)', ignore_errors=True)"
	@ echo clean done
