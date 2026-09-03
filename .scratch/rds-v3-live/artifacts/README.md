# RDS V3 artifacts

Drop NIST's **real** RDS V3 distribution artifacts here so the `rds-v3-live`
effort can be validated against them. The NIST S3 bucket
(`s3.amazonaws.com/rds.nsrl.nist.gov/RDS/`) is currently `AccessDenied` for
anonymous GET, so these are staged off-network.

## Why

Ticket `01` (`.scratch/rds-v3-live/issues/01-confirm-real-schema.md`) must
**byte-confirm** NIST's real Minimal `FILE`/`DISTINCT_HASH` schema from NIST's
shipped `schema.sql`. It was designed against the ~206 MiB
`RDS_2026.03.1_modern_minimal_delta.zip`, which ships `schema.sql` +
`signatures.txt` + `..._delta.sql` + `readme.txt`.

## What to drop and where

**Required to close ticket `01`** — drop into `extracted/` (unzipped is fine):

- `extracted/schema.sql` — **the authoritative schema** (the whole point of 01)
- `extracted/signatures.txt` — inner SHA-256 manifest (corroborates 01; needed by 05)
- `extracted/RDS_2026.03.1_modern_minimal_delta.sql` — the real delta `.sql`

**Needed later (tickets 05-06), cheap, drop when you have them:**

- `extracted/version.txt`
- `extracted/dbhashes.txt`
- `extracted/hash_counts.txt`
- `extracted/readme.txt`

**Optional, heavy (gitignored — kept on disk, not committed):**

- `raw/RDS_2026.03.1_modern_minimal_delta.zip` (the zip you unzipped)
- `raw/RDS_2026.03.1_modern_minimal_delta.zip_sha` (its SHA-1 sidecar)
- `raw/RDS_2021.12.2_curated.zip` (~86.9 MiB curated db, for the 07 mechanics smoke)

## Layout

```
artifacts/
  README.md            # this file (committed)
  .gitignore           # keeps *.zip *.db *.sha *.bin out of git; keeps text in
  raw/                 # heavy binaries: zips + their .sha sidecars (gitignored)
  extracted/           # unzipped + downloaded text evidence (committed)
```

## How I'll use it

- `schema.sql` → recorded verbatim in ticket `01`'s `Answer` section (citation).
- `signatures.txt` / `dbhashes.txt` → integrity layers for tickets 05-06.
- the `..._delta.sql` → the real delta shape for tickets 04 / 07.

The 18 GiB full Minimal set and the production deploy stay operator steps and
are not staged here.
