# 08 — Audit trail for lookups

Status: resolved — Audit Trail in `rds-v3-migration/09`+`12` (commit `2a5b904`)
Type: task
Blocked by: 04

Because the lookup interface is public / no-auth (ADR-0004), the forensic guarantee comes
from auditing, not access control. Record every **Lookup Session** as an audit entry: a
timestamp, an identifier (a service id for now — a caller-supplied id later), the
algorithm, each digest submitted, its per-item status (`known`/`unknown`/`invalid`), and
the **Release** + applied **Delta releases** that answered. The store must be durable and,
ideally, tamper-evident, since nothing at the interface prevents a caller from issuing
arbitrary requests. Hooked in by ticket 04 as each `POST /check` completes. Define the
**Audit Entry** shape in `CONTEXT.md`.

## Comments
