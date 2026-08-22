# 07: `POST /check` + `/health` for MD5 (first tracer bullet)

**What to build:** the first complete end-to-end tracer bullet through the HTTP layer
(Seam 1). `POST /check` serves one **Algorithm** per request (scope: **MD5**) with
per-item **Lookup Results**, and `/health` reports the loaded **Release** + applied
**Delta releases** and a ready flag. Driven through the application's HTTP/WSGI test client.

Request/response shape and the authoritative **Lookup Result** schema live in
`.scratch/rds-v3-migration/spec.md` (Implementation Decisions → API contract / response).
Build to that schema; do not re-paste it here.

**Blocked by:** 06 (`look_up` module + full provenance for MD5)

**Status:** ready-for-agent

- [ ] `POST /check` accepts one **Algorithm** + one-or-more digests and returns one
      **Lookup Result** per digest.
- [ ] A structurally well-formed request returns **HTTP 200** even when some digests don't
      parse; each unparseable digest is a per-item **Invalid** in the results list.
- [ ] A request naming an unsupported **Algorithm**, or a structurally malformed body, is a
      request-level rejection (**4xx**, no results list).
- [ ] Digits are accepted in any case and normalised to UPPERCASE before lookup.
- [ ] `/health` reports the loaded **Release** + applied **Delta releases** and a ready flag
      (not-ready when no **Hash Set** is provisioned).
- [ ] Tests drive this behaviour through the HTTP test client (Seam 1).

## Comments
