"""Provision/delta-apply smoke checks (build-time, not a seam).

Fixtures model a Delta as a set of insert rows, rendered to NIST's ordered
`.sql` shape and applied by `executescript`; we assert the index rebuild, the
provenance refresh, and that the base is left untouched.
"""

import app
import hashlib
import io
import os
import sqlite3
from hasheset import Provenance
import hasheset

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"


def _row(file_name, md5, **kw):
    row = {"crc32": None, "md5": md5, "sha1": None, "sha256": None,
            "file_name": file_name, "file_size": 0, "package_id": 0}
    row.update(kw)
    return row


def _apply(base_set, rows, release):
     """Apply a fixture Delta rendered as NIST's ordered `.sql`."""
     delta_sql = hasheset.build_delta_sql(rows)
     return hasheset.apply_delta(base_set, delta_sql, release)


def test_apply_delta_yields_updated_hash_set(tmp_path):
     """Applying a Delta adds rows and rebuilds the index."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [
           _row("base.bin", KNOWN_MD5),
           _row("md5only.bin", "11111111111111111111111111111111"),
       ])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
     updated = _apply(base_set, [_row("delta.bin", new_md5)], "2026.06.1")
     assert updated.is_known("md5", new_md5)
     assert updated.is_known("md5", KNOWN_MD5)
     assert not base_set.is_known("md5", new_md5)


def test_apply_delta_refreshes_provenance(tmp_path):
     """The applied Delta is recorded in the refreshed provenance."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     updated = _apply(base_set, [_row("delta.bin", KNOWN_MD5)], "2026.06.1")
     assert updated.provenance.release == "2026.03.1"
     assert updated.provenance.deltas == ("2026.06.1",)
     assert updated.provenance.dataset() == {
          "set": "modern", "release": "2026.03.1", "deltas": ["2026.06.1"], "dbhash": "deadbeef"}


def test_apply_delta_leaves_base_untouched(tmp_path):
     """Copy-on-apply leaves the base db's rows unchanged."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
     _apply(base_set, [_row("delta.bin", new_md5)], "2026.06.1")
     assert base_set.is_known("md5", KNOWN_MD5)
     assert not base_set.is_known("md5", new_md5)


def test_apply_delta_in_place_updates_the_same_database(tmp_path):
    # In-place apply (ADR-0007): the Delta lands in the base's own `.db`, so a
    # disposable scratch working copy costs no second full database.
    base = str(tmp_path / "base.db")
    hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
    base_set = hasheset.provision(base,
        Provenance("modern", "2026.03.1", dbhash="deadbeef"))
    new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
    updated = hasheset.apply_delta(
        base_set,
        hasheset.build_delta_sql([_row("delta.bin", new_md5)]),
        "2026.06.1", in_place=True)
    assert updated.path == base_set.path
    assert updated.is_known("md5", new_md5)
    assert updated.provenance.deltas == ("2026.06.1",)
    # The row persisted in the one file a re-open sees.
    reloaded = hasheset.HashSet(
        base, Provenance("modern", "2026.03.1"))
    assert reloaded.is_known("md5", new_md5)
    assert reloaded.is_known("md5", KNOWN_MD5)


def test_apply_delta_default_copies_to_a_new_database(tmp_path):
    # The default copy-on-apply result is a fresh path; the source is intact.
    base = str(tmp_path / "base.db")
    hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
    base_set = hasheset.provision(base,
        Provenance("modern", "2026.03.1", dbhash="deadbeef"))
    new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
    updated = hasheset.apply_delta(
        base_set,
        hasheset.build_delta_sql([_row("delta.bin", new_md5)]),
        "2026.06.1")
    assert os.path.realpath(updated.path) != os.path.realpath(base)
    assert not base_set.is_known("md5", new_md5)


def test_junk_statement_is_refused(tmp_path):
    # A stream line that cannot start a SQL statement (binary metadata, a
    # resource fork) is refused loudly; it is never applied as if it were a
    # script, and nothing is left half-written.
    base = str(tmp_path / "base.db")
    hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
    base_set = hasheset.provision(base,
        Provenance("modern", "2026.03.1", dbhash="deadbeef"))
    try:
        hasheset.apply_delta(
            base_set, "BEGIN TRANSACTION\n._Icon\nCOMMIT", "2026.06.1")
    except ValueError as err:
        assert "non-SQL statement" in str(err)
        return
    raise AssertionError("expected a junk statement to be refused")


def test_delta_refused_on_mismatched_set(tmp_path):
     """A Minimal delta is refused against a base of a different Set."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     delta_sql = hasheset.build_delta_sql([_row("delta.bin", KNOWN_MD5)])
     try:
         hasheset.apply_delta(base_set, delta_sql, "2026.06.1",
                              set_name="legacy")
     except ValueError:
         return
     raise AssertionError("expected cross-set application to be refused")


