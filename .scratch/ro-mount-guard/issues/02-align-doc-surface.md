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

**Status:** resolved

- [x] `CONTEXT.md`'s **Hash index** term states the real shape: the in-db per-Algorithm
       B-tree **is** the membership index, not a sidecar. The ticket's literal "drop the
       quoted phrase from the `_Avoid_` list" is the one instruction deliberately not
       taken — the phrase is retained, correctly worded as an *avoid*, and is the
       signpost for the retained historical records that still use "sidecar" (Answer).
- [x] `notes.md`'s "one sidecar index per supported Algorithm, queried by indexed seek"
       is corrected to the in-db per-Algorithm **hash index** (rebuilt on **Delta**
       apply) — landed in `7ec7428`; the quoted phrase no longer occurs anywhere in the
       repo.
- [x] The living prose still states the ADR-0006 shape: the service trusts the verified
       mount and does not rebuild the index at boot or `verify` — verified on `main`:
       `CONTEXT.md:44,138-139`, `notes.md:59-63`, `README.md:19-28,34-38,43-49`.
- [x] No living surface (`CONTEXT.md`, `README.md`, `notes.md`) describes boot/verify as
       rebuilding the index or shipping a sidecar (the only surviving "sidecar" mentions
       are the *release-zip* SHA-1 integrity file); historical `.scratch`/`docs` records
       are left intact — this close-out changes none of them.

## Notes

- Scope is prose-only; the code change is 01. This ticket is the alignment pass that lands
  after 01 so the description matches what shipped.

## Answer

Most of this ticket was overtaken by events: the living prose was already aligned in
`7ec7428` ("Docs + proofs: in-db index / streamed apply / trust-the-mount"), which landed
with the source fix `0af05af` — before the 01 guards (`b1cf24b`) merged (`8a89389`).
This close-out is a verification pass against `main` plus one scope call; it changes no
living doc, only this ticket file.

**Overtaken, verified.** `7ec7428` rewrote the **Hash index** body to the shipped
invariant — per-Algorithm B-tree `CREATE INDEX` "built **inside the Hash Set's own
`.db`**, not a separate on-disk artifact", rebuilt "when a **Delta release** is applied"
(i.e. by the **Provisioner** / **Delta** apply paths, never boot/verify) — and the
"one sidecar index per supported Algorithm, queried by indexed seek" the preamble quotes
no longer occurs anywhere in the repo: a whole-repo sweep for both preamble phrases
returns a single hit, the `_Avoid_` occurrence handled below. The ADR-0006 shape stands
in all three living surfaces: `CONTEXT.md:44` (loads the Hash Set read-only) and
`CONTEXT.md:138-139` (trusts the verified mount, not a recomputed dbhash — see ADR-0006),
`notes.md:59-63` (single `mode=ro` connection; boot/verify "does not rebuild the index;
the **Provisioner** and **Delta** apply are the only writable paths"), and
`README.md` (mounted read-only; the per-Algorithm **hash index** built into the same
`.db` at provisioning; "the container trusts the verified mount and does not recompute
**dbhash** at boot"; provisioning is one-time). The block on 01 — that the prose
describe the *shipped* invariant, not the pre-01 one — is satisfied: the source fix and
its guards are both on `main`, and the prose describes exactly that state.

**One scope call: the `_Avoid_` phrase is retained, not dropped.** The only literal delta
left to the checklist was dropping "an on-disk sidecar copy of `DISTINCT_HASH`" from the
**Hash index** term's `_Avoid_` list. Not taken, for three reasons: (1) under the
glossary convention `_Avoid_` is the term's *negative* list — the item reads "the index
is **not** a sidecar copy of DISTINCT_HASH", which is true of the shipped in-db B-tree,
and it sits beside "the mounted database itself", which likewise names a live thing, not
a dead one; (2) the retained historical records — which item 4 of this very ticket keeps
intact — still use "sidecar" for the superseded design, and the `_Avoid_` item is what
keeps a reader of those records from re-importing the old shape; (3) the ticket's stated
goal — a reader of the domain docs meets the real invariant, not the old one — is met by
`7ec7428`'s body rewrite, and the surviving item is the disambiguator that makes it
stick.

**No sidecar, no rebuild, on the living surface.** The only other "sidecar" mentions in
the three living docs (`CONTEXT.md:127`; `README.md:40`) are the *release-zip* SHA-1
integrity file NIST ships beside each release — a live, different concept, not a hash
index (the manifest / readiness-gate passages name the same three integrity layers
without the word). The only "rebuild" mentions are the Delta-apply rebuild
(`CONTEXT.md:72-73`) and the explicit boot/verify negative (`notes.md:61-62`).
Historical `.scratch` tickets, ADRs, and `docs/` records are untouched.
