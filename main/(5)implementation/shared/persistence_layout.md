# Persistence Layout (FRAM/E2)

- Keyspace: 16-bit keys (
s_id:key_id) mapped from value descriptors (DG-7.3).
- Blocks: [key, length, crc, payload] stored sequentially; wear-leveling TBD.
- Lifecycle:
  1. On boot, provisioning module scans FRAM table, validates CRC, hydrates values flagged load.
  2. On value update with save mode, schedule debounced write (DR-5.3).
  3. On CRC failure, mark entry stale, fall back to defaults, emit warning event.

Implementation doc Provisioning.md must reference this layout.
