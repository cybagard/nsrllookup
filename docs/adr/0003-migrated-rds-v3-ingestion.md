# Migrate to NIST RDS V3, provisioned as a mounted volume

NIST has retired the V2 `rds_modernm.zip`/`NSRLFile.txt` ingest path (the URL now 403s)
and publishes the Reference Data Set as versioned RDS V3 releases — SQLite databases —
e.g. `RDS_2026.03.1_modern.zip`. NIST publishes quarterly: a full **Release** in March,
**Delta releases** in June/September/December that apply against the prior full Release.
The full Modern set is ~124 GB; the **Minimal** set is ~18 GB. We provision the **Minimal
set** into a mounted, read-only volume and keep it current by applying Delta releases,
rather than downloading the full 124 GB, and not at build or CI time.

- **Status**: accepted
- **Considered Options**: keep downloading the V2 URL (rejected: dead, retired format);
  download the full 124 GB full set to a volume (rejected: it's the minimal set that fits,
  and deltas keep it current — the full set is unnecessary weight); download+index at build
  time (rejected: a 18 GB set plus deltas does not belong in a build or CI step); supply
  the set out-of-band per deployment (rejected: no reproducibility for forensics).
- **Consequences**: `svr/prepare-hash-set.sh` (the download+`nsrlupdate` step) is
  superseded by a minimal-set + delta volume-provisioning step; the current dataset must be
  identified (Release + which deltas applied) so it can be surfaced in every Lookup
  Result; the set's exact on-disk V3 layout is learned from the release before we can parse
  it (tracked as a learn ticket).
