# 12: Log request-level rejections as Audit Entries

**What to build:** a request rejected at the request level (unsupported **Algorithm** or a
structurally malformed body) is also recorded in the **Audit Trail** — a forensic record of
a bad request is worth keeping, even though it produced no **Lookup Result** list.

**Blocked by:** 09 (Record an Audit Entry for every Lookup Session)

**Status:** ready-for-agent

- [ ] A bad-**Algorithm** rejection is recorded as an **Audit Entry**.
- [ ] A malformed-body rejection is recorded as an **Audit Entry**.
- [ ] The recorded entry for a rejection notes that no **Lookup Result** list was produced.
- [ ] Verified at Seam 1 by observing that a rejected request still produced an entry.

## Comments
