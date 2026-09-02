# 05: Provision a fixture Minimal Set + per-Algorithm index at ingest (MD5)

**What to build:** the data layer for the first algorithm. A fixture Minimal **Set** can be
provisioned into a queryable **Hash Set**, and a per-Algorithm **hash→known index** is built
at ingest (one index per supported **Algorithm**), because V3 stores digests UPPERCASE with
no standalone hash index. Scope: **MD5** — the data half of the first tracer bullet.

**Blocked by:** 01 (Modern stack & runtime), 04 (Confirm the RDS V3 on-disk layout)

**Status:** resolved

- [x] A fixture Minimal **Set** loads as a queryable **Hash Set**.
- [x] A per-Algorithm **hash→known index** (MD5) is built at ingest, not per request.
- [x] A **Known** digest, an **Unknown** digest, and an **Invalid** value are distinguishable
      at the data layer for MD5.
- [x] A smoke check confirms a small minimal-style DB builds a queryable, indexed **Hash Set**.
- [x] **CRC-32** is present in the data but is *not* exposed as a supported lookup
        **Algorithm**.

## Comments

Delivered in `api/hasheset.py`: `Provenance` (Set / Release / applied Deltas), the
`HashSet` (per-algorithm `hash→known` index built once via `provision()`, not per
request), and `is_known(algorithm, digest)`. Verified at the data layer by
`api/tests/test_hasheset_layout.py` (smoke check: a tiny minimal-style DB is
queryable, distinguishable known/unknown, CRC-32 physically present but not a
supported algorithm). Index built at ingest, confirmed by `provision()` opening
the SQLite db a single time.
