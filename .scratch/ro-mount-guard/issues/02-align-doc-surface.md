# 02: Align the doc surface with "the index lives in the db; the service trusts the mount"

**What to build:** the glossary and notes read the way the code now behaves. The
**Hash index** is an in-db per-Algorithm B-tree (ADR-0001), and the service is a
pure read-only consumer that trusts the verified mount (ADR-0006); a few prose surfaces
still describe the superseded shape ("an on-disk sidecar copy of DISTINCT_HASH", "one
sidecar index … queried by indexed seek"). After 01 ships, these are corrected so a reader
of the domain docs meets the real invariant, not the old one.

Historical `.scratch` tickets and ADRs are left as history (each describes its own time),
so the alignment is confined to the living domain surface: `CONTEXT.md` and `notes.md`. Any
new term or nuance is written into `CONTEXT.md` (which stays implementation-free).

**Blocked by:** 01 (so the prose describes the shipped invariant, not the pre-01 one)

**Status:** ready-for-agent

- [ ] `CONTEXT.md`'s **Hash index** term drops the stale "an on-disk sidecar copy of
       `DISTINCT_HASH`" from its `_Avoid_` list — the in-db B-tree **is** the membership
       index; the sidecar is the thing that's gone.
- [ ] `notes.md`'s "one sidecar index per supported Algorithm, queried by indexed seek"
       is corrected to the in-db per-Algorithm **hash index** (rebuilt on **Delta** apply).
- [ ] The living prose still states the ADR-0006 shape: the service trusts the verified
       mount and does not rebuild the index at boot or `verify`.
- [ ] No living surface (`CONTEXT.md`, `README.md`, `notes.md`) describes boot/verify as
       rebuilding the index or shipping a sidecar; historical `.scratch`/`docs` records are
       left intact.

## Notes

- Scope is prose-only; the code change is 01. This ticket is the alignment pass that lands
  after 01 so the description matches what shipped.
