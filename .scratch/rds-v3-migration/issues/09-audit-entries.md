# 09: Record an Audit Entry for every Lookup Session

**What to build:** the forensic guarantee behind a public interface (ADR-0004). Every
finished **Lookup Session** produces an **Audit Entry** — timestamp, a caller identifier
(a fixed service id for now), the **Algorithm**, each **Digest** with its per-item status,
and the **Release** + applied **Delta releases** that answered — written to a durable,
append-only **Audit Trail**. Verified black-box at Seam 1.

The interface stays **public** (no authentication); the **Audit Trail** is the safety net.

**Blocked by:** 07 (`POST /check` + `/health` for MD5)

**Status:** ready-for-agent

- [ ] Each successful **Lookup Session** writes exactly one **Audit Entry**.
- [ ] An **Audit Entry** records timestamp, caller identifier, **Algorithm**, each **Digest**
      + per-item status, and the **Release** + applied **Delta releases** that answered.
- [ ] The **Audit Trail** is append-only and durable.
- [ ] Verified at Seam 1 by observing that the entry was produced after a session; the
      **Audit Trail** internals are not a separate seam.
- [ ] No authentication layer is added (interface remains public).

## Comments
