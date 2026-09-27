"""smoke_test.py - prove the installation works, end to end.

Copies the workspace to a throwaway temp folder and exercises each system
there, so the real workspace is untouched. Prints PASS/FAIL per check and
exits nonzero on any failure.

Usage:  python Maintenance/smoke_test.py   (from anywhere)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from workspace_common import workspace_root  # noqa: E402


SRC = workspace_root(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        (" - " + detail) if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(ws, *args):
    r = subprocess.run([sys.executable] + list(args), cwd=ws,
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    tmp = tempfile.mkdtemp(prefix="workspace-smoke-")
    ws = os.path.join(tmp, "ws")
    shutil.copytree(SRC, ws, ignore=shutil.ignore_patterns(
        "__pycache__", "memory.db", "*.log", "*_log.txt"))
    print("smoke workspace: %s\n" % ws)

    # --- Memory: index, search, evict -------------------------------
    rc, out = run(ws, os.path.join("Memory", "engine", "indexer.py"))
    check("memory: indexer runs", rc == 0, out)
    check("memory: chunks indexed", "chunks total" in out and
          not out.startswith("indexed: 0 "), out)
    rc, out = run(ws, os.path.join("Memory", "engine", "search.py"),
                  "admission test")
    check("memory: search finds AGENTS.md content", rc == 0 and
          "AGENTS.md" in out, out[:200])
    rc, out = run(ws, os.path.join("Memory", "engine", "search.py"),
                  "zzz-no-such-term-zzz")
    check("memory: honest miss", "not found in memory" in out, out[:200])

    wm = os.path.join(ws, "Memory", "global", "working-memory.md")
    with open(wm, "a", encoding="utf-8") as f:
        f.write("evictable test line\n")
    rc, out = run(ws, os.path.join("Memory", "engine", "evict.py"),
                  wm, "evictable test line")
    logf = os.path.join(ws, "Memory", "global", "logs",
                        date.today().isoformat() + ".md")
    check("memory: evict records then removes", rc == 0
          and os.path.exists(logf)
          and "evictable test line" in open(logf, encoding="utf-8").read()
          and "evictable" not in open(wm, encoding="utf-8").read(), out)

    # --- Work items: complete the example item ----------------------
    spec = os.path.join(ws, "Work Items", "WI-01_example-item.md")
    with open(spec, "a", encoding="utf-8") as f:
        f.write("\noutcome: smoke test completion\n")
    os.makedirs(os.path.join(ws, "Work Items", "completed"), exist_ok=True)
    shutil.move(spec, os.path.join(ws, "Work Items", "completed",
                                   "WI-01_example-item.md"))
    rc, out = run(ws, os.path.join("Work Items", "tools",
                                   "build_completed_index.py"))
    idx = os.path.join(ws, "Work Items", "completed",
                       "00_completed_index.md")
    check("work items: completed index builds", rc == 0
          and os.path.exists(idx)
          and "WI-01" in open(idx, encoding="utf-8").read(), out)

    # --- Backup: real snapshot to a temp destination ----------------
    dest = os.path.join(tmp, "backups")
    cfgp = os.path.join(ws, "workspace.json")
    cfg = json.load(open(cfgp, encoding="utf-8"))
    cfg["backup"]["weekly_dest"] = dest
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), indent=2)
    rc, out = run(ws, os.path.join("Maintenance", "backup.py"),
                  "--tier", "weekly")
    snap = os.path.join(dest, date.today().isoformat())
    check("backup: snapshot lands", rc == 0 and os.path.isdir(snap), out)
    check("backup: snapshot carries AGENTS.md",
          os.path.exists(os.path.join(snap, "AGENTS.md")))

    # --- Cleanup: expired file deleted, cooling file held -----------
    # Filenames are ASSEMBLED so their literals never appear in this file:
    # this script is itself a load-bearing surface the reference re-check
    # searches, and a spelled-out name here would hold the file forever.
    qname = "old_" + "scr" + "atch.txt"
    qfile = os.path.join(ws, "Quarantine", qname)
    open(qfile, "w").write("expired quarantined file")
    with open(os.path.join(ws, "Quarantine", "manifest.md"), "a",
              encoding="utf-8") as f:
        f.write("2020-01-01 | 2020-01-15 | Quarantine/%s | smoke\n" % qname)
    kfile = os.path.join(ws, "Temp", "managed",
                         "fresh_" + "scr" + "atch.txt")
    open(kfile, "w").write("fresh managed file")
    rc, out = run(ws, os.path.join("Maintenance", "cleanup.py"))
    check("cleanup: expired file deleted", rc == 0
          and not os.path.exists(qfile), out)
    check("cleanup: fresh file held (cooling)", os.path.exists(kfile), out)

    # --- Cleanup: boundary holds ------------------------------------
    outside = os.path.join(ws, "AGENTS.md")
    check("cleanup: boundary intact", os.path.exists(outside))

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    if FAILURES:
        print("FAILED: %d check(s): %s" % (len(FAILURES),
                                           ", ".join(FAILURES)))
        sys.exit(1)
    print("ALL CHECKS PASSED - the installation works.")


if __name__ == "__main__":
    main()
