# 09: Record an Audit Entry for every Lookup Session

**What to build:** the forensic guarantee behind a public interface (ADR-0004). Every
finished **Lookup Session** produces an **Audit Entry** — timestamp, a caller identifier
(a fixed service id for now), the **Algorithm**, each **Digest** with its per-item status,
and the **Release** + applied **Delta releases** that answered — written to a durable,
append-only **Audit Trail**. Verified black-box at Seam 1.

The interface stays **public** (no authentication); the **Audit Trail** is the safety net.

**Blocked by:** 07 (`POST /check` + `/health` for MD5)

**Status:** resolved

- [x] Each successful **Lookup Session** writes exactly one **Audit Entry**.
- [x] An **Audit Entry** records timestamp, caller identifier, **Algorithm**, each **Digest**
         + per-item status, and the **Release** + applied **Delta releases** that answered.
- [x] The **Audit Trail** is append-only and durable.
- [x] Verified at Seam 1 by observing that the entry was produced after a session; the
         **Audit Trail** internals are not a separate seam.
- [x] No authentication layer is added (interface remains public).

## Comments

Delivered in `api/audit.py`: `AuditTrail` (JSON-line append-only, file-backed,
`configure_audit`-injectable for Seam 1). `api/app.py` calls `_record_session`
for every finished `POST /check` session, stamping timestamp + fixed service id
(caller) + algorithm + per-digest results + dataset provenance. `api/tests/
integration/test_audit_entries.py` observes the entry at Seam 1 (one entry per
session, full field set, durability by re-reading the file). No auth added.
