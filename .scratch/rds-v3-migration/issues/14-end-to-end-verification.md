# 14: End-to-end verification

**What to build:** run the full composed stack against a realistic Minimal **Set** and
confirm every slice holds together as a whole — a closing verification, not a feature.

**Blocked by:** 03 (CI test job), 08 (Widen lookup + API to SHA-1 & SHA-256),
12 (Log request-level rejections as Audit Entries), 13 (Retire `nsrlsvr`, old `GET /check`, two-service compose/README)

**Status:** resolved

- [x] All three **Algorithms** (MD5, SHA-1, SHA-256) answer **Known/Unknown/Invalid** with
      full provenance against a realistic Minimal **Set**.
- [x] A **Delta** has been applied; `/health` reports the refreshed **Release** + **Delta
      release(s)**; lookups reflect the updated **Hash Set**.
- [x] The **Audit Trail** is populated, including request-level rejections.
- [x] CI is green after `nsrlsvr` retirement.
- [x] No retired component or old response shape is reachable.

## Comments

`api/tests/integration/test_end_to_end.py` composes the whole flow on a realistic fixture:
provision a Minimal **Set** → apply a **Delta** on top (refreshed provenance) → all three
**Algorithms** answer `known` with full provenance via `POST /check` and `/health`; the
**Audit Trail** holds both a successful and a rejected (bad-algorithm) **Audit Entry**; and
the retired `GET /check/<hash>` route returns 404. Verified in the devcontainer with the
exact CI invocation `pytest --cov=. --cov-report=term-missing --cov-report=xml` → 38 passed,
0 skipped, 98% coverage, exit 0; `svr/`, `nsrllookup.py`, the old GET route, and the old
response shape are all gone.
