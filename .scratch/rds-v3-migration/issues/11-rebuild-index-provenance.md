# 11: Rebuild index + refresh `/health` provenance after a Delta

**What to build:** after a **Delta** is applied, the per-Algorithm **hash→known index** is
rebuilt and `/health` reports the refreshed provenance, so lookups stay fast and the
reported **Release** + **Delta releases** always reflect the data that answered.

**Blocked by:** 10 (Apply a Delta release at ingest)

**Status:** ready-for-agent

- [ ] Applying a **Delta** rebuilds the per-Algorithm **hash→known index** (not per request).
- [ ] `/health` reports the refreshed **Release** + applied **Delta releases** after a
      **Delta** is applied.
- [ ] Lookup answers reflect the **Delta**-updated **Hash Set**.
- [ ] A smoke check confirms a small minimal DB + a sample **Delta** yields a queryable,
      indexed **Hash Set** with the expected **Known/Unknown** outcomes.

## Comments
