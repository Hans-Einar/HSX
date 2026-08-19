# AVR HSX Implementation SDP

This track is reserved for the AVR implementation of HSX.

It owns target-specific concerns such as:

- selected AVR device(s) and hardware assumptions;
- flash/SRAM/EEPROM/external-memory budgets;
- Harvard-architecture loader/execution constraints;
- C/C++ VM implementation details;
- HEOS integration and HSX Executive-as-HEOS-task contract;
- target HAL/SVC bindings;
- timing, instruction throughput, scheduler budget, and determinism measurements;
- embedded debugger transport implementation;
- Python-reference vs AVR differential/conformance verification;
- toolchain/build/programming integration for the target.

It does not redefine portable HSX ISA/ABI/VM semantics. Those are dependencies on
`SDP/HSX`.

The AVR track remains **reserved/inactive** until the portable HSX and debugger development
environments are stable enough to define target entry criteria. The first future activity
will be a numbered Study (`AVR-ST-001`) rather than immediate implementation.
