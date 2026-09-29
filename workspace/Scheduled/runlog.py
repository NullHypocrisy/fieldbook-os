"""runlog.py - the one writer of Scheduled/runs.log, and the helpers every
scheduled task's precheck and wrapper share.

The run log is one line per run, appended, never rewritten:

    YYYY-MM-DD HH:MM | task | exit N | result

- time: the local clock, read when the line is written
- task: the Scheduled/<task> folder name ("doctor" for the doctor)
- exit: the run's exit code: 0 fine (did its work or had nothing to do),
  1 crashed, 2 broken (could not do its job or could not tell), 3 held
  (ran, and stopped on or flagged something needing the user)
- result: one line; a result starting "empty" or "nothing" means the run
  found nothing to do

Maintenance/dashboard_build.py reads this file to render scheduled-piece
health; Maintenance/doctor.py writes its own line through record().

Usage (for a session that finishes a task's agenda):
  python Scheduled/runlog.py TASK CODE "RESULT"
Exit codes: 0 written; 1 crashed; 2 bad argument or the line did not land.
"""

import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs.log")


def record(task, code, result, path=RUNS):
    """Append one run line; True if it landed. Never raises."""
    try:
        result = " ".join(str(result).replace("|", "/").split()) or "-"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s | %s | exit %d | %s\n" % (
                datetime.now().strftime("%Y-%m-%d %H:%M"), task, int(code),
                result))
        return True
    except (OSError, ValueError):
        return False


def empty(task, why):
    """A precheck found nothing: log the run itself, print EMPTY, exit 0."""
    record(task, 0, "empty: " + why)
    print("EMPTY")
    return 0


def broken(task, why):
    """A precheck could not tell: log it (the board turns red), exit 2."""
    record(task, 2, "broken: " + why)
    print("BROKEN " + why)
    return 2


def work(why):
    """Something to do: print it and leave the run's line to whoever does
    the work (the wrapper, or the session following the agenda)."""
    print("WORK " + why)
    return 0


def wrap(task, argv, classify):
    """Run a workspace script for a task and log its outcome.

    argv is workspace-relative. classify(last output line) -> (code,
    result). A script that exits nonzero is a crash, whatever it printed."""
    root = os.path.dirname(HERE)
    try:
        r = subprocess.run([sys.executable] + argv, cwd=root,
                           capture_output=True, text=True)
    except OSError as e:
        return broken(task, "could not start %s (%s)" % (argv[0], e))
    lines = [x.strip() for x in (r.stdout + r.stderr).splitlines()
             if x.strip()]
    last = lines[-1] if lines else ""
    if r.returncode != 0:
        code, result = 1, "crashed: " + (last or "no output")
    else:
        code, result = classify(last)
    record(task, code, result)
    print("%s (exit %d)" % (result, code))
    return code


def main():
    if len(sys.argv) != 4:
        print('usage: runlog.py TASK CODE "RESULT"')
        return 2
    task, code, result = sys.argv[1:]
    if not code.isdigit() or not task.strip() or "|" in task:
        print("bad argument: TASK is a folder name, CODE a number")
        return 2
    if not record(task, int(code), result):
        print("BROKEN the line did not land in %s" % RUNS)
        return 2
    print("LOGGED %s exit %s" % (task, code))
    return 0


if __name__ == "__main__":
    sys.exit(main())
