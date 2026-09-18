# 02 — Provision the RDS into a mounted volume

Status: resolved — succeeded by `rds-v3-live/05` + turnkey driver (commit `5671832`, `3556c3e`)
Type: task
Blocked by: none

Supersede `svr/prepare-hash-set.sh` (download + `nsrlupdate`), which is dead: the V2 URL
403s and the V2 flat file is retired. Provision NIST's **Minimal** RDS V3 set into a
mounted, read-only volume that nsrllookup queries, and keep it current by applying
**Delta releases** on top of the full March Release. NIST publishes quarterly — full
Release in March, deltas in June/Sep/Dec — so this provisions a full Release then layers
deltas; **do not** download the 124 GB full set, and **do not** download or index it in a
build or CI step. Record the current dataset identity — the **Release** date-version and
which **Delta releases** are applied (e.g. `release: 2026.03.1`, `deltas: [2026.06.1]`)
plus an ingest timestamp — so ticket 04 can surface it in every Lookup Result and the
consumer knows exactly what it is checking against.

## Comments
