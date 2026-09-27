"""indexer.py - build/refresh the memory search index.

Walks every tenant's scopes from Memory/tenants.json, splits markdown files
into chunks by heading, and stores them in Memory/index/memory.db with
SQLite FTS5. Incremental by content hash: unchanged files are skipped.

Secrets are excluded unconditionally: .env files never enter the index, and
any line matching a key-like pattern is dropped before storage, whatever the
scopes say.

Usage:  python indexer.py [--rebuild]
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from workspace_common import workspace_root  # noqa: E402

SECRET_LINE = re.compile(
    r"(api[_-]?key|secret|token|password|webhook)\s*[:=]\s*\S{8,}", re.I
)


ROOT = workspace_root(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "Memory", "index", "memory.db")
TENANTS = os.path.join(ROOT, "Memory", "tenants.json")


def open_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS files(
            path TEXT PRIMARY KEY, hash TEXT, mtime TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
            tenant, path, heading, body, filedate);
        """
    )
    return con


def iter_scope_files(scope):
    root = os.path.normpath(os.path.join(ROOT, scope.get("root", ".")))
    seen = set()
    for pattern in scope.get("include", ["*.md"]):
        # Split pattern into directory part and filename part.
        subdir, _, name = pattern.rpartition("/")
        base = os.path.normpath(os.path.join(root, subdir)) if subdir else root
        if "**" in subdir:
            walk_roots = [d for d, _, _ in os.walk(root)]
        elif subdir:
            walk_roots = [base] if os.path.isdir(base) else []
        else:
            walk_roots = [root] if os.path.isdir(root) else []
        for d in walk_roots:
            try:
                entries = os.listdir(d)
            except OSError:
                continue
            for f in entries:
                full = os.path.join(d, f)
                if not os.path.isfile(full) or full in seen:
                    continue
                if f == ".env" or f.endswith(".env"):
                    continue
                if fnmatch.fnmatch(f, name or "*.md"):
                    seen.add(full)
                    yield full


def chunk(text):
    """Yield (heading, body) pairs, split on markdown headings."""
    heading, buf = "(top)", []
    for line in text.splitlines():
        if line.startswith("#"):
            if buf and "".join(buf).strip():
                yield heading, "\n".join(buf).strip()
            heading, buf = line.lstrip("#").strip(), []
        elif not SECRET_LINE.search(line):
            buf.append(line)
    if buf and "".join(buf).strip():
        yield heading, "\n".join(buf).strip()


def file_date(path):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    if m:
        return m.group(1)
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def index_file(con, tenant, path):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print("SKIP %s (%s)" % (path, e))
        return 0
    h = hashlib.sha256(text.encode()).hexdigest()
    row = con.execute("SELECT hash FROM files WHERE path=?", (path,)).fetchone()
    if row and row[0] == h:
        return 0
    con.execute("DELETE FROM chunks WHERE path=?", (path,))
    n = 0
    fdate = file_date(path)
    for heading, body in chunk(text):
        con.execute(
            "INSERT INTO chunks(tenant,path,heading,body,filedate) VALUES(?,?,?,?,?)",
            (tenant, path, heading, body, fdate),
        )
        n += 1
    con.execute(
        "INSERT OR REPLACE INTO files(path,hash,mtime) VALUES(?,?,?)",
        (path, h, datetime.now().isoformat(timespec="seconds")),
    )
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true",
                    help="drop the index and reindex everything")
    args = ap.parse_args()

    if args.rebuild and os.path.exists(DB):
        os.remove(DB)
    con = open_db()

    reg = json.load(open(TENANTS, encoding="utf-8"))
    plans = [("global", reg.get("global", {}).get("scopes", []))]
    for name, t in reg.get("tenants", {}).items():
        plans.append((name, t.get("scopes", [])))

    total = 0
    for tenant, scopes in plans:
        for scope in scopes:
            for path in iter_scope_files(scope):
                total += index_file(con, tenant, path)
    con.commit()
    nfiles = con.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    nchunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    con.close()
    print("indexed: %d new/changed chunks; %d files, %d chunks total"
          % (total, nfiles, nchunks))


if __name__ == "__main__":
    main()
