# HSX Repository Refactor Plan

## Vision
Build a tidy, automation-friendly workspace that centres on the Python toolchain and host VM while keeping room for hardware backends and legacy experiments. The refactor should make it easy to add new examples, run tests from one command, and scale towards documentation tooling (e.g. Doxygen) and future CI.

## Guiding Principles
- Keep Python toolchain sources first-class; other language targets live under clearly named subtrees.
- Prefer generated artefacts inside per-target `build/` folders to keep the repository root clean.
- Mirror automated tests with runnable examples so Python `pytest` and C drivers stay in sync.
- Remove or archive ad-hoc scripts (batch files) in favour of Make-based entry points.
- Design for future multi-platform host VM builds without breaking current workflows.

## Proposed Directory Layout
```
HSX/
  Makefile                  # entry point: lint, test, docs, package
  README.md                 # stays at root for quick-start context
  AGENTS.md                 # quick contributor briefing, root accessible
  MILESTONES.md             # keep at root for now, move later if desired
  LICENSE
  docs/
    Doxyfile
    Makefile                # wraps doxygen + doc-specific tooling
    *.md                    # all other markdown content slated for docs/
  python/
    asm.py
    hsx-llc.py
    hld.py
    toolchain_util.py
    host_vm.py              # (reserved for shared helpers, primary VM lives under platforms/python/)
    tests/
      test_vm_exit.py
      ...
  examples/
    tests/
      Makefile             # builds/runs unit-aligned samples
      build/               # auto-generated per sample (gitignored)
        test_vm_exit/
          test_vm_exit.ll
          test_vm_exit.mvasm
          test_vm_exit.hxe
      test_vm_exit/
        main.c             # mirrors python/tests/test_vm_exit.py
      test_ir_call/
        main.c
      ...
    demos/
      Makefile             # larger user-facing programs
      build/
      uart_shell/
        main.c
    legacy/
      README.md            # pointer explaining archived batch tools
      *.bat (optional reference)
  platforms/
    python/
      host_vm.py           # primary implementation lives here
      README.md            # documents host VM usage and options
      (future) alt hosts (avr128da28, cortex-m4)
  tools/
    pack.py
    ...                    # packaging helpers kept centralised
```

## Build & Test Strategy
- **Top-level Makefile** provides orchestrators:
  - `make tests` -> runs `pytest` and `examples/tests` builds.
  - `make examples-tests` -> compiles every C sample under `examples/tests` producing outputs in `examples/tests/build/<sample>/`.
  - `make run-<sample>` -> delegates to `examples/tests/Makefile` (set RUN_ARGS="--trace" for VM flags) and executes via `platforms/python/host_vm.py`.
  - `make clean` -> cascades to sub-makefiles, removing only generated outputs.
- **Naming convention**: mirror directories with the `test_` prefix (e.g. `test_vm_exit/`) so correspondence with pytest modules is obvious.
- **`examples/tests/Makefile`** responsibilities:
  - Auto-discover each `test_*` subdirectory containing a `main.c` (or configurable entry file).
  - Provide per-sample targets: `make test_ir_call`, `make run-test_ir_call`, `make clean-test_ir_call`.
  - Emit intermediate `.ll`, `.mvasm`, and final `.hxe` into `build/<sample>/`.
  - Allow `BUILD_DIR?=build` overrides so CI or developers can customise paths if needed.
- **Intermediate artefacts**: keep `.ll` alongside `.mvasm/.hxe` inside `build/<sample>/` for now to aid debugging; track potential pruning/cleanup in the backlog.
- **Parallel builds**: use pattern rules and `$(MAKE) -C` delegation so per-sample builds can parallelise (`make -j`).
- **Legacy batch scripts**: move into `examples/legacy/` and stop wiring them into automation; keep a short README for manual reference.

