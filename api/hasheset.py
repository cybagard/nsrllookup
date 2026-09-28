"""NIST RDS V3 real Minimal layout, fixture builder, and queryable Hash Set.

The data layer is re-based onto NIST's real Minimal Set, byte-confirmed in
ticket 01 from the shipped `schema.sql`: a `FILE` table
(`sha256, sha1, md5, crc32, file_name, file_size, package_id`) and a
`DISTINCT_HASH` (`sha256, sha1, md5, crc32`) view NIST ships. Digests are
stored UPPERCASE. Membership is served by a per-Algorithm **hash index** -- a
B-tree `CREATE INDEX` on each digest column (`idx_md5`, `idx_sha1`,
`idx_sha256`) built **inside the mounted Hash Set's own `.db`**, so a lookup
is an indexed on-disk seek, not a raw `FILE` scan, and costs O(1) memory rather
than materialising the distinct-digest set in RAM. The index lives in the same
database as the rows it covers (no second dataset, no copy to keep in sync --
ADR-0001), and a lookup UPPERCASEs the input digest to match the UPPERCASED
columns, so membership is case-agnostic. `crc32` is a physical column but is not
a supported lookup Algorithm (per CONTEXT.md). The synthetic
`METADATA`/`md5sha1`/`filename` shape is gone.
"""

from __future__ import annotations

import codecs
import os
import shutil
import sqlite3
import tempfile
import threading
from typing import Any
from typing import Dict
from typing import Sequence
from typing import Set

TABLE = "FILE"

DISTINCT_HASH_VIEW = "DISTINCT_HASH"

COLUMNS = ("sha256", "sha1", "md5", "crc32",
           "file_name", "file_size", "package_id")

COLUMN_TYPES = {
    "sha256": "VARCHAR",
    "sha1": "VARCHAR",
    "md5": "VARCHAR",
    "crc32": "VARCHAR",
    "file_name": "VARCHAR",
    "file_size": "INTEGER",
    "package_id": "INTEGER",
}

CRC32_COLUMN = "crc32"

ALGORITHM_COLUMN = {
    "md5": "md5",
    "sha1": "sha1",
    "sha256": "sha256",
}

SUPPORTED_ALGORITHMS: Set[str] = set(ALGORITHM_COLUMN)

# The per-Algorithm hash index lives inside the Hash Set's own `.db`: one B-tree
# index per lookup Algorithm column (idx_md5, idx_sha1, idx_sha256), built by
# `build_hash_index` at provision so a membership lookup is an indexed on-disk
# seek, not a raw `FILE` scan. No separate on-disk sidecar -- the index and the
# rows it covers are the one and same database (ADR-0001).
HASH_INDEX_NAMES = ["idx_" + algorithm for algorithm in ALGORITHM_COLUMN]

# Lexical states for the Delta statement scanner. NIST delta `.sql` files put
# raw carriage-return bytes inside quoted `file_name` values; a text-mode
# reader translates each lone `\r` to a line break, which splits one INSERT
# into two fragments (`unrecognized token` at apply time). The scanner is
# quote- and comment-aware so it sees the file as SQLite sees it, and it runs
# on decoded text over read/decoded chunks -- never on the whole file at once.
_CODE = 0
_SINGLE_QUOTE = 1
_DOUBLE_QUOTE = 2
_LINE_COMMENT = 3
_BLOCK_COMMENT = 4

# Ceiling on the scanner's live buffer, enforced by `_scan_stream`'s re-base
# (a `ValueError` when crossed): the in-flight statement, carried from its
# first code byte, plus the current (default 1 MiB) stream chunk. Real NIST
# delta statements are one line, a few hundred bytes at most; only a
# runaway or corrupt file -- one that never terminates -- can approach this.
_MAX_STATEMENT = 16 * (1 << 20)


