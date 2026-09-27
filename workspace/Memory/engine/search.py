"""search.py - keyword recall over the memory index, with citations.

Usage:  python search.py "query" [--tenant NAME] [--limit N]

Every hit prints source file, heading, and date. No hits prints
"not found in memory" - never a guess.
"""

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from workspace_common import workspace_root  # noqa: E402


ROOT = workspace_root(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "Memory", "index", "memory.db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--tenant")
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()

    if not os.path.exists(DB):
        sys.exit("no index yet - run engine/indexer.py first")
    con = sqlite3.connect(DB)
    # Quote each term so user punctuation cannot break FTS5 query syntax.
    q = " ".join('"%s"' % t.replace('"', "") for t in args.query.split())
    sql = ("SELECT tenant, path, heading, filedate, "
           "snippet(chunks, 3, '[', ']', '...', 24) "
           "FROM chunks WHERE chunks MATCH ?")
    params = [q]
    if args.tenant:
        sql += " AND tenant=?"
        params.append(args.tenant)
    sql += " ORDER BY bm25(chunks), filedate DESC LIMIT ?"
    params.append(args.limit)
    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        sys.exit("query error: %s" % e)
    if not rows:
        print("not found in memory")
        return
    for tenant, path, heading, fdate, snip in rows:
        rel = os.path.relpath(path, ROOT)
        print("[%s] %s :: %s (%s)\n    %s\n" % (tenant, rel, heading, fdate,
                                                snip.replace("\n", " ")))


if __name__ == "__main__":
    main()