## Alignment Between Pytests and C Samples
- For each critical unit test under `python/tests`, add a matching C program under `examples/tests/test_<name>/main.c` that exercises the same toolchain path.
- When pytest introduces a new regression sample, add the twin C source and rely on auto discovery to surface the Make targets.
- Provide optional metadata files (e.g. `expected.json`) if the VM output needs richer validation; these can be consumed by helper targets.

## Python Toolchain Structure
- Move the primary host VM implementation into `platforms/python/host_vm.py` and retire the legacy shim in `python/host_vm.py`.
- Keep the remaining `python/*.py` files flat until we formalise modules; introduce `python/toolchain_util.py` (or similar) for shared build helpers so Makefiles can call `python -m` entry points.
- Document CLI usage in `docs/toolchain.md` so downstream repos can "install" or vendor the toolchain cleanly.

## Documentation & Doxygen
- Relocate existing `.md` files (except `README.md`, `AGENTS.md`, `MILESTONES.md`) into `docs/` while preserving relative links.
- Add a minimal `docs/Makefile` with `make docs` invoking Doxygen and optional Markdown site generation later.
- Generate static HTML output and commit it under `docs/html/` initially; GitHub Pages can host the static site if desired once we decide on publication timing.
- Start with vanilla Doxygen theming, and evaluate alternatives (e.g. Sphinx+Breathe, MkDocs+Doxygen plugin) as part of the documentation backlog item.
- Create `docs/ARCHITECTURE.md` as landing page pointing to `HSX_SPEC.md`, `HSX_VALUE_INTERFACE.md`, etc.

## Python Environment Management
- Provide `make venv` and `make dev-env` targets that wrap `python -m venv` and dependency installation, replacing platform-specific batch scripts.
- Document environment usage in `README.md` (root) and `docs/toolchain.md` so Linux/macOS/Windows users can follow the same workflow.
- Allow developers to opt out (external tooling still supported) by guarding Make targets with existence checks.

## Packaging & Release Targets
- Add `make package` for assembling distributable archives of the toolchain (Python scripts + docs snapshot).
- Add `make release` once the workflow stabilises; it can depend on `make package`, `make docs`, and regression tests to ensure consistency before tagging.
- Consider a `make install` target later for copying scripts into a user-specified prefix.

## Implementation Phases
1. **Host VM relocation**: move `host_vm.py` into `platforms/python/` and remove the deprecated `python/host_vm.py`.
2. **Scaffold Makefiles**: top-level + `examples/tests` with empty sample; verify no behavioural change to Python tooling.
3. **Mirror Existing Tests**: port current `.bat` flows and unit coverage into new example directories; ensure `pytest` stays green.
4. **Archive Legacy Scripts**: move batch files into `examples/legacy/`, update documentation to reference new make targets.
5. **Docs Relocation**: shift Markdown into `docs/`, fix links, introduce Doxygen skeleton and add `make docs` wiring.
6. **Platform Preparation**: flesh out `platforms/python/README.md` and keep placeholders for MCU targets.
7. **CI & Packaging**: add `make ci` (pytest + examples build) and prepare for GitHub Actions or similar; wire up `make package`/`make release` once automated checks pass.

## Decisions & Follow-ups
- **Naming**: stick with `test_<name>` for mirrored examples.
- **IR retention**: keep `.ll` outputs in `build/` for now; track clean-up policy in the backlog.
- **Virtualenvs**: manage via Make (`make venv`/`make dev-env`) to stay cross-platform and avoid `.bat` scripts.
- **Docs tooling**: proceed with baseline Doxygen, publish static HTML initially, and revisit theming/hosting later.
- **Packaging**: plan for `make package`/`make release` targets once the build/test footing is stable.

## Open Questions
- Clarify expectations for publishing generated docs (commit static HTML vs GitHub Pages deployment) after the first Doxygen run lands.
- Decide whether Make should expose convenience targets for packaging external dependencies (e.g. vendored LLVM tools) alongside the Python scripts.
- Determine long-term caching strategy for large toolchain artefacts (LLVM intermediates, linked objects) when build volume grows.




