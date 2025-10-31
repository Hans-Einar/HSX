# ---------- OS detection ----------
ifeq ($(OS),Windows_NT)
  IS_WINDOWS := 1
else
  IS_WINDOWS :=
endif

# ---------- REPO_ROOT (uten $(shell) på *nix og med PowerShell på Windows) ----------
ifeq ($(IS_WINDOWS),1)
  # Bruk PowerShell og LiteralPath for å få absolutt path trygt med mellomrom
  REPO_ROOT := $(shell powershell -NoProfile -Command "[System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath '$(CURDIR)\..\..').Path)")
else
  # Bruk make sine egne path-funksjoner (tåler mellomrom riktig når du siterer ved bruk)
  REPO_ROOT := $(abspath $(CURDIR)/../..)
endif

# ---------- Python valg ----------
# Tips: sett HSX_PY til full sti, f.eks. C:\Python312\python.exe
ifeq ($(origin PYTHON), undefined)
  ifneq ($(HSX_PY),)
    PYTHON := $(HSX_PY)
  else
    ifeq ($(IS_WINDOWS),1)
      # Ikke forsøk 'where' her – det blir tullete med mellomrom. Stol på PATH.
      PYTHON := python
    else
      PYTHON := $(or $(shell command -v python3 2>/dev/null),$(shell command -v python 2>/dev/null),python)
    endif
  endif
endif

CLANG ?= $(if $(HSX_CLANG),$(HSX_CLANG),clang)
VM := $(REPO_ROOT)/platforms/python/host_vm.py
BUILD_DIR ?= build
CLANGFLAGS ?= -S -emit-llvm -O0 -fno-builtin
RUN_ARGS ?=

# mkdir som funker på begge OS (kjøres i recipe, derfor siteres "$@")
MKDIR_CMD = "$(PYTHON)" -c "import os,sys; p=os.path.abspath(sys.argv[1]); os.makedirs(os.path.dirname(p),exist_ok=True)" "$@"

LIB_DIR := $(REPO_ROOT)/examples/lib
INCLUDE_DIR := $(REPO_ROOT)/include

HSX_EXTRA_MVASM_mailbox_producer := \
	examples/lib/hsx_mailbox.mvasm \
	examples/lib/hsx_stdio.mvasm
HSX_EXTRA_MVASM_mailbox_consumer := \
	examples/lib/hsx_mailbox.mvasm \
	examples/lib/hsx_stdio.mvasm

.SECONDARY:
.PHONY: all longrun runlongrun mailbox_producer mailbox_consumer run_mailbox_producer run_mailbox_consumer shell runshell clean print-root

print-root:
	@echo REPO_ROOT="$(REPO_ROOT)"
	@echo PYTHON   ="$(PYTHON)"

all: longrun mailbox_producer mailbox_consumer

longrun: $(BUILD_DIR)/longrun/main.hxe

runlongrun: longrun
	"$(PYTHON)" "$(VM)" "$(BUILD_DIR)/longrun/main.hxe" $(RUN_ARGS)

$(BUILD_DIR)/longrun/main.hxe: $(BUILD_DIR)/longrun/main.mvasm
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/build_hxe.py" \
		--asm "$(REPO_ROOT)/python/asm.py" \
		--linker "$(REPO_ROOT)/python/hld.py" \
		--main "$<" \
		--out "$@"

$(BUILD_DIR)/longrun/main.mvasm: $(BUILD_DIR)/longrun/main.ll
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/hsx-llc.py" "$<" -o "$@"

$(BUILD_DIR)/longrun/main.ll: longrun/main.c
	$(MKDIR_CMD)
	"$(CLANG)" $(CLANGFLAGS) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" "$<" -o "$@"

mailbox_producer: $(BUILD_DIR)/mailbox/producer.hxe
mailbox_consumer: $(BUILD_DIR)/mailbox/consumer.hxe

run_mailbox_producer: mailbox_producer
	"$(PYTHON)" "$(VM)" "$(BUILD_DIR)/mailbox/producer.hxe" $(RUN_ARGS)

run_mailbox_consumer: mailbox_consumer
	"$(PYTHON)" "$(VM)" "$(BUILD_DIR)/mailbox/consumer.hxe" $(RUN_ARGS)

$(BUILD_DIR)/mailbox/producer.hxe: $(BUILD_DIR)/mailbox/producer.mvasm
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/build_hxe.py" \
		--asm "$(REPO_ROOT)/python/asm.py" \
		--linker "$(REPO_ROOT)/python/hld.py" \
		--main "$<" \
		--out "$@" $(foreach lib,$(HSX_EXTRA_MVASM_mailbox_producer), --extra "$(REPO_ROOT)/$(lib)")

$(BUILD_DIR)/mailbox/producer.mvasm: $(BUILD_DIR)/mailbox/producer.ll
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/hsx-llc.py" "$<" -o "$@"

$(BUILD_DIR)/mailbox/producer.ll: mailbox/producer.c
	$(MKDIR_CMD)
	"$(CLANG)" $(CLANGFLAGS) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" "$<" -o "$@"

$(BUILD_DIR)/mailbox/consumer.hxe: $(BUILD_DIR)/mailbox/consumer.mvasm
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/build_hxe.py" \
		--asm "$(REPO_ROOT)/python/asm.py" \
		--linker "$(REPO_ROOT)/python/hld.py" \
		--main "$<" \
		--out "$@" $(foreach lib,$(HSX_EXTRA_MVASM_mailbox_consumer), --extra "$(REPO_ROOT)/$(lib)")

$(BUILD_DIR)/mailbox/consumer.mvasm: $(BUILD_DIR)/mailbox/consumer.ll
	$(MKDIR_CMD)
	"$(PYTHON)" "$(REPO_ROOT)/python/hsx-llc.py" "$<" -o "$@"

$(BUILD_DIR)/mailbox/consumer.ll: mailbox/consumer.c
	$(MKDIR_CMD)
	"$(CLANG)" $(CLANGFLAGS) -I"$(LIB_DIR)" -I"$(INCLUDE_DIR)" "$<" -o "$@"

.PHONY: clean

clean:
	@ "$(PYTHON)" -c "import shutil, os; shutil.rmtree(r'$(BUILD_DIR)', ignore_errors=True)"
	@ echo clean done