def build_minimal_fixture_db(path: str, rows: Sequence[dict]) -> None:
    """Create a real-layout Minimal RDS V3 database at `path`.

    The db carries the real `FILE` table and the `DISTINCT_HASH` view NIST
    ships; digests are stored UPPERCASE. Row dicts supply the seven `FILE`
    columns and need not all be present.
    """
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        columns = ", ".join(
            f"    {name} {COLUMN_TYPES[name]}"
            for name in COLUMNS)
        conn.execute(f"CREATE TABLE {TABLE} (\n{columns}\n)")
        column_list = ", ".join(COLUMNS)
        placeholders = ", ".join(["?"] * len(COLUMNS))
        for row in rows:
            values = [row.get(column, None) for column in COLUMNS]
            conn.execute(
                f"INSERT INTO {TABLE} ({column_list}) VALUES "
                f"({placeholders})",
                tuple(values))
        conn.execute(
            f"CREATE VIEW {DISTINCT_HASH_VIEW} AS\n"
            "  SELECT DISTINCT sha256, sha1, md5, crc32\n"
            f"  FROM {TABLE};\n")
        conn.commit()
    finally:
        conn.close()


def build_hash_index(db_path: str) -> None:
    """Create the per-Algorithm B-tree index inside the Hash Set's own `.db`.

    One `CREATE INDEX IF NOT EXISTS idx_<algo> ON FILE(<algo>)` per lookup
    Algorithm, built on the writable provisioned database so a membership lookup
    is an indexed seek rather than a raw `FILE` scan. `IF NOT EXISTS` makes it
    idempotent -- a no-op on a re-apply once the index exists -- so every
    provision path can call it. (The real NIST Minimal base ships *no* indexes:
    page 1 of its `.db` schema carries the tables + view and zero `CREATE
    INDEX` -- verified from the 2026.03.1 release -- so a first provision builds
    them, which is what grows the working database ~40% on real data.) The
    index persists as part of the same database, so it needs no separate
    on-disk artifact, no shipping, and no staleness beyond the rows it covers
    (ADR-0001).
    """
    conn = sqlite3.connect(db_path)
    try:
        _rebuild_index(conn)
        conn.commit()
    finally:
        conn.close()


def _rebuild_index(conn: sqlite3.Connection) -> None:
    """Create the per-Algorithm hash index on an open db connection.

    Runs one `CREATE INDEX IF NOT EXISTS idx_<algo> ON FILE(<algo>)` per
    lookup Algorithm. `IF NOT EXISTS` keeps it idempotent, so calling it on a
    set that `provision` already indexed is a no-op. (The real NIST Minimal
    base ships *no* indexes -- page 1 of the shipped `.db` carries the schema
    with tables + view and zero `CREATE INDEX` -- so the index is ours to build
    at provision; a base never run through `provision` gets them built here as
    a correct-but-slow fallback.) Used by `build_hash_index` and by
    `apply_delta`, which refreshes the index after each apply so the refreshed
    set is indexed (ADR-0001).
    """
    for name in HASH_INDEX_NAMES:
        column = name[len("idx_"):]
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {TABLE} ({column})")


class Provenance:
    """Identity of a loaded Hash Set: Set, Release, Deltas, dbhash."""

    def __init__(self, set_name: str, release: str,
                 deltas: Sequence[str] = (),
                 dbhash: str | None = None) -> None:
        self.set_name = set_name
        self.release = release
        self.deltas = tuple(deltas)
        self.dbhash = dbhash

    def dataset(self) -> Dict[str, Any]:
        return {
            "set": self.set_name,
            "release": self.release,
            "deltas": list(self.deltas),
            "dbhash": self.dbhash,
        }


class HashSet:
    """Provisioned, queryable Hash Set with a per-Algorithm hash index.

    Opens the provisioned `.db` read-only and answers membership by an indexed
    on-disk seek, holding no in-RAM digest copy -- the index lives in the
    database itself (ADR-0001), so there is no second dataset and no OOM from
    materialising the distinct-digest set. A single read-only connection is
    shared across lookups to keep the open handles bounded. The connection
    crosses service threads (``check_same_thread=False``) and each membership
    query holds a lock, because CPython's ``sqlite3`` guarantees a connection
    may move between threads but not that concurrent use of one connection is
    safe -- and the service opens it once at boot while waitress answers
    Lookup Sessions on worker threads.
    """

    def __init__(self, path: str, provenance: Provenance) -> None:
        self._path = os.fspath(path)
        self._provenance = provenance
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            "file:" + self._path + "?mode=ro", uri=True,
            check_same_thread=False)

    @property
    def provenance(self) -> Provenance:
        return self._provenance

    @property
    def path(self) -> str:
        return self._path

    def is_known(self, algorithm: str, digest: str) -> bool:
        """Membership at the data layer; Invalid is the lookup task.

        An indexed on-disk seek: the input digest is UPPERCASED to match the
        UPPERCASED column, then compared against the per-Algorithm B-tree
        index, so any case resolves. A single-row existence test needs only the
        index, not the raw `FILE` scan, and holds no copies in RAM.
        """
        with self._lock:
            cursor = self._conn.execute(
                "SELECT 1 FROM " + TABLE + " WHERE "
                + ALGORITHM_COLUMN[algorithm] + " = ? LIMIT 1",
                (digest.upper(),))
            return cursor.fetchone() is not None


