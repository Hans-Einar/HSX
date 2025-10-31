# HSX Security & Access Control (Design Option)

> Lightweight placeholder capturing the agreed security focus areas so future milestones can reference a single stub while the implementation remains on hold.

## Scope
- Executive-facing interfaces that could require authentication or authorization (shell/debugger RPC, provisioning channels, value/command APIs).
- Transport integrity for provisioning pathways (CAN, SD, host) plus persistence surfaces (EEPROM/FRAM).
- Operator workflows that might need audit or rate limiting once policies exist.

## Current Status
- No authentication or ACL enforcement is implemented; all attached clients are trusted.
- Value and command namespaces rely on cooperative behaviour; sensitive operations should remain out of band until policies are defined.
- Provisioning assumes trusted media (developer workstation, lab CAN bus) and validates payload integrity via `.hxe` CRCs only.

## Design Option (Deferred)
- Treat security as a future design option once the runtime feature set stabilises.
- Track policy decisions (auth levels, tokens, signatures) in this document before promoting requirements into the executive/tooling specs.
- Keep the executive/documentation references scoped to “design option” language to avoid implying behaviour that is not yet implemented.

## Placeholder Considerations
1. **Session-level auth:** optional shared secret or device token negotiated during `session.open`.
2. **Value/command ACLs:** extend descriptors with `auth_level` or token requirements; enforce host-side until MiniVM-level checks exist.
3. **Provisioning integrity:** add signature blocks alongside the existing CRC once policy agreed.
4. **Transport hardening:** rate limiting / filtering for CAN shell commands or remote exec to mitigate flooding.

## Next Steps (When Reactivated)
- Confirm security requirements with stakeholders (product, field, security).
- Update [main/04--Design/04.02--Executive.md](../main/04--Design/04.02--Executive.md) and related specs with normative requirements, replacing the “design option” qualifier.
- Prototype host-side enforcement in Python executive and shell tooling before porting to embedded targets.
