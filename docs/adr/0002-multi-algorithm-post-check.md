# Multi-algorithm POST /check

The lookup is now per-algorithm (MD5, SHA-1, SHA-256), so the old MD5-only
`GET /check/<hash>` contract no longer carries the algorithm. We replace it with
`POST /check` taking a JSON body that names the `algorithm` and one or more `hash`es,
and each `Lookup Result` names its own `algorithm` plus the RDS `dataset_version`
consulted.

- **Status**: accepted
- **Considered Options**: algorithm in the path (`/check/sha256/<h>`) — rejected as it
  doesn't scale to batching; algorithm as a query param — rejected as less explicit for a
  forensic request; keep the bare `true/false` response — rejected because it hides which
  release answered, which forensics requires.
- **Consequences**: the response shape changes from
  `{"result": "true|false|invalid hash format"}` to one result per digest, each of form
  `{"digest", "algorithm", "known"/"unknown"/"invalid", "dataset_version"}` (a bare
  `status` field is optional). This is a deliberate, breaking change to the public
  contract; consumers must adopt the new shape.