def provision(path: str, provenance: Provenance) -> HashSet:
    """Build the per-Algorithm hash index at ingest; return a Set."""
    build_hash_index(path)
    return HashSet(path, provenance)


def _emit_statement(buf, code_start, end, out):
    """Append the statement spanning `buf[code_start:end]`, if it has any.

    `code_start` is the in-flight statement's first code byte and `end` the
    offset just past its end -- the terminator found at scan time, or the
    buffer's end when a statement is left unterminated at the stream's end.
    The slice is stripped; a blank run carries no SQL. A stray `;` token
    survives the strip so `_apply_sql_stream` refuses it loudly, exactly as
    the line-based reader did.
    """
    start = 0 if code_start is None else code_start
    text = buf[start:end].strip()
    if text:
        out.append(text)


def _scan(data, scanner, out):
    """Scan `data` text, appending each complete statement found to `out`.

    `scanner` is the mutable carry `(state, pos, code_start)` -- the lexical
    state (code, a quote state, or a comment state), the scan position, and
    the offset of the in-flight statement's first code byte. Every exit from
    the scan loop writes the carry, so a token at the very end of `data` that
    a later read could still be part of (a lone closing quote that might open
    a doubled escape, a comment with no newline yet) parks `pos` just before
    a re-read of it, and the caller (`_scan_stream`) re-bases the buffer to
    the in-flight statement's start -- or to `pos` while inside a quote or
    comment -- so the token reassembles intact. While in code the in-flight
    statement's start is tracked from its first code byte, so a statement
    with no terminator and no opener in the buffer still carries on.
    """
    state, pos, code_start = scanner
    size = len(data)
    while pos < size:
        if state == _CODE:
            if code_start is None:
                code_start = _content_from(data, pos, size)
                if code_start == size:
                    code_start = None
            semi = data.find(";", pos)
            q1 = data.find("'", pos)
            q2 = data.find('"', pos)
            line = data.find("--", pos)
            block = data.find("/*", pos)
            if semi != -1 and (q1 == -1 or semi < q1) \
                    and (q2 == -1 or semi < q2) \
                    and (line == -1 or semi < line) \
                    and (block == -1 or semi < block):
                # A statement terminator in code: the statement ends here.
                _emit_statement(data, code_start, semi + 1, out)
                code_start = None
                pos = semi + 1
                continue
            openers = []
            if q1 != -1:
                openers.append((q1, _SINGLE_QUOTE, 1))
            if q2 != -1:
                openers.append((q2, _DOUBLE_QUOTE, 1))
            if line != -1:
                openers.append((line, _LINE_COMMENT, 2))
            if block != -1:
                openers.append((block, _BLOCK_COMMENT, 2))
            if not openers:
                if data[size - 1:size] in ("-", "/"):
                    # A lone `-` or `/` at the buffer's end: the opener pair
                    # (`--`, `/*`) can still arrive on the next read. Park
                    # before it so that read re-examines it, as the quote
                    # close does -- otherwise the pair never opens and the
                    # comment body is scanned as code.
                    pos = size - 1
                    break
                pos = size
                break
            token, next_state, _ = min(openers)
            if next_state in (_LINE_COMMENT, _BLOCK_COMMENT) \
                    and code_start is not None and code_start >= token:
                # The comment is the run's first content: `code_start` was
                # pinned to a `-`/`/` the lone-byte rule reported as code
                # before its pair arrived. A comment never opens a statement,
                # so clear it -- otherwise a re-base (or an open-at-EOF
                # comment) would emit the comment body as a statement.
                code_start = None
            state = next_state
            pos = token + 2 if next_state in (_LINE_COMMENT, _BLOCK_COMMENT) \
                else token + 1
            continue
        if state == _SINGLE_QUOTE:
            i = data.find("'", pos)
            if i == -1:
                pos = size
                break
            if i + 1 >= size:
                # A lone quote at the buffer's end: a closer, or the first
                # half of a doubled escape -- the next read decides.
                pos = i
                break
            if data[i + 1:i + 2] == "'":
                pos = i + 2
                continue
            state = _CODE
            pos = i + 1
            continue
        if state == _DOUBLE_QUOTE:
            i = data.find('"', pos)
            if i == -1:
                pos = size
                break
            if i + 1 >= size:
                pos = i
                break
            state = _CODE
            pos = i + 1
            continue
        if state == _LINE_COMMENT:
            newline = data.find("\n", pos)
            if newline == -1:
                pos = size
                break
            state = _CODE
            pos = newline + 1
            continue
        # _BLOCK_COMMENT.
        close = data.find("*/", pos)
        if close == -1:
            pos = size
            if pos and data[pos - 1:pos] == "*":
                # The buffer ended on the closer's first byte: the `*` and the
                # next read's leading `/` still complete it, so park before it
                # (as the quote close does) -- a re-based-away `*` strands that
                # `/` in comment state and every later statement is eaten.
                pos = pos - 1
            break
        state = _CODE
        pos = close + 2
        continue
    scanner[0], scanner[1], scanner[2] = state, pos, code_start


