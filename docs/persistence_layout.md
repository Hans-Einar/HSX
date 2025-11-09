# HSX Persistence Layout (Draft)

This document captures the working assumptions for the Python reference FRAM/EEPROM store. The goal is to model the C-side persistence contract closely enough that tooling and higher level flows can be validated before the embedded implementation lands.

## Key Space

- Persistence keys are 16-bit unsigned integers (0x0001 through 0xFFFE).
- 0x0000 is reserved to mean "no persistence".
- 0xFFFF is reserved for future control structures (factory reset markers, wear counters).

## Value Records

Each persisted value stores the raw IEEE-754 half precision bits that the registry exposes in the Python reference implementation. The on-disk/on-FRAM representation is therefore a 16-bit unsigned integer per key.

Offset 0: raw f16 value (uint16)

For the Python prototype the values are written into a JSON file (one entry per key). On the microcontroller port the same key/value mapping will be realised as a compact binary table with CRC and wear-levelling metadata (see design note 04.04--ValCmd §4.4.4).

## Access Semantics

- Load on boot: When the VM controller detects a value with the PERSIST flag and a non-zero persist_key, it attempts to load the stored raw value. If the load succeeds, the registry initialises the value with the persisted bits instead of the declarative init_value.
- Debounced writes: When a persistent value changes, the write is scheduled via the persistence backend. The debounce interval comes from the Persist descriptor (debounce_ms, default 0). Multiple updates within the debounce window coalesce into a single write.
- Failure handling: If a load fails (missing key/corrupt store), the registry falls back to the declarative init_value. Write failures raise a warning and leave the last known value in memory; callers can inspect events/logs to detect the problem.

## File Backing (Python Reference)

The default backend writes to HSX_FRAM_PATH (if defined) or keeps data in-memory for the current process. Writes use a temporary file + rename to keep the on-disk image crash-safe.

## Future Work

- Add CRC / version stamping for robustness.
- Integrate wear-levelling counters to match the embedded requirements.
- Document garbage collection / key rotation once the C port is scoped.
