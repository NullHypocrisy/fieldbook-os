"""precheck.py - is anything in Quarantine/ or Temp/managed/ past expiry?

One call, before any session reads anything. Uses cleanup.py's own
expiry rules (manifest line, else the cooling window from the file's age),
so the check and the cleanup never disagree. Deletes nothing.
  EMPTY   nothing past expiry (logged by this check)
  BROKEN  workspace.json or a folder unreadable (logged; exit 2)
  WORK    N file(s) past expiry; run.py lets cleanup.py decide each one
Exit codes: 0 EMPTY or WORK; 1 crashed; 2 broken.
"""

import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE),
                os.path.join(os.path.dirname(os.path.dirname(HERE)),
                             "Maintenance")]
import runlog  # noqa: E402
import cleanup  # noqa: E402

TASK = os.path.basename(HERE)


def main():
    try:
        with open(os.path.join(cleanup.ROOT, "workspace.json"),
                  encoding="utf-8") as f:
            cooling = int(json.load(f).get("cleanup", {})
                          .get("cooling_days", 14))
        due = 0
        for folder in (cleanup.QUARANTINE, cleanup.MANAGED):
            if not os.path.isdir(folder):
                continue
            recorded = cleanup.read_manifest(folder)
            for dirpath, _, files in os.walk(folder):
                for f in files:
                    if f.lower() in cleanup.NEVER_DELETE:
                        continue
                    exp = cleanup.expiry_for(os.path.join(dirpath, f),
                                             recorded, cooling)
                    due += exp <= date.today()
    except (OSError, ValueError) as e:
        return runlog.broken(TASK, "could not read the cleanup folders (%s)"
                             % e)
    if not due:
        return runlog.empty(TASK, "nothing past expiry")
    return runlog.work("%d file(s) past expiry" % due)


if __name__ == "__main__":
    sys.exit(main())
