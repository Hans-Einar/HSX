# .mailbox Section Schema (JSON, v1)

- Payload: UTF-8 JSON object or array.
- Preferred form:
  ```json
  {
    "version": 1,
    "mailboxes": [
      {
        "target": "app:telemetry",
        "capacity": 128,
        "mode_mask": 0x0007,
        "owner_pid": 2,
        "bindings": [{"pid": 2, "flags": 1}]
      }
    ]
  }
  ```
- If the top-level value is an array, it is treated as the `mailboxes` list; `version` defaults to `1` when omitted.
- Field rules per entry:
  - `target` (string, required): namespace-prefixed mailbox name (`svc:`, `pid:`, `app:`, `shared:`).
  - `capacity` (int, optional): requested ring capacity in bytes. `0`/`null`/missing ⇒ use executive default (`HSX_MBX_DEFAULT_RING_CAPACITY`).
  - `mode_mask` (int, optional): `HSX_MBX_MODE_*` bit-mask. Defaults to `HSX_MBX_MODE_RDWR` if absent/zero.
  - `owner_pid` (int, optional): nominal owner PID for diagnostic tooling.
  - `bindings` (array, optional): declarative binding hints. Each object must include `pid` (int) and may include `flags` plus future attributes. Values are normalised to integers and preserved.
  - `reserved` (any, optional): stored verbatim for forward compatibility.
- Loader behaviour:
  - Validates field types, normalises integers, rejects duplicate targets.
  - Emits records with both normalised fields (`target`, `capacity`, `mode_mask`, `bindings`, `owner_pid`) and a `raw` snapshot for tooling.
  - Falls back to the legacy binary table (`>IHHQ` entries + string table) when JSON decoding fails; legacy data is wrapped into the same normalised structure with `_source="legacy"` and empty bindings.