def _content_from(data, pos, near):
    """Offset of the first code byte in `data[pos:near]`, or `near`.

    Blanks and whole comments are skipped (a statement never starts inside
    them); `near` itself is returned when only blanks run on or a comment
    is still open at `near` -- the statement then begins once the comment
    or the content resumes.
    """
    while pos < near:
        while pos < near and data[pos] in " \t\r\n":
            pos += 1
        if pos >= near:
            return near
        if pos + 1 >= near and data[pos] in "-/":
            # The range's final byte could be the first half of a `--` or
            # `/*` opener the next read would complete -- or a code byte
            # either way; it is live content. Report it (keeping it through
            # the caller's re-base) rather than `near`, which would drop a
            # byte the next read still has to decide what it joins.
            return pos
        if data[pos:pos + 2] == "--":
            close = data.find("\n", pos)
            if close == -1 or close >= near:
                return near
            pos = close + 1
            continue
        if data[pos:pos + 2] == "/*":
            close = data.find("*/", pos)
            if close == -1 or close + 2 > near:
                return near
            pos = close + 2
            continue
        return pos
    return near


def _scan_text(delta_sql):
    """Yield the statements of an in-memory Delta text.

    Text without any `;` (the junk-probe shape) falls back to whole-line
    yields, preserving the established refuse-loudly behaviour of
    `_apply_sql_stream`; otherwise a full `;`-terminated scan assembles
    statements across line breaks, quotes, and comments.
    """
    if ";" not in delta_sql:
        yield from delta_sql.splitlines()
        return
    out = []
    scanner = [_CODE, 0, None]
    _scan(delta_sql, scanner, out)
    code_start = scanner[2]
    if code_start is not None:
        # A statement left unterminated at the text's end (its closer or
        # terminator can never arrive): emit it; the executor or the junk
        # guard refuses it loudly, as the line-based reader did.
        _emit_statement(delta_sql, code_start, len(delta_sql), out)
    for statement in out:
        yield statement


