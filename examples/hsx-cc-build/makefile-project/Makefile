# Makefile for HSX project using hsx-cc-build.py
# This demonstrates how to integrate hsx-cc-build.py with make

PROJECT_ROOT := $(shell pwd)
PYTHON := python3
HSX_CC_BUILD := $(PROJECT_ROOT)/../../../python/hsx-cc-build.py

# Source files
SOURCES := main.c module1.c module2.c
OUTPUT := myapp.hxe

.PHONY: all debug release clean help

help:
	@echo "Available targets:"
	@echo "  make all     - Build release version"
	@echo "  make debug   - Build debug version with symbols"
	@echo "  make release - Build optimized release"
	@echo "  make clean   - Remove build artifacts"

all: release

debug:
	$(PYTHON) $(HSX_CC_BUILD) --debug $(SOURCES) -o $(OUTPUT)

release:
	$(PYTHON) $(HSX_CC_BUILD) $(SOURCES) -o $(OUTPUT) -b build/release

clean:
	rm -rf build/
	@echo "Cleaned build artifacts"

# You can also invoke hsx-cc-build.py from make for custom rules
custom-build:
	$(PYTHON) $(HSX_CC_BUILD) --debug -v $(SOURCES) -o $(OUTPUT) --app-name MyCustomApp
