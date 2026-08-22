# 07 — Retire svr/ + update README/compose

Status: open
Type: task
Blocked by: 03, 04

Once the SQLite engine (03) and `POST /check` (04) exist, remove the `svr/` service
(`svr/Dockerfile`, `svr/docker-entrypoint.sh`, the `cybagard/nsrlsvr` fork pin at
`svr/Dockerfile:6`, and `svr/prepare-hash-set.sh`) and the `nsrllookup.py` socket client.
Rewrite the README's two-service "prepare the environment / run svr then api" flow into the
new single-service + minimal-set-with-deltas mounted-volume model (ticket 02), and trim the
compose files to match.

## Comments
