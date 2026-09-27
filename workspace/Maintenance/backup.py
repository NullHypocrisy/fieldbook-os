"""backup.py - snapshot the whole workspace to dated folders.

Tiers come from workspace.json (backup.daily_dest / weekly_dest, keep
counts). Each run writes <dest>/YYYY-MM-DD as a complete copy, then prunes
the oldest dated folders past the keep count. Retention reads folder NAMES,
never filesystem timestamps. SQLite .db files go through the sqlite backup
API; everything else is a plain copy. Reads the workspace, writes out,
never writes back. One outcome line per run to backup_log.txt, even on a
crash.

Usage:  python backup.py --tier daily|weekly [--dry-run]
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import traceback
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from workspace_common import log_line, workspace_root  # noqa: E402


ROOT = workspace_root(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "backup_log.txt")
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def copy_db(src, dst):
    """Snapshot a SQLite database consistently; raw-copy if not SQLite."""
    con = out = None
    try:
        con = sqlite3.connect(src)
        out = sqlite3.connect(dst)
        con.backup(out)
    except sqlite3.Error:
        shutil.copy2(src, dst)
    finally:
        # Close explicitly: sqlite's context manager commits but does NOT
        # close, and an open handle inside the .partial folder blocks the
        # final directory rename on Windows.
        for c in (con, out):
            if c is not None:
                c.close()


def snapshot(dest_root, excluded):
    today = datetime.now().strftime("%Y-%m-%d")
    target = os.path.join(dest_root, today)
    if os.path.exists(target):
        return target, 0, "already landed"
    tmp = target + ".partial"
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    n = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        dirnames[:] = [d for d in dirnames if d not in excluded]
        outdir = os.path.join(tmp, rel) if rel != "." else tmp
        os.makedirs(outdir, exist_ok=True)
        for f in filenames:
            src = os.path.join(dirpath, f)
            dst = os.path.join(outdir, f)
            # Skip SQLite sidecars: they describe a moment already gone.
            if f.endswith(("-wal", "-shm", "-journal")):
                continue
            if f.endswith(".db"):
                copy_db(src, dst)
            else:
                try:
                    shutil.copy2(src, dst)
                except OSError as e:
                    log_line(LOG, "WARN could not copy %s (%s)" % (src, e))
                    continue
            n += 1
    # Antivirus or the search indexer can hold a brand-new folder open for
    # a moment on Windows; retry briefly, then fall back to a move.
    for attempt in range(10):
        try:
            os.rename(tmp, target)
            break
        except OSError:
            if attempt == 9:
                shutil.move(tmp, target)
            else:
                time.sleep(0.3)
    return target, n, "ok"


def prune(dest_root, keep):
    dated = sorted(d for d in os.listdir(dest_root)
                   if DATED.match(d)
                   and os.path.isdir(os.path.join(dest_root, d)))
    removed = []
    while len(dated) > keep:
        victim = dated.pop(0)
        shutil.rmtree(os.path.join(dest_root, victim))
        removed.append(victim)
    return removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["daily", "weekly"], required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        cfg = json.load(open(os.path.join(ROOT, "workspace.json"),
                             encoding="utf-8")).get("backup", {})
        dest = cfg.get(args.tier + "_dest")
        keep = int(cfg.get(args.tier + "_keep", 7))
        if not dest:
            log_line(LOG, "%s | NO-DEST | no %s_dest configured in workspace.json"
                     % (args.tier, args.tier))
            return
        dest = dest if os.path.isabs(dest) else os.path.join(ROOT, dest)
        try:
            inside = os.path.commonpath([os.path.abspath(dest), ROOT]) == ROOT
        except ValueError:      # different drives - certainly outside
            inside = False
        if inside:
            log_line(LOG, "%s | REFUSED | destination is inside the workspace; "
                     "a backup that backs itself up grows without bound"
                     % args.tier)
            return
        excluded = set(cfg.get("exclude_dirs", []))
        if args.tier == "daily":
            excluded |= set(cfg.get("daily_exclude_dirs", []))
        if args.dry_run:
            log_line(LOG, "%s | DRY-RUN | would snapshot to %s, keep %d"
                     % (args.tier, dest, keep))
            return
        os.makedirs(dest, exist_ok=True)
        target, n, status = snapshot(dest, excluded)
        removed = prune(dest, keep)
        log_line(LOG, "%s | %s | %s, %d files, pruned %s"
                 % (args.tier, status.upper(), target, n,
                    ",".join(removed) or "none"))
    except Exception:
        log_line(LOG, "%s | CRASH | %s"
                 % (args.tier, traceback.format_exc().strip().splitlines()[-1]))
        raise


if __name__ == "__main__":
    main()
