# Public interface with a full audit trail

nsrllookup's lookup interface is **public**: no authentication on `POST /check`. This
matches the existing behaviour (the published `cybagard/nsrllookup-*` docker images expose
`/check` unauthenticated) and keeps the tool trivial to deploy.

Because the interface is open but every result already carries full provenance, the service
is made forensically safe not by access control but by **auditing**: every Lookup Session is
recorded — who/when (timestamp + an identifying field, even if a fixed service id for now),
the algorithm, each digest, and the Release + deltas that answered. The audit trail is the
forensic guarantee that openness otherwise leaves out.

- **Status**: accepted
- **Considered Options**: token-gated access (rejected for now: no consumer requirement and it
  adds operational surface a public utility shouldn't carry by default — remains an
  easy toggle later); no audit trail (rejected: an open forensic service with no record of
  what was asked is not reproducible and defeats the provenance we already record per
  result).
- **Consequences**: every successful Lookup Session writes an audit record as part of ticket
  04; the audit store must be durable and tamper-evident even though the interface is open;
  "add auth" is a tracked, unblocked follow-up, not a prerequisite.
