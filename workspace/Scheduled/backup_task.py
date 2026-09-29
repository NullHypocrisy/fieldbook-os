"""backup_task.py - precheck and wrapper shared by the two backup tasks,
Scheduled/backup-daily and Scheduled/backup-weekly. Each folder's
precheck.py and run.py call in here with its tier.

precheck(tier) answers "is a snapshot due?" from workspace.json and the
destination alone, without copying anything:
  EMPTY   no destination set for the tier, or today's dated folder is
          already there (logged by the check itself)
  BROKEN  the destination is inside the workspace, or neither it nor its
          parent folder can be reached (logged; exit 2)
  WORK    a snapshot is due
run(tier) runs Maintenance/backup.py for the tier and logs its outcome.
When a weekly snapshot newly lands, it then runs Maintenance/restore_drill.py,
which logs under its own task name, restore-drill; nothing here reads those
lines as a backup's.

Exit codes: 0 EMPTY, WORK or a landed snapshot; 1 crashed; 2 broken.
"""

import json
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import runlog  # noqa: E402
from workspace_common import workspace_root  # noqa: E402

ROOT = workspace_root(HERE)


def task(tier):
    return "backup-" + tier


def precheck(tier):
    t = task(tier)
    try:
        with open(os.path.join(ROOT, "workspace.json"), encoding="utf-8") as f:
            cfg = json.load(f).get("backup", {})
    except (OSError, ValueError) as e:
        return runlog.broken(t, "workspace.json unreadable (%s)" % e)
    dest = cfg.get(tier + "_dest")
    if not dest:
        return runlog.empty(t, "no %s backup destination set in "
                            "workspace.json" % tier)
    dest = os.path.abspath(dest if os.path.isabs(dest)
                           else os.path.join(ROOT, dest))
    try:
        inside = os.path.commonpath([dest, ROOT]) == ROOT
    except ValueError:          # different drives: certainly outside
        inside = False
    if inside:
        return runlog.broken(t, "the %s destination is inside the workspace; "
                             "set one outside it in workspace.json" % tier)
    if not (os.path.isdir(dest) or os.path.isdir(os.path.dirname(dest))):
        return runlog.broken(t, "the %s destination %s cannot be reached "
                             "(drive or share not connected?)" % (tier, dest))
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.isdir(os.path.join(dest, today)):
        return runlog.empty(t, "today's %s snapshot already landed" % tier)
    return runlog.work("%s snapshot due to %s" % (tier, dest))


def classify(last):
    parts = [p.strip() for p in last.split("|")]
    status = parts[1] if len(parts) > 2 else ""
    detail = " | ".join(parts[2:]) if len(parts) > 2 else last
    if status == "REFUSED":
        return 2, "broken: " + detail
    if status == "NO-DEST":
        return 0, "nothing: " + detail
    if status in ("OK", "ALREADY LANDED"):
        return 0, "snapshot landed: " + detail
    return 2, "broken: unrecognised backup output: " + (last or "none")


def run(tier):
    lasts = []

    def seen(last):
        lasts.append(last)
        return classify(last)
    code = runlog.wrap(task(tier), ["Maintenance/backup.py", "--tier", tier],
                       seen)
    landed = code == 0 and lasts and [p.strip() for p in
                                      lasts[0].split("|")][1:2] == ["OK"]
    if tier == "weekly" and landed:
        drill()
    return code


def drill():
    """The restore drill, after a weekly snapshot lands. It logs its own
    line as task restore-drill; the backup's exit code stays its own."""
    try:
        r = subprocess.run([sys.executable, "Maintenance/restore_drill.py"],
                           cwd=ROOT, capture_output=True, text=True)
        for line in (r.stdout + r.stderr).strip().splitlines()[-1:]:
            print(line)
    except OSError as e:
        runlog.record("restore-drill", 1, "crashed: could not start the "
                      "drill (%s)" % e)
