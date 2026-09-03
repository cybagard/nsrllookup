# 02: Domain model + ADR-0005 / ADR-0006 (prefactor)

**What to build:** the decided model, written down before the implementation chain that must
respect it. **`CONTEXT.md`** (single context, glossary only, implementation-free) gains /
sharpens the terms the re-base changes: the real **Set schema** (`FILE`/`DISTINCT_HASH`,
`crc32` a column), the **Sidecar index** (persisted, distinct-digest, invalidatable on
delta), the **Provisioner** + **Provisioning manifest** (the integrity attestation),
**`dbhash`** (NIST's dataset-integrity token), and **`Delta release`** sharpened to "a
`.sql` of INSERT/UPDATE/DELETE applied in order." Two decisions that are hard-to-reverse,
surprising, and the result of a real trade-off get ADRs: **ADR-0005** (the **Provisioning
manifest** as the integrity token / readiness gate) and **ADR-0006** (accepting NIST's
external **`dbhash`** dependency; the container trusts the verified mount). This is the
"make the change easy" prefactor — the implementation tickets below cite these terms and
ADRs.

**Blocked by:** 01 (confirm the real schema) — the terms describe the layout `01` records.

**Status:** resolved

- [x] `CONTEXT.md` carries the real **Set schema**, **Sidecar index**, **Provisioner** +
         **Provisioning manifest**, **`dbhash`**, and the sharpened **Delta release**; it
        remains implementation-free.
- [x] **ADR-0005** (manifest = integrity token / readiness gate) is written and accepted,
        recording the decision and its alternatives.
- [x] **ADR-0006** (external `dbhash` / trust-the-mount) is written and accepted.
- [x] The re-based implementation tickets (03–08) cite these terms and ADRs; no term is
        introduced in code that is not already in `CONTEXT.md`.

## Answer

`CONTEXT.md` gained/sharpened, implementation-free: **Set schema** (`FILE`/`DISTINCT_HASH`,
`crc32` a column, refuting `METADATA`/`md5sha1`/`filename`), **Sidecar index**, **dbhash**,
the **Provisioner** + **Provisioning manifest** (new "Provisioning" group under *The
service*), and the sharpened **Delta release** (`.sql` of `INSERT/UPDATE/DELETE` in order);
**Lookup Result** and **Audit Entry** now carry the final **dbhash**. **ADR-0005**
(`docs/adr/0005-provisioning-manifest-integrity-token.md`, accepted) records the manifest as
the integrity token / readiness gate; **ADR-0006**
(`docs/adr/0006-external-dbhash-trust-the-mount.md`, accepted) records accepting NIST's
external `dbhash` dependency and trusting the verified mount. Tickets 03–08 cite the new
terms/ADRs (03 names **Set schema**; 04–07 name **Sidecar index**/**Provisioner**/
**Provisioning manifest**/**dbhash**; 05 cites ADR-0006, 06 cites ADR-0005).