def test_health_reports_refreshed_provenance(tmp_path):
     """Health reflects the applied Delta after a rebuild."""
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(base,
         Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     updated = _apply(base_set, [_row("delta.bin", KNOWN_MD5)], "2026.06.1")
     app.configure(updated, updated.provenance.dataset())
     try:
          data = app.api.test_client().get("/health").get_json()
          assert data["dataset"] == {
               "set": "modern", "release": "2026.03.1", "deltas": ["2026.06.1"], "dbhash": "deadbeef"}
     finally:
          app.configure(None)


def _scan(data, chunk=1):
     """Decode `data` through the streamed scanner at a given chunk size."""
     return list(hasheset._scan_stream(io.BytesIO(data), chunk_size=chunk))


def test_scanner_is_chunk_size_invariant():
     # The scanner must cut a Delta identically no matter how the bytes arrive:
     # a CR byte, a doubled quote, a comment opener, or a semicolon inside a
     # value that straddles a chunk boundary must not split a statement that a
     # whole-file read keeps whole.
     sql = (
          "BEGIN TRANSACTION;\n"
          "INSERT INTO FILE(sha256,sha1,md5,crc32,file_name,file_size,package_id) "
          "VALUES('E3B0','DA39',\r'D0','6FB1',\n"
          "'w32py-3.7.4; \"x\" -- y/*z*/.exe','129758','Game');\n"
          "COMMIT;\n"
     ).encode()
     expected = list(hasheset._scan_text(sql.decode("utf-8")))
     assert len(expected) == 3
     for chunk in (1, 2, 3, 5, 8, 17, 64):
          assert _scan(sql, chunk) == expected, chunk


def test_scanner_sweeps_comment_and_blank_trailing():
     # Whitespace, lone comment openers, and closed trailing comments after the
     # final statement yield no extra statement -- not even an empty one.
     for tail in (b"COMMIT;\n", b"COMMIT;\n\n", b"COMMIT;\n-- note\n",
                     b"COMMIT;\n--", b"COMMIT;\n/*\n*/\n", b"COMMIT;\n/*",
                     b"COMMIT;\n  \t "):
          for chunk in (1, 2, 3):
               got = _scan(b"insert into t values (1);\n" + tail, chunk)
               assert got == ["insert into t values (1);", "COMMIT;"], \
                    (tail, chunk, got)


def test_scanner_dangling_fragment_is_emitted():
     # A bare code fragment trailing the final `;` (a lone `-` that never
     # becomes a `--` comment) is emitted -- the apply runner then refuses it
     # loudly. This is the safe behaviour: a malformed Delta surfaces, it does
     # not vanish.
     got = _scan(b"insert into t values (1);\nCOMMIT;\n-", 1)
     assert got == ["insert into t values (1);", "COMMIT;", "-"]


def test_scanner_unterminated_fragment_is_loud():
     got = _scan(b"insert into t values ('a")
     assert got == ["insert into t values ('a"]


def test_scanner_oversized_statement_refused():
     sql = b"insert into t values ('" + b"z" * (
          hasheset._MAX_STATEMENT + 1) + b"')\n"
     try:
          list(hasheset._scan_stream(io.BytesIO(sql), chunk_size=1024))
     except ValueError as err:
          assert "exceeds" in str(err)
          return
     raise AssertionError("expected an oversized statement to be refused")


def test_apply_file_path_stream_preserves_cr_and_quotes(tmp_path):
     # The turnkey path: a Delta given as an on-disk `.sql` is streamed (never
     # read whole) and applied; a CR byte, a doubled quote, a semicolon, and a
     # trailing comment inside a `file_name` all survive into the stored value.
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(
          base, Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     delta_path = tmp_path / "delta.sql"
     delta_path.write_bytes(
          b"BEGIN TRANSACTION;\n"
          b"INSERT INTO FILE(sha256,sha1,md5,crc32,file_name,file_size,package_id)\n"
          b"VALUES(NULL,NULL,NULL,NULL,"
          b"'x\ry''z;w -- c','5','P');\n"
          b"COMMIT;\n-- trailing comment\n")
     updated = hasheset.apply_delta(base_set, delta_path, "2026.04.1",
                                            in_place=True)
     value = sqlite3.connect(updated.path).execute(
          "SELECT file_name FROM FILE WHERE package_id = 'P'").fetchone()[0]
     assert value == "x\ry'z;w -- c"


def test_apply_file_path_trailing_comment_is_dropped(tmp_path):
     # A trailing line comment after the final statement is swept, so the apply
     # succeeds and lands exactly one new row (the base row plus the delta row).
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(
          base, Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     delta_path = tmp_path / "delta.sql"
     delta_path.write_bytes(
          b"BEGIN TRANSACTION;\n"
          b"INSERT INTO FILE(sha256,sha1,md5,crc32,file_name,file_size,package_id)\n"
          b"VALUES(NULL,NULL,NULL,NULL,'row2','5','P2');\n"
          b"COMMIT;\n-- trailing\n")
     updated = hasheset.apply_delta(base_set, delta_path, "2026.04.1",
                                            in_place=True)
     count = sqlite3.connect(updated.path).execute(
          "SELECT COUNT(*) FROM FILE").fetchone()[0]
     assert count == 2


def test_apply_file_path_dangling_fragment_is_refused(tmp_path):
     # A Delta that ends in a bare code fragment (not a comment) is refused
     # loudly and leaves the base unmodified -- nothing half-written.
     base = str(tmp_path / "base.db")
     hasheset.build_minimal_fixture_db(base, [_row("base.bin", KNOWN_MD5)])
     base_set = hasheset.provision(
          base, Provenance("modern", "2026.03.1", dbhash="deadbeef"))
     delta_path = tmp_path / "delta.sql"
     delta_path.write_bytes(
          b"BEGIN TRANSACTION;\n"
          b"INSERT INTO FILE(sha256,sha1,md5,crc32,file_name,file_size,package_id)\n"
          b"VALUES(NULL,NULL,NULL,NULL,'row3','5','P3');\n"
          b"COMMIT;\n-")
     try:
          hasheset.apply_delta(base_set, delta_path, "2026.04.1",
                                    in_place=True)
     except ValueError as err:
          assert "non-SQL statement" in str(err)
     else:
          raise AssertionError("expected a dangling fragment to be refused")
     count = sqlite3.connect(base).execute(
          "SELECT COUNT(*) FROM FILE").fetchone()[0]
     assert count == 1
     assert base_set.is_known("md5", KNOWN_MD5)



def test_scanner_block_comment_closer_straddles_a_chunk_boundary():
     # A `*/` split across chunk reads must still close its comment: a
     # re-based-away trailing `*` would strand the next read's leading `/` in
     # comment state and every later statement would silently go missing.
     sql = ("insert into t values (1); /*X*/\n"
            "insert into t values (2);\n")
     expected = ["insert into t values (1);", "insert into t values (2);"]
     for chunk in range(1, len(sql) + 1):
          assert _scan(sql.encode("utf-8"), chunk) == expected, chunk
     assert list(hasheset._scan_text(sql)) == expected


def test_scanner_unterminated_statement_in_comment_matches_text():
     # A statement left unterminated whose final bytes open a comment at the
     # end must be emitted on both the text and the stream path -- the loud
     # refuse, never a silent loss -- whatever the chunk size.
     sql = ("insert into t values (1);\n"
            "insert into t values (2) /*")
     expected = ["insert into t values (1);",
                 "insert into t values (2) /*"]
     for chunk in (1, 2, 3, 16):
          assert _scan(sql.encode("utf-8"), chunk) == expected, chunk
     assert list(hasheset._scan_text(sql)) == expected
