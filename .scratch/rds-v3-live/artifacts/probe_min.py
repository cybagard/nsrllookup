"""Minimal ground-truth probe of the real NIST Minimal delta `.sql` files.

One C-speed check per raw LF-line (8 MiB binary chunks straight from the zips,
no text-mode newline translation): how many lines carry a `\\r` byte, how many
end in `;`, and the content of every `\\r`-bearing line (there are very few),
with each `\\r`'s offset within its line. Run with `python -u`.
"""

import sys
import time
import zipfile

from pathlib import Path

RAW = str(Path(__file__).resolve().parent / "raw")
ZIPS = [
    "RDS_2026.06.1_modern_minimal_delta.zip",
    "RDS_2026.09.1_modern_minimal_delta.zip",
    "RDS_2021.12.2_curated.zip",
]
CHUNK = 8 * (1 << 20)


def probe_stream(stream, label):
    t0 = time.time()
    lines_total = 0
    lines_cr = 0
    lines_semi = 0
    lines_nosemi = 0
    cr_examples = []
    tail = b""
    while True:
        chunk = stream.read(CHUNK)
        data = tail + chunk
        if chunk:
            parts = data.split(b"\n")
            if data.endswith(b"\n"):
                lines, tail = parts, b""
            else:
                tail = parts.pop()
                lines = parts
        else:
            lines, tail = ([tail] if tail else []), b""
        for line in lines:
            lines_total += 1
            if b"\r" in line:
                lines_cr += 1
                if len(cr_examples) < 8:
                    cr_examples.append((lines_total, line))
            if line.rstrip(b"\r \t").endswith(b";"):
                lines_semi += 1
            else:
                lines_nosemi += 1
        sys.stdout.write(
            "    [%s] %d lines in %.1fs\n" % (label, lines_total,
                                              time.time() - t0))
        sys.stdout.flush()
    print("  [%s] DONE: lines=%d  with_CR=%d  end_semi=%d  not_end_semi=%d"
          % (label, lines_total, lines_cr, lines_semi, lines_nosemi))
    for lineno, line in cr_examples:
        positions = [i for i in range(len(line)) if line[i:i + 1] == b"\r"]
        print("  --- CR line %d (%d bytes, CR at %r):" %
              (lineno, len(line), positions[:6]) +
              ("..." if len(positions) > 6 else ""))
        print("      %r" % line[:400].decode("utf-8", "replace"))
        print("      tail: %r" % line[-200:].decode("utf-8", "replace"))


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for zname in ZIPS:
        if only and only not in zname:
            continue
        print("=" * 70, flush=True)
        print("ZIP: " + zname, flush=True)
        zf = zipfile.ZipFile("%s/%s" % (RAW, zname))
        for e in zf.namelist():
            if e.endswith("/"):
                continue
            info = zf.getinfo(e)
            print("  member: %s  (%d bytes, compressed %d, "
                  "%s)" % (e, info.file_size, info.compress_size,
                           "stored" if info.compress_type == 0
                           else "deflated"), flush=True)
            if e.lower().endswith(".sql"):
                print("  probing %s..." % e, flush=True)
                probe_stream(zf.open(e), e)
        zf.close()


if __name__ == "__main__":
    main()
