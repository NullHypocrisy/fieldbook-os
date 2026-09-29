"""precheck.py - the nightly memory sweep's mechanical half, and its answer
to "is there anything for a session to do?".

1. Index: runs Memory/engine/indexer.py (incremental; unchanged files are
   skipped) and, on success, marks the index file as refreshed now, so the
   board's "rebuilt" date means "last known current".
2. Drift audit, against Memory/tenants.json: a tenant whose working-memory
   file is missing, or whose working memory or core profile is over its
   cap. Over cap means lines are homed in the wrong file.

  EMPTY   index refreshed, no drift (logged by this check)
  BROKEN  the indexer failed or tenants.json is unreadable (logged; exit 2)
  WORK    drift found, one "tenant: what" item per finding; the session
          follows AGENDA.md and logs the run
Exit codes: 0 EMPTY or WORK; 1 crashed; 2 broken.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), os.path.dirname(os.path.dirname(HERE))]
import runlog  # noqa: E402
from workspace_common import workspace_root  # noqa: E402

TASK = os.path.basename(HERE)
ROOT = workspace_root(HERE)
DB = os.path.join(ROOT, "Memory", "index", "memory.db")


def size(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8",
              errors="replace") as f:
        return len(f.read())


def drift():
    with open(os.path.join(ROOT, "Memory", "tenants.json"),
              encoding="utf-8") as f:
        reg = json.load(f)
    tenants = [("global", reg.get("global", {}))] + \
        sorted(reg.get("tenants", {}).items())
    found = []
    for name, t in tenants:
        wm = t.get("working_memory")
        if not wm or not os.path.isfile(os.path.join(ROOT, wm)):
            found.append("%s: working-memory file missing" % name)
        else:
            cap = int(t.get("cap_chars", 0) or 0)
            n = size(wm)
            if cap and n > cap:
                found.append("%s: working memory %d / %d chars"
                             % (name, n, cap))
        cp, ccap = t.get("core_profile"), int(
            t.get("core_profile_cap_chars", 0) or 0)
        if cp and ccap and os.path.isfile(os.path.join(ROOT, cp)) \
                and size(cp) > ccap:
            found.append("%s: core profile %d / %d chars"
                         % (name, size(cp), ccap))
    return found


def main():
    r = subprocess.run([sys.executable, os.path.join(
        "Memory", "engine", "indexer.py")], cwd=ROOT, capture_output=True,
        text=True)
    out = (r.stdout + r.stderr).strip().splitlines()
    if r.returncode != 0 or not os.path.exists(DB):
        return runlog.broken(TASK, "indexer failed: %s"
                             % (out[-1] if out else "no output"))
    os.utime(DB)
    indexed = out[-1] if out else "indexed"
    try:
        found = drift()
    except (OSError, ValueError) as e:
        return runlog.broken(TASK, "Memory/tenants.json unreadable (%s)" % e)
    if not found:
        return runlog.empty(TASK, "no drift; " + indexed)
    return runlog.work("drift: " + "; ".join(found))


if __name__ == "__main__":
    sys.exit(main())
