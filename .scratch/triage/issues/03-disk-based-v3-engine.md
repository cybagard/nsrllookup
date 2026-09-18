# 03 — Query the RDS V3 (SQLite) directly, with a hash index

Status: resolved — SQLite engine + in-db index landed in `rds-v3-live/03` (commit `36c0350`, `0af05af`)
Type: task
Blocked by: 01

Query the mounted RDS V3 **SQLite** database directly and retire `nsrlsvr` + the socket
protocol in `api/nsrllookup.py` (ADR-0001). No separate daemon: the engine is "open the
`.db`, run a query". V3 stores digests **UPPERCASE** with **no standalone hash index**, so
a `WHERE md5 = '…'` over ~940 M rows is a full scan — build a **hash→known index at
ingest** (one sidecar index per supported Algorithm, rebuilt when a Delta release is
applied per ticket 02) so lookups are fast. Must answer per-algorithm for **MD5, SHA-1,
SHA-256** (the `Lookup Result` contract in ticket 04). **CRC-32** is present in every row
but is **not** a supported lookup. This makes the `svr/` service and the `nsrlsvr` fork
pin (`svr/Dockerfile:6`) obsolete — retire them in ticket 07.

## Comments
