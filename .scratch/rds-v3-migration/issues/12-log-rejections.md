# 12: Log request-level rejections as Audit Entries

**What to build:** a request rejected at the request level (unsupported **Algorithm** or a
structurally malformed body) is also recorded in the **Audit Trail** — a forensic record of
a bad request is worth keeping, even though it produced no **Lookup Result** list.

**Blocked by:** 09 (Record an Audit Entry for every Lookup Session)

**Status:** resolved

- [x] A bad-**Algorithm** rejection is recorded as an **Audit Entry**.
- [x] A malformed-body rejection is recorded as an **Audit Entry**.
- [x] The recorded entry for a rejection notes that no **Lookup Result** list was produced.
- [x] Verified at Seam 1 by observing that a rejected request still produced an entry.

## Comments

`api/app.py` already routes every request-level rejection (malformed body,
unsupported Algorithm, malformed hashes, unsupported set) through
`_record_session(..., results_produced=False)`, so each writes one **Audit
Entry** with `results: None`. `api/tests/integration/test_log_rejections.py`
observes, black-box at Seam 1, that a bad-algorithm and a malformed-body
rejection each produce exactly one entry noting no results were produced.
