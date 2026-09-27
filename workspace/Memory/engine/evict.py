"""evict.py - remove a line from a working-memory file, safely.

The line is appended to today's day log for the owning tenant FIRST, the log
is re-read to confirm it landed, and only then is the line removed. Refuses
anything it cannot read back, so nothing vanishes silently.

Usage:  python evict.py <memory-file> "exact line text"
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from workspace_common import workspace_root  # noqa: E402


ROOT = workspace_root(os.path.dirname(os.path.abspath(__file__)))


def tenant_for(memfile):
    """Which tenant owns this working-memory file, per the registry."""
    reg = json.load(open(os.path.join(ROOT, "Memory", "tenants.json"),
                         encoding="utf-8"))
    target = os.path.normcase(os.path.abspath(memfile))
    entries = [("global", reg.get("global", {}))]
    entries += list(reg.get("tenants", {}).items())
    for name, t in entries:
        wm = t.get("working_memory")
        if wm and os.path.normcase(os.path.join(ROOT, wm)) == target:
            return name
    sys.exit("file is not a registered working-memory file: " + memfile)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    memfile, line = sys.argv[1], sys.argv[2].rstrip("\n")

    text = open(memfile, encoding="utf-8").read()
    if line not in text.splitlines():
        sys.exit("REFUSED: that exact line is not in the file. "
                 "Eviction is exact-match only.")

    tenant = tenant_for(memfile)
    logdir = os.path.join(ROOT, "Memory", tenant, "logs")
    os.makedirs(logdir, exist_ok=True)
    logfile = os.path.join(logdir, date.today().isoformat() + ".md")
    entry = "\n## Evicted from working memory\n%s\n" % line
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(entry)

    # Read back before touching the memory file.
    if line not in open(logfile, encoding="utf-8").read():
        sys.exit("REFUSED: read-back of the day log failed; "
                 "working memory untouched.")

    kept = [l for l in text.splitlines() if l != line]
    with open(memfile, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")
    print("evicted 1 line from %s; recorded in %s"
          % (os.path.relpath(memfile, ROOT), os.path.relpath(logfile, ROOT)))


if __name__ == "__main__":
    main()
