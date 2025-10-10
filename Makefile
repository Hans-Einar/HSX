# HSX repository Makefile entry point

PYTHON_SYS ?= $(if $(HSX_PY),$(HSX_PY),python)
DOXYGEN ?= doxygen
VENV_DIR ?= .venv
PACKAGE_DIR ?= dist
PACKAGE_NAME ?= hsx-toolchain
RUN_ARGS ?=

ifeq ($(OS),Windows_NT)
VENV_BIN := $(VENV_DIR)/Scripts
VENV_PYTHON := $(VENV_BIN)/python.exe
VENV_PIP := $(VENV_BIN)/pip.exe
else
VENV_BIN := $(VENV_DIR)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
endif

ifneq ($(wildcard $(VENV_PYTHON)),)
PYTHON := $(VENV_PYTHON)
else
PYTHON := $(PYTHON_SYS)
endif

.DEFAULT_GOAL := help

.PHONY: help tests pytest examples-tests run-% clean docs venv dev-env clean-venv package release

help:
	@echo "HSX build targets:"
	@echo "  make tests            - run pytest and build all examples/tests"
	@echo "  make pytest           - run python unit tests"
	@echo "  make examples-tests   - build all C examples under examples/tests"
	@echo "  make run-<name>       - run host VM on examples/tests/test_<name> (pass RUN_ARGS=\"--trace\" if needed)"
	@echo "  make docs             - build documentation (if configured)"
	@echo "  make venv             - create a local Python virtual environment"
	@echo "  make dev-env          - create venv (if needed) and install dependencies"
	@echo "  make package          - assemble a distributable zip in $(PACKAGE_DIR)/"
	@echo "  make release          - run tests/docs and produce a distributable archive"
	@echo "  make clean            - remove generated artefacts"
	@echo "  make clean-venv       - remove the managed virtual environment"

pytest:
	$(PYTHON) -m pytest $(PYTEST_ARGS)

examples-tests:
	$(MAKE) -C examples/tests tests PYTHON="$(PYTHON)"

run-%:
	$(MAKE) -C examples/tests run-$* PYTHON="$(PYTHON)" RUN_ARGS="$(RUN_ARGS)"

docs:
	$(MAKE) -C docs docs PYTHON="$(PYTHON)" DOXYGEN="$(DOXYGEN)"

clean:
	$(MAKE) -C examples/tests clean PYTHON="$(PYTHON)"
	$(PYTHON_SYS) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"

venv:
	$(PYTHON_SYS) -m venv $(VENV_DIR)
	@echo "Virtual environment ready at $(VENV_DIR)"

DEV_REQUIREMENTS := $(filter $(wildcard requirements.txt requirements-dev.txt),requirements.txt requirements-dev.txt)

dev-env: venv
ifeq ($(strip $(DEV_REQUIREMENTS)),)
	@echo "No requirements*.txt found; venv created with stock interpreter."
else
	$(VENV_PYTHON) -m pip install --upgrade pip
	@for req in $(DEV_REQUIREMENTS); do "$(VENV_PIP)" install -r $$req; done
endif

clean-venv:
	$(PYTHON_SYS) -c "import shutil; shutil.rmtree('$(VENV_DIR)', ignore_errors=True)"
	@echo "Removed $(VENV_DIR)"

package: docs
	$(PYTHON_SYS) - <<'PY'
import datetime as dt
import pathlib
import shutil

root = pathlib.Path('.').resolve()
dist = root / "$(PACKAGE_DIR)"
dist.mkdir(parents=True, exist_ok=True)
stage = root / "build" / "package"
shutil.rmtree(stage, ignore_errors=True)
include = [
    "Makefile",
    "agents.md",
    "MILESTONES.md",
    "python",
    "platforms/python",
    "examples",
    "docs",
    "include",
]
for item in include:
    src = root / item
    if not src.exists():
        continue
    dest = stage / item
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
for build_dir in stage.glob('examples/**/build'):
    shutil.rmtree(build_dir, ignore_errors=True)
stamp = dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')
archive = dist / f"$(PACKAGE_NAME)-{stamp}"
shutil.make_archive(str(archive), 'zip', stage)
shutil.rmtree(stage, ignore_errors=True)
print(f"Created {archive.with_suffix('.zip')}")
PY

release: tests package
	@echo "Release artefact available under $(PACKAGE_DIR)/"

tests: pytest examples-tests

