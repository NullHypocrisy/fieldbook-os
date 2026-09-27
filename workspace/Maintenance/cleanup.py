"""cleanup.py - the weekly hygiene pass over Quarantine/ and Temp/managed/.

Deletes a file only when ALL THREE hold:
  1. It is past expiry (manifest line, or the cooling window from its own
     filesystem age when no line records one).
  2. Nothing load-bearing in the live tree still references its name -
     scripts, config, skills, open work-item specs. Logs, archives, and the
     quarantine area itself are excluded from the search, because they name
     retired files precisely because they were retired.
  3. This week's backup landed (skipped when require_backup is false or no
     backup destination is configured... in which case require_backup=true
     refuses to delete at all, which is the safe default).

THE ABSOLUTE BOUNDARY: nothing outside Quarantine/ and Temp/managed/ is
ever deleted. All removals funnel into safe_delete(), and that function
resolves symlinks/junctions first and raises on any path that does not sit
under one of those two roots.

Manifests are never edited: a deleted file's line stays as the record.
One outcome line per run to cleanup_log.txt, even on a crash.

Usage:  python cleanup.py [--dry-run]
"""

import argparse
import json
import os
import re
import sys
import traceback
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from workspace_common import log_line, workspace_root  # noqa: E402


ROOT = workspace_root(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "cleanup_log.txt")
QUARANTINE = os.path.join(ROOT, "Quarantine")
MANAGED = os.path.join(ROOT, "Temp", "managed")
NEVER_DELETE = {"manifest.md", "readme.md", ".keep"}
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")

LOAD_BEARING_EXTS = {".py", ".ps1", ".sh", ".bat", ".cmd",
                     ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg"}
SEARCH_MD_DIRS = ("Skills", "Work Items")   # open specs + skills only
EXCLUDED_DIR_NAMES = {"Quarantine", "__pycache__", ".git", "node_modules",
                      "completed", "logs", "closed", "managed"}


def read_manifest(folder):
    """basename -> expiry date from the folder's manifest, where recorded."""
    out = {}
    mf = os.path.join(folder, "manifest.md")
    if not os.path.exists(mf):
        return out
    for line in open(mf, encoding="utf-8", errors="replace"):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and ISO.match(parts[0]) and ISO.match(parts[1]):
            out[os.path.basename(parts[2])] = parts[1]
    return out


def load_bearing_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
        rel = os.path.relpath(dirpath, ROOT)
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in LOAD_BEARING_EXTS:
                yield os.path.join(dirpath, f)
            elif ext == ".md" and (rel == "." or
                                   rel.split(os.sep)[0] in SEARCH_MD_DIRS):
                yield os.path.join(dirpath, f)


def referenced(basename, surfaces_text):
    return basename.lower() in surfaces_text


def safe_delete(path, dry):
    real = os.path.realpath(path)
    if not (real.startswith(os.path.realpath(QUARANTINE) + os.sep)
            or real.startswith(os.path.realpath(MANAGED) + os.sep)):
        raise RuntimeError("BOUNDARY: refusing to delete " + real)
    if not dry:
        os.remove(real)


def backup_landed(cfg):
    bcfg = json.load(open(os.path.join(ROOT, "workspace.json"),
                          encoding="utf-8")).get("backup", {})
    dest = bcfg.get("weekly_dest") or bcfg.get("daily_dest")
    if not dest:
        return False
    dest = dest if os.path.isabs(dest) else os.path.join(ROOT, dest)
    if not os.path.isdir(dest):
        return False
    week_ago = date.today() - timedelta(days=7)
    for d in os.listdir(dest):
        if ISO.match(d):
            try:
                if date.fromisoformat(d) >= week_ago:
                    return True
            except ValueError:
                pass
    return False


def expiry_for(path, recorded, cooling_days):
    if os.path.basename(path) in recorded:
        return date.fromisoformat(recorded[os.path.basename(path)])
    aged = datetime.fromtimestamp(os.path.getmtime(path)).date()
    return aged + timedelta(days=cooling_days)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        cfg = json.load(open(os.path.join(ROOT, "workspace.json"),
                             encoding="utf-8")).get("cleanup", {})
        cooling = int(cfg.get("cooling_days", 14))
        require_backup = bool(cfg.get("require_backup", True))

        if require_backup and not backup_landed(cfg):
            log_line(LOG, "HELD-ALL | no backup landed this week "
                     "(require_backup is true); nothing deleted")
            return

        surfaces = ""
        for f in load_bearing_files():
            try:
                surfaces += open(f, encoding="utf-8",
                                 errors="replace").read().lower()
            except OSError:
                pass

        deleted, held = [], []
        today = date.today()
        for folder in (QUARANTINE, MANAGED):
            if not os.path.isdir(folder):
                continue
            recorded = read_manifest(folder)
            for dirpath, _, filenames in os.walk(folder):
                for f in filenames:
                    if f.lower() in NEVER_DELETE:
                        continue
                    path = os.path.join(dirpath, f)
                    if expiry_for(path, recorded, cooling) > today:
                        held.append((f, "cooling"))
                    elif referenced(f, surfaces):
                        held.append((f, "referenced"))
                    else:
                        safe_delete(path, args.dry_run)
                        deleted.append(f)
        verb = "WOULD-DELETE" if args.dry_run else "DELETED"
        log_line(LOG, "%s %d (%s) | held %d (%s)"
                 % (verb, len(deleted), ",".join(deleted[:20]) or "-",
                    len(held),
                    ",".join("%s:%s" % h for h in held[:20]) or "-"))
    except Exception:
        log_line(LOG, "CRASH | %s"
                 % traceback.format_exc().strip().splitlines()[-1])
        raise


if __name__ == "__main__":
    main()
