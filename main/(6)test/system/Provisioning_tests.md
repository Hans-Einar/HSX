# Provisioning & Persistence Test Plan

## DR Coverage
- DR-1.1: Runtime loading of HXE apps over CAN/SD.
- DR-3.1: Header/CRC validation.
- DR-5.3: FRAM persistence with rollback.

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| CAN transfer | Simulate chunked CAN load with retries | Validate status events + CRC handling.
| SD manifest | Boot with TOML manifest referencing multiple HXEs | Ensure ordering + PID assignment.
| FRAM persistence | Write calibration values, power-cycle simulation | Confirm restoration + CRC checks.
| Abort/rollback | Trigger abort mid-transfer | Ensure system reverts to previous image.

## Fixtures / Mocks
- Sample manifests/HXE files under (6)/fixtures/provisioning/.
- Mock CAN transport + FRAM storage under (6)/mocks.