def _scan_stream(handle, chunk_size=1 << 20):
    """Yield the statements of a binary-file Delta stream.

    Raw chunks are decoded with an incremental UTF-8 decoder and buffered; the
    scanner runs over the buffer, then the buffer is re-based to what a
    later read can still be part of -- the in-flight statement from its first
    code byte while in code, or the scan position (the context) while inside
    a quote or comment -- and its scan coordinates shifted to match, so a
    statement (or a `\\r`-carrying string) split across chunk reads reassembles
    intact. A re-base that would leave more than `_MAX_STATEMENT` live text
    raises: only an unterminated statement can ever grow that far.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    buf = ""
    out = []
    scanner = [_CODE, 0, None]
    while True:
        chunk = handle.read(chunk_size)
        if not chunk:
            break
        buf += decoder.decode(chunk, final=False)
        _scan(buf, scanner, out)
        statements = out
        out = []
        for statement in statements:
            yield statement
        state, pos, code_start = scanner
        if size := len(buf):
            if code_start is not None:
                keep_from = min(code_start, pos)
            elif state != _CODE:
                # Inside a quote or comment whose closer is still to come:
                # the context matters, the consumed bytes do not.
                keep_from = pos
            else:
                keep_from = size
            # Unconditional re-base: `keep_from == size` (nothing live) must
            # still slice the buffer to nothing and zero the coordinates --
            # otherwise `pos` keeps its last value (the fully-consumed size)
            # and reads that only reassemble that consumed region start the
            # scan with `pos > len(buf)` and never advance it.
            if keep_from < 0:
                keep_from = 0
            elif keep_from > size:
                keep_from = size
            if len(buf) > keep_from:
                buf = buf[keep_from:]
            else:
                buf = ""
            scanner[1] = pos - keep_from
            scanner[2] = None if code_start is None \
                else code_start - keep_from
            if len(buf) > _MAX_STATEMENT:
                raise ValueError(
                    "delta statement exceeds %d bytes "
                    "(unterminated or corrupt)" % _MAX_STATEMENT)
    buf += decoder.decode(b"", final=True)
    _scan(buf, scanner, out)
    _, _, code_start = scanner
    if code_start is not None:
        # A statement left unterminated at the stream's end -- even one whose
        # final bytes sit inside an open comment at the end: emit it (this
        # matches `_scan_text`), and the executor or the junk guard refuses it
        # loudly. A pure comment tail carries no `code_start` (the opener
        # branch cleared it when a comment is a run's first content), so it is
        # dropped, never emitted.
        _emit_statement(buf, code_start, len(buf), out)
    for statement in out:
        yield statement


def _iter_statements(delta_sql):
    """Yield the statements of a Delta `.sql`, streaming a file when given one.

    A Delta may be a SQL string (the fixture path) or an on-disk `.sql` (`os`
    path-like, the turnkey path). A real Delta is millions of one-line
    `INSERT`s, so a path is opened in binary mode and streamed as decoded
    chunks -- never read whole into memory -- through a quote- and
    comment-aware statement scanner (`_scan`). That scanner, not a text-mode
    line split, is what keeps a NIST Delta applying cleanly: the real files
    carry carriage-return bytes inside quoted `file_name` values, and a
    text-mode reader would translate each one into a line break, slicing
    one INSERT in two.
    """
    if isinstance(delta_sql, os.PathLike):
        with open(delta_sql, "rb") as handle:
            yield from _scan_stream(handle)
    elif isinstance(delta_sql, str):
        yield from _scan_text(delta_sql)
    else:
        yield from delta_sql


def _apply_sql_stream(conn, delta_sql, batch=100_000):
    """Apply a Delta `.sql` as a streamed, batched sequence of statements.

    Feeding NIST's single `BEGIN TRANSACTION; ... COMMIT;` of millions of
    `INSERT`s to `executescript` exceeds its script-size limit and the memory
    budget; this streams one statement at a time, skips the wrapper's
    `BEGIN`/`COMMIT` markers and manages its own transactions, committing
    once every `batch` statements so neither the full text nor a
    mega-transaction is ever held at once.

    The statements arrive from `_iter_statements`' quote-aware scanner --
    already split at code-level semicolons, so a quoted `;` (or a
    carriage-return-bearing string) can never split a statement -- and this
    runner keeps the batched transactions, the junk-token guard, and the
    trailing `;` the executor expects.
    """
    conn.isolation_level = None
    conn.execute("BEGIN")
    count = 0
    for raw in _iter_statements(delta_sql):
        statement = raw.strip()
        if not statement:
            continue
        upper = statement.upper()
        if upper.startswith("BEGIN") or upper.startswith("START") \
                or upper.startswith("COMMIT"):
            continue
        if not ("A" <= statement[0] <= "Z"
                or "a" <= statement[0] <= "z"):
            # A stream line that cannot start a SQL statement -- binary
            # metadata blobs, resource forks, the like. Failing loudly here
            # (before it can corrupt anything) keeps a stale or mistyped
            # ``.sql`` from ever being applied as if it were one.
            raise ValueError(
                "non-SQL statement in delta (first token "
                + repr(statement[:40]) + ")")
        conn.execute(statement if statement.endswith(
            ";") else statement + ";")
        count += 1
        if count % batch == 0:
            conn.execute("COMMIT")
            conn.execute("BEGIN")
    conn.execute("COMMIT")
    return count


def apply_delta(base: HashSet, delta_sql: str | os.PathLike | None,
                delta_release: str,
                set_name: str | None = None,
                in_place: bool = False) -> HashSet:
    """Apply a NIST Delta as an ordered `.sql`, rebuild, refresh provenance.

    NIST ships a Delta release as a SQLite script -- `BEGIN TRANSACTION;
    INSERT/UPDATE/DELETE INTO FILE ...` -- applied to the base Hash Set by a
    streaming `execute` (the documented `.read` mechanism, no external CLI).
    A Delta `.sql` is a path (streamed) or a SQL text; a real delta of millions
    of inserts is applied in bounded batches, not read whole (ADR-0008: the
    streaming scanner; none of the file is ever in RAM at once). It then rebuilds the per-Algorithm
    hash index and records the Release plus the now-applied Delta. A Delta is
    guarded against a base of a different Set: a `set_name` is refused when it
    differs from the base (Minimal deltas apply only to Minimal bases, no
    cross-set application).

    Where the new database lands depends on `in_place`. The default is
    copy-on-apply: a full copy of the base is made into system scratch space
    and the Delta applied there, so a failed apply never touches the source
    volume. With `in_place=True` the Delta is instead applied to the base's
    own `.db`, which costs zero extra disk. In-place is only sound when the
    base is disposable scratch derived from the verified archive (the turnkey
    run's working copy); the driver routes it that way and refuses it for a
    trusted mounted volume, which keeps copy-on-apply as the protection
    (ADR-0005/ADR-0007).
    """
    if set_name is not None and set_name != base.provenance.set_name:
        raise ValueError(
            f"delta targets {set_name} but the base is "
            f"{base.provenance.set_name}")
    if in_place:
        new_path = base.path
    else:
        fd, new_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        shutil.copyfile(base.path, new_path)
    conn = sqlite3.connect(new_path)
    try:
        _apply_sql_stream(conn, delta_sql)
        _rebuild_index(conn)
    finally:
        conn.close()
    updated = list(base.provenance.deltas)
    if delta_release not in updated:
        updated.append(delta_release)
    provenance = Provenance(base.provenance.set_name,
                            base.provenance.release, updated,
                            base.provenance.dbhash)
    return HashSet(new_path, provenance)


def verify_readiness(manifest, hash_set: "HashSet") -> bool:
    """The mount is trusted only when its manifest agrees with it.

    The service is ready when a Provisioning manifest is present and its
    recorded identity -- the Set, the Release, the ordered Delta releases, and
    the final dbhash -- matches the loaded Hash Set provenance. A missing
    manifest or any mismatch means the mount is unverified, so the service is
    not-ready and serves nothing (ADR-0005). Per ADR-0006 the service trusts
    the verified mount; it does not recompute dbhash.
    """
    if manifest is None or hash_set is None:
        return False
    record = {
        "set": manifest.get("set"),
        "release": manifest.get("release"),
        "deltas": manifest.get("deltas"),
        "dbhash": manifest.get("dbhash"),
    }
    return record == hash_set.provenance.dataset()


def _sql_literal(value: Any) -> str:
    """Render a Python value as a SQL literal for an `executescript` script."""
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def build_delta_sql(rows: Sequence[dict]) -> str:
    """Render a Delta as NIST's ordered `.sql` of `FILE` inserts.

    Each insert carries the real Minimal columns with the value case as given;
    a fixture Delta is a set of inserts against a sample base. A `;` per
    statement plus `BEGIN`/`COMMIT` keep the script `executescript`-safe.
    """
    column_list = ", ".join(COLUMNS)
    statements = ["BEGIN TRANSACTION"]
    for row in rows:
        values = ", ".join(
            _sql_literal(row.get(column)) for column in COLUMNS)
        statements.append(
            f"INSERT INTO {TABLE} ({column_list}) VALUES ({values})")
    statements.append("COMMIT")
    return ";\n".join(statements) + ";\n"
