# 01 — Learn the on-disk V3 layout

Status: resolved — confirmed by `rds-v3-migration/04` + `rds-v3-live/01` (commit `3ba267c`)
Type: research
Blocked by: none

Determine the exact on-disk format of an RDS V3 release so ticket 03 can parse it. The
set is ~132 GB (`RDS_2026.03.1_modern.zip`), so do not unpack the whole thing in
session: inspect just enough (the zip manifest / a sample slice / the
`RDSv3_Docs/RDSv3.pdf`, dated 2023) to characterise the layout — file(s), record format,
hash-algorithm columns, and how a digest is looked up.

Confirm against the live release before building the parser. The V2 `NSRLFile.txt`/
`nsrlupdate` path is superseded and must not be reused.

## Comments
