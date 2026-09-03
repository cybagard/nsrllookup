# 07: Real-data mechanics smoke (one-off, out of CI)

**What to build:** two one-off, hand-run **real-data** validations that prove the re-based
reader against NIST's actual artifacts. They are **not** added to the automated suite (real
data I/O is multi-GB); they are performed and recorded.

   (a) **Byte-confirm the Minimal schema** from NIST's shipped `schema.sql` (the authoritative
   source for ticket 01; an independent re-check that ticket 03's shape matches NIST).
   (b) **Mechanics smoke** of reader + **delta apply** + **`dbhash`** against a small
    **real** NIST database that exists — `RDS_2021.12.2_curated` (~86.9 MiB). This is a
    *different* (curated) schema, so it is a **mechanics** proof — the `.sql` apply +
    `dbhash` + read path works on a real NIST db — **not** a Minimal-layout proof.

The full ~18 GiB Minimal **Set** and the production deploy remain **operator steps**, out of
this ticket.

**Blocked by:** 06 (manifest/readiness + `dbhash` surfacing) — the mechanics smoke exercises
the reader + delta + readiness + `dbhash` path end to end.

**Status:** ready-for-agent

- [ ] (a) The Minimal `FILE`/`DISTINCT_HASH` schema is byte-confirmed against NIST's shipped
         `schema.sql` and recorded.
- [ ] (b) The mechanics smoke runs reader + **delta apply** + **`dbhash`** verification
        against `RDS_2021.12.2_curated`, recorded as passing.
- [ ] Neither validation is added to the automated suite; both are one-off, recorded out of
        CI.
