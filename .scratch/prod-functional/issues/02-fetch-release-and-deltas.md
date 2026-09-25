# 02: Fetch the Release and Delta releases from NIST

**What to build:** the turnkey **Provisioner** driver gains the **fetch** stage: it pulls the
full **Release** zip plus its ordered **Delta release** zips — each with its `.sha` sidecar —
plus the **terminal release's** `dbhashes.txt`, from NIST's distribution, ahead of any
verify/apply/write. (There is no top-level `signatures.txt` on NIST — live probes 403, and the
release README lists the top-level objects without one; each archive carries its *inner*
`signatures.txt`, which the signature layer verifies from the extracted tree — so the turnkey
path fetches the terminal release's `dbhashes.txt` as its single per-Release text object.) NIST distributes RDS V3 from a per-**Release** S3 path whose listing is
**access-denied** but whose individual objects are **public-read**, so the fetch **probes
exact object names** derived from the **Release** and **Delta release** identifiers rather
than listing the bucket. This is the slice that makes "bring a fresh box online" start
without hand-assembling the download list. The multi-gigabyte fetch is the operator's step
and is never a build or CI step (ADR-0003); this ticket wires *where the driver fetches from*,
not the heavy download itself. No new dependency.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] The driver fetches the full-Minimal **Release** zip + `.sha` sidecar and each ordered
         **Delta release** zip + sidecar, plus the **terminal release's** `dbhashes.txt`, by
         exact object names on NIST's per-Release path (there is no top-level `signatures.txt`
         to fetch: each archive carries its inner one, verified from the extracted tree).
- [x] Object names are derived from the **Release** and **Delta release** identifiers, not
        hard-coded URLs.
- [x] A failed or missing object surfaces clearly (no silent empty fetch).
- [x] No new third-party dependency is introduced; the fetch reuses stdlib.
- [x] The heavy multi-GB download is documented as the operator's step, out of CI (ADR-0003).

## Comments

- 2026-09-21 (ADR-0007): the fetch gained *resume* — `_download` trusts an object
  already complete on disk (a failed fetch leaves nothing behind, so an existing
  target is complete by construction; a corrupt pre-place is caught by layers 1–2
  before anything else runs). The resolved contract is unchanged (a *missing*
  object is still probed and refuses loudly); a re-run simply stops re-copying
  the 18.8 GiB archive. Exercised for real by the uncapped ticket-04 run, where
  all seven objects resumed from the operator's `raw/` set.
