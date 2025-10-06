# HSX Test Examples

Each `test_*` directory mirrors a pytest scenario under `python/tests/` and contains a `main.c` (plus optional helpers) that exercises the same toolchain path. Build outputs land in `build/<name>/` when you run `make`.

Use `make -C examples/tests` to compile everything, or `make -C examples/tests run-test_ir_icmp RUN_ARGS="--trace"` to run a single sample in the host VM with tracing enabled.
