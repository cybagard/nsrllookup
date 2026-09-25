# Streaming statement scanner for Delta `.sql` files

A Delta release is one SQLite script -- `BEGIN TRANSACTION; …3.8 M INSERTs…
COMMIT;`, up to ~1 GB. Two constraints collide: NIST ships it as a single file
(`executescript`'s documented `.read` mechanism), but that file is far too
large to read whole -- it exceeds the script-size limit and the memory budget
(ADR-0001: nothing dataset-scale in RAM; ADR-0003: no multi-GB work in a
build step; ADR-0007: the turnkey run fits a small machine, measured 126 MiB
peak RSS). And it cannot be split naively: the real deltas carry raw `CR`
bytes inside quoted `file_name` values (a text-mode reader would translate
each to a line break and split one `INSERT` in two), quote/comment tokens
occur inside strings and comments, a stale AppleDouble metadata twin was once
served in place of the real script by a crashed run's scratch, and a
corrupt or never-terminated statement must fail loudly, not vanish.

**Decision**: `hasheset` applies a Delta through a small stateful scanner
(`_scan` with `_scan_text`/`_scan_stream` front-ends, `_apply_sql_stream`
runner). A five-state lexer (code, single-quote, double-quote, line comment,
block comment) splits at code-level semicolons only, so `;`, quotes, and
comment openers inside strings and comments never split a statement. The
stream path reads the file in 1 MiB binary chunks (UTF-8 incremental decode,
CRs preserved verbatim -- no newline translation) and unconditionally
re-bases its live buffer to the in-flight statement (or, inside a quote or
comment, to the scanner position), so a token split by *any* read boundary
reassembles byte-identically: a Delta applies identically no matter how the
bytes arrive (the chunk-invariance sweep is tested at every size 1..N). The
live buffer is capped at 16 MiB per in-flight statement; crossing the cap is
a loud `ValueError`. The runner batches execution (skip the wrapper
`BEGIN`/`COMMIT`, self-managed transactions, commit every 100 K statements)
and refuses any statement that cannot begin with a SQL keyword, so the
metadata-twin class fails in milliseconds. Text and stream front-ends share
one scanner core, so `_apply_delta` on a path and on equivalent text yield
identical statement cuts.

**RAM bound, reconciled**: ADR-0001 rejects dataset-scale in-RAM objects
(the 18 GB set, the ~430 M×3 digest set -- the OOM that killed the old
design). The scanner's 16 MiB per-statement ceiling is 10× the
megabyte-class bound and is *deliberately accepted*: real NIST statements
are one line, a few hundred bytes; the cap exists as a runaway/corruption
detector, not a legitimate size -- only a file that never terminates can
reach it -- and the steady working set stays one 1 MiB chunk plus one
in-flight statement. The docstring citation "no multi-megabyte object in
RAM at once" belongs to this ADR, not ADR-0003 (which governs the operator
fetch, not in-process memory).

- **Status**: accepted
- **Considered Options**: `executescript` on the whole file (rejected:
  script-size limit + the GB-class RAM it holds); naive `splitlines`
  (rejected: `CR`-in-string splits real `INSERT`s -- observed, not
  hypothetical); read the whole file then regex-split in memory (rejected:
  GB-class, ADR-0001/0007); an external `sqlite3` CLI (rejected: a
  non-stdlib dependency for a splitting job this codebase must own); a
  full SQL parser (rejected: a five-state splitter is sufficient -- full
  parsing is the executor's job, and the loud guards below catch what the
  splitter lets through).
- **Consequences**: `_apply_delta` accepts a `.sql` path or text with
  identical behaviour; an unterminated statement at the stream's end is
  emitted and then refused loudly by the executor or the junk guard, never
  silently dropped; a Delta whose in-flight statement exceeds 16 MiB fails
  fast with a clear message; the mechanism is regression-tested (chunk
  invariance sweeps, closer/quote/`CR` boundary straddles, oversized
  refusal, text/stream parity, trailing-comment and dangling-fragment
  cases) and was validated by the real-data turnkey proof, whose measured
  transcript (`realdata_turnkey_proof` output) records 126 MiB peak RSS
  across both real Delta applies (prod-functional ticket 04).
