# 11: Rebuild index + refresh `/health` provenance after a Delta

**What to build:** after a **Delta** is applied, the per-Algorithm **hash→known index** is
rebuilt and `/health` reports the refreshed provenance, so lookups stay fast and the
reported **Release** + **Delta releases** always reflect the data that answered.

**Blocked by:** 10 (Apply a Delta release at ingest)

**Status:** resolved

- [x] Applying a **Delta** rebuilds the per-Algorithm **hash→known index** (not per request).
- [x] `/health` reports the refreshed **Release** + applied **Delta releases** after a
       **Delta** is applied.
- [x] Lookup answers reflect the **Delta**-updated **Hash Set**.
- [x] A smoke check confirms a small minimal DB + a sample **Delta** yields a queryable,
      indexed **Hash Set** with the expected **Known/Unknown** outcomes.

## Comments

`apply_delta` (ticket 10) rebuilds the index in `HashSet.__init__` over the merged db,
so the new **Hash Set** is queryable and correct on every algorithm. `api/tests/test_
apply_delta.py` `test_apply_delta_refreshes_provenance` + `test_health_reports_refreshed_
provenance` confirm the refreshed provenance and that `/health` reports it; delta rows are
Known after the apply and absent on the base. No per-request reconstruction.
