"""restore_drill.py - prove the newest backups RESTORE, not only that they
landed.

For the newest dated snapshot of each backup tier set in workspace.json
(newest by folder NAME):
  - every file is read in full, so an unreadable copy fails;
  - a file whose live copy has the same size and whole-second modification
    time (unchanged since the snapshot) must match it by SHA-256; files
    changed or gone since are counted, not compared;
  - every SQLite .db is restored to a scratch folder under Temp/managed
    (one manifest line, one-day expiry, removed at the end) and must pass
    PRAGMA integrity_check there. Its bytes are not compared: backup.py
    copies databases through the sqlite backup API, so they never match
    byte for byte.
Nothing in a backup destination is opened for write.

The weekly backup task runs this after a weekly snapshot lands
(Scheduled/backup_task.py); it also runs alone:

    python Maintenance/restore_drill.py

One line per run to Scheduled/runs.log as task "restore-drill" (format:
Scheduled/runlog.py), result "passed: ...", "failed: <first problem>
(+N more); ...", "broken: ..." or "nothing: no backup destination set". Any
nonzero run is also filed to the attention queue under the key the board uses,
so it waits on the user even before the board is next built.

Exit codes: 0 passed, or nothing to drill; 1 crashed; 2 could not drill (a
destination unreachable); 3 a snapshot failed the drill.
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import traceback
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)
from workspace_common import workspace_root  # noqa: E402

ROOT = workspace_root(HERE)
sys.path.insert(0, os.path.join(ROOT, "Scheduled"))
import runlog  # noqa: E402
import attention  # noqa: E402

TASK = "restore-drill"
FAIL_KEY = "backup:drill-failed"        # the board files under "board:" + it
FAIL_TEXT = ("The last restore drill failed - read its line in "
             "Scheduled/runs.log, fix what it names, then run python "
             "Maintenance/restore_drill.py.")
MANAGED = os.path.join(ROOT, "Temp", "managed")
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SQLITE_MAGIC = b"SQLite format 3\x00"
CHUNK = 1 << 20


def newest(dest):
    names = sorted(d for d in os.listdir(dest)
                   if DATED.match(d) and os.path.isdir(os.path.join(dest, d)))
    return os.path.join(dest, names[-1]) if names else None


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def check_db(path, scratch, n):
    """Restore one database to scratch and integrity-check it there.
    None when it passes, else why."""
    dst = os.path.join(scratch, "db_%05d.db" % n)
    shutil.copyfile(path, dst)
    try:
        con = sqlite3.connect(dst)
        try:
            rows = con.execute("PRAGMA integrity_check").fetchall()
        finally:
            con.close()
    except sqlite3.Error as e:
        return str(e)
    finally:
        for p in (dst, dst + "-wal", dst + "-shm", dst + "-journal"):
            try:
                os.remove(p)
            except OSError:
                pass
    return None if rows == [("ok",)] else "; ".join(
        str(r[0]) for r in rows[:3])


def drill_one(label, snap, scratch, fails):
    """Drill one snapshot folder; problems go to fails. Returns counts."""
    n = dict(files=0, dbs=0, matched=0, changed=0, locked=0)
    name = "%s %s" % (label, os.path.basename(snap))

    def walk_err(e):
        fails.append("%s: cannot list %s (%s)" % (name, e.filename, e))
    for dirpath, dirnames, files in os.walk(snap, onerror=walk_err):
        dirnames.sort()
        for fn in sorted(files):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, snap)
            n["files"] += 1
            try:
                with open(full, "rb") as f:
                    head = f.read(16)
                if fn.endswith(".db") and head == SQLITE_MAGIC:
                    n["dbs"] += 1
                    why = check_db(full, scratch, n["dbs"])
                    if why:
                        fails.append("%s: %s fails its integrity check (%s)"
                                     % (name, rel, why))
                    continue
                digest = sha(full)
            except OSError as e:
                fails.append("%s: %s unreadable (%s)" % (name, rel, e))
                continue
            live = os.path.join(ROOT, rel)
            try:
                a, b = os.stat(full), os.stat(live)
            except OSError:
                n["changed"] += 1               # gone since the snapshot
                continue
            if a.st_size != b.st_size or int(a.st_mtime) != int(b.st_mtime):
                n["changed"] += 1
                continue
            try:
                same = sha(live) == digest
            except OSError:
                n["locked"] += 1                # held open by another program
                continue
            if same:
                n["matched"] += 1
            else:
                fails.append("%s: %s differs from its unchanged live copy"
                             % (name, rel))
    if not n["files"]:
        fails.append("%s: the snapshot is empty" % name)
    return ("%s: %d files read, %d databases checked, %d matched live, "
            "%d changed since, %d locked" % (name, n["files"], n["dbs"],
                                            n["matched"], n["changed"],
                                            n["locked"]))


def scratch_dir():
    """A folder under Temp/managed with its manifest line."""
    now = datetime.now()
    name = "restore-drill-" + now.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(MANAGED, name)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(MANAGED, "manifest.md"), "a",
              encoding="utf-8") as f:
        f.write("%s | %s | %s | restore drill scratch; the drill removes it\n"
                % (now.strftime("%Y-%m-%d"),
                   (now + timedelta(days=1)).strftime("%Y-%m-%d"), name))
    return path


def drill():
    """(exit code, result) for every tier with a destination set."""
    with open(os.path.join(ROOT, "workspace.json"), encoding="utf-8-sig") as f:
        cfg = json.load(f).get("backup", {})
    snaps, cannot = [], []
    for tier in ("daily", "weekly"):
        dest = cfg.get(tier + "_dest")
        if not dest:
            continue
        dest = dest if os.path.isabs(dest) else os.path.join(ROOT, dest)
        if not os.path.isdir(dest):
            cannot.append("%s destination %s not reachable" % (tier, dest))
        elif newest(dest):
            snaps.append((tier, newest(dest)))
    if cannot:
        return 2, "broken: could not drill: " + "; ".join(cannot)
    if not snaps:
        return 0, "nothing: no backup destination set, or none landed yet"
    fails, parts = [], []
    scratch = scratch_dir()
    try:
        for tier, snap in snaps:
            parts.append(drill_one(tier, snap, scratch, fails))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if not fails:
        return 0, "passed: " + "; ".join(parts)
    more = " (+%d more)" % (len(fails) - 1) if len(fails) > 1 else ""
    return 3, "failed: %s%s; %s" % (fails[0], more, "; ".join(parts))


def main():
    try:
        code, result = drill()
    except Exception:
        code, result = 1, "crashed: " + traceback.format_exc(
            limit=3).strip().splitlines()[-1]
    runlog.record(TASK, code, result)
    if code:
        attention.file_item(FAIL_TEXT, source=TASK, key="board:" + FAIL_KEY)
    print("%s (exit %d)" % (result, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
