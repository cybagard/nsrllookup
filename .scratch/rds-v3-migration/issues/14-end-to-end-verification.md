# 14: End-to-end verification

**What to build:** run the full composed stack against a realistic Minimal **Set** and
confirm every slice holds together as a whole — a closing verification, not a feature.

**Blocked by:** 03 (CI test job), 08 (Widen lookup + API to SHA-1 & SHA-256),
12 (Log request-level rejections as Audit Entries), 13 (Retire `nsrlsvr`, old `GET /check`, two-service compose/README)

**Status:** ready-for-agent

- [ ] All three **Algorithms** (MD5, SHA-1, SHA-256) answer **Known/Unknown/Invalid** with
      full provenance against a realistic Minimal **Set**.
- [ ] A **Delta** has been applied; `/health` reports the refreshed **Release** + **Delta
      release(s)**; lookups reflect the updated **Hash Set**.
- [ ] The **Audit Trail** is populated, including request-level rejections.
- [ ] CI is green after `nsrlsvr` retirement.
- [ ] No retired component or old response shape is reachable.

## Comments
