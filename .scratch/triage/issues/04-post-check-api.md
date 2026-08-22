# 04 — POST /check multi-algorithm API + full provenance

Status: open
Type: task
Blocked by: 03

Replace `GET /check/<hash>` (`api/app.py:24`) with `POST /check` (ADR-0002). One request
carries **one Algorithm** (MD5, SHA-1, or SHA-256) and one or more digests; it returns
one `Lookup Result` per digest. Each result carries **full provenance**: the digest, its
algorithm, the `known`/`unknown` status, the **Set** consulted, the **Release** date-
version, and which **Delta releases** were applied. **CRC-32** is not an accepted lookup
algorithm. Replace the MD5-only 32-hex regex (`api/app.py:26`) with per-algorithm
validation; accept lowercase/mixed-case input and **normalize to uppercase** internally
(V3 stores digests uppercase — matches the old `/check` tolerance and the existing
upper/lower test variants). Add a `/health` endpoint exposing the current Release and
applied Deltas. The old `{result: "true|false|invalid hash format"}` shape is a
deliberate, breaking change.

**Error semantics (locked):** a structurally well-formed request returns **HTTP 200** even
if some digests don't parse; each unparseable digest is returned as a per-item
`invalid` status inside the result list (alongside `known`/`unknown`), so a batch never
fails wholesale on one bad item. A request with an unsupported algorithm or a structurally
malformed body is a request-level rejection (4xx, no result list). Access is **public /
no auth** (ADR-0004). **Every** Lookup Session writes an audit record (digests, algorithm,
timestamp, and the Release + deltas that answered) via ticket 08.

## Comments
