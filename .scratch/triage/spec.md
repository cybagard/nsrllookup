# Triage: bring nsrllookup current

Triage of `cybagard/nsrllookup` for "make the project current" + "the NSRL side has
updates". Decided 2026-08-21, locked in `.scratch/triage/`.

## Decisions (locked)

- **Dataset**: migrate to NIST **RDS V3** — SQLite databases (V2 `rds_modernm.zip` is
  dead/retired; the URL now 403s). Serve the NIST **Minimal** set (~18 GB, e.g.
  `RDS_2026.03.1_modern`), keep it current by applying quarterly **Delta releases**, not
  the 124 GB full set. Provisioned into a mounted read-only volume, not a build/CI step.
  See ADR-0003.
- **Algorithms**: lookup is per-algorithm for **MD5, SHA-1, SHA-256** — all first-class.
  RDS V3 physically carries CRC-32 too, but it is **not** a supported lookup.
- **Engine**: query the **SQLite** database directly; **retire `nsrlsvr`** + the
  `nsrllookup.py` socket protocol. Build a **hash→known index at ingest** (per algorithm),
  because V3 stores digests uppercase with no standalone hash index. Serve the minimal
  set, not the full download. See ADR-0001.
- **API surface**: **`POST /check`**, one request = **one algorithm** + one-or-more
  digests; each result carries **full provenance** — digest, algorithm,
   `known`/`unknown`, **Set**, **Release**, applied **deltas**. Accept any case, normalize
  to uppercase internally. See ADR-0002.
- **Error semantics**: a well-formed **`POST /check`** returns **HTTP 200** even when some
  digests don't parse; each unparseable digest is a per-item `invalid` in the result list.
  Bad algorithm / malformed body is a request-level 4xx.
- **Access & audit**: lookup interface is **public / no auth**; every session is recorded
  in an append-only, durable **Audit Trail** (the forensic guarantee for an open
  interface). See ADR-0004.
- **Stack**: full modern bump — **Python 3.12, Flask 3, waitress 3, pytest +
  pytest-cov**; drop `nose`/`nosetests`, drop `Paste`/`TransLogger`.
- **Ingestion**: set is **provisioned once into a mounted volume**, kept current by
  deltas; never downloaded in build/CI.
- **Domain docs**: written/updated this session (`CONTEXT.md`, `docs/adr/0001..4`).

## Work items (issues/)

| # | Ticket | Blocked by |
|---|--------|-----------|
| 01 | Learn the on-disk V3 (SQLite) layout for the minimal set | — |
| 02 | Provision the Minimal set + apply deltas into a mounted read-only volume (successor to `svr/prepare-hash-set.sh`) | — |
| 03 | Query RDS V3 SQLite directly + per-algorithm hash index (retire `nsrlsvr` + `nsrllookup.py`) | 01 |
| 04 | `POST /check` multi-algorithm API + full-provenance results + `/health` + 200/per-item-invalid semantics | 03 |
| 05 | Modern dependency stack (Python 3.12, Flask 3, waitress 3, drop nose/Paste) | — |
| 06 | pytest suite + CI test job; drop `version:"3"`; tag images by minor | 05 |
| 07 | Retire `svr/` service + socket protocol; update README + compose | 03, 04 |
| 08 | Audit trail for every lookup (public-but-fully-audited, per ADR-0004) | 04 |

## Open / not resolvable here

- **V3 in-zip layout** (ticket 01): the public `RDSv3_Docs/RDSv3.pdf` exists but we will
   not unpack a 18 GB minimal / 124 GB full archive in-session. Schema is known from the
   PDF (SQLite; `METADATA` table with crc32/md5/sha1/sha256; uppercase digests; no
  standalone hash index); full on-disk confirmation is against a release at implementation
  time.
