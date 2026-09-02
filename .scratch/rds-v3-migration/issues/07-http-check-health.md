# 07: `POST /check` + `/health` for MD5 (first tracer bullet)

**What to build:** the first complete end-to-end tracer bullet through the HTTP layer
(Seam 1). `POST /check` serves one **Algorithm** per request (scope: **MD5**) with
per-item **Lookup Results**, and `/health` reports the loaded **Release** + applied
**Delta releases** and a ready flag. Driven through the application's HTTP/WSGI test client.

Request/response shape and the authoritative **Lookup Result** schema live in
`.scratch/rds-v3-migration/spec.md` (Implementation Decisions → API contract / response).
Build to that schema; do not re-paste it here.

**Blocked by:** 06 (`look_up` module + full provenance for MD5)

**Status:** resolved

- [x] `POST /check` accepts one **Algorithm** + one-or-more digests and returns one
        **Lookup Result** per digest.
- [x] A structurally well-formed request returns **HTTP 200** even when some digests don't
      parse; each unparseable digest is a per-item **Invalid** in the results list.
- [x] A request naming an unsupported **Algorithm**, or a structurally malformed body, is a
      request-level rejection (**4xx**, no results list).
- [x] Digits are accepted in any case and normalised to UPPERCASE before lookup.
- [x] `/health` reports the loaded **Release** + applied **Delta releases** and a ready flag
        (not-ready when no **Hash Set** is provisioned).
- [x] Tests drive this behaviour through the HTTP test client (Seam 1).

## Comments

Delivered in `api/app.py`: `POST /check` (one **Algorithm** + one-or-more **Digests**,
delegating to `lookup.look_up`) and `/health` (`ready` + `dataset`), with `configure()`
installing the provisioned **Hash Set** (503 / not-ready when unprovisioned). Unsupported
**Algorithm** and malformed body are request-level 4xx with no `results` list; per-item
**Invalid** returns 200. Drive through the HTTP test client in
`api/tests/integration/test_check_health.py` (seam 1). The retired MD5-only
`GET /check/<hash>` is kept behind an on-demand `nsrllookup` import (removed in ticket 13)
so `from app import api` stays boot-safe.
