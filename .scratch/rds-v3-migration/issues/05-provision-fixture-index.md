# 05: Provision a fixture Minimal Set + per-Algorithm index at ingest (MD5)

**What to build:** the data layer for the first algorithm. A fixture Minimal **Set** can be
provisioned into a queryable **Hash Set**, and a per-Algorithm **hash→known index** is built
at ingest (one index per supported **Algorithm**), because V3 stores digests UPPERCASE with
no standalone hash index. Scope: **MD5** — the data half of the first tracer bullet.

**Blocked by:** 01 (Modern stack & runtime), 04 (Confirm the RDS V3 on-disk layout)

**Status:** ready-for-agent

- [ ] A fixture Minimal **Set** loads as a queryable **Hash Set**.
- [ ] A per-Algorithm **hash→known index** (MD5) is built at ingest, not per request.
- [ ] A **Known** digest, an **Unknown** digest, and an **Invalid** value are distinguishable
      at the data layer for MD5.
- [ ] A smoke check confirms a small minimal-style DB builds a queryable, indexed **Hash Set**.
- [ ] **CRC-32** is present in the data but is *not* exposed as a supported lookup
      **Algorithm**.

## Comments
