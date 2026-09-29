"""run.py - run Maintenance/cleanup.py and log the run.

cleanup.py deletes only what is past expiry, unreferenced and backed up,
and says so in one line. Logged as: deleted/held counts (exit 0), or
"held: no backup landed this week" (exit 3), or a crash (exit 1).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import runlog  # noqa: E402

TASK = os.path.basename(HERE)


def classify(last):
    if last.startswith("HELD-ALL"):
        return 3, "held: " + last.split("|", 1)[-1].strip()
    if last.startswith("DELETED"):
        return 0, "done: " + last.lower()
    return 2, "broken: unrecognised cleanup output: " + (last or "none")


if __name__ == "__main__":
    sys.exit(runlog.wrap(TASK, ["Maintenance/cleanup.py"], classify))
