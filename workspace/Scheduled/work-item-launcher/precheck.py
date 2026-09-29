"""precheck.py - is a work item marked for the launcher, and which one runs?

One call, before any session reads anything. Read-only. The pick is
deterministic, so the session never chooses:

  Candidates  open specs (Work Items/WI-*.md) whose table carries the row
              "| Run | launcher |" - the user's mark that every decision the
              work needs is already in the spec
  Waiting     a candidate whose "Depends on" row names a work item that is
              still open is skipped until that item completes
  Resume      a candidate holding a "## Progress" section (a run that
              stopped partway) outranks everything
  Order       rank in Work Items/scores.md where that file exists (order of
              first appearance of each WI-NN in it; the kit ships no
              scorer, so any ranking you keep works), then the Priority
              row (P0 first, none last), then the lowest id

  EMPTY   no candidate, or every candidate waiting (logged by this check)
  BROKEN  the work-item folder cannot be read (logged; exit 2)
  WORK    WORK <file> - why it was picked
Exit codes: 0 EMPTY or WORK; 1 crashed; 2 broken.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), os.path.dirname(os.path.dirname(HERE))]
import runlog  # noqa: E402
from workspace_common import workspace_root  # noqa: E402

TASK = os.path.basename(HERE)
ROOT = workspace_root(HERE)
WI = os.path.join(ROOT, "Work Items")
SPEC = re.compile(r"^WI-(\d+)[_\-.].*\.md$", re.I)
RUN = re.compile(r"^\|\s*Run\s*\|\s*launcher\b", re.I | re.M)
PRIO = re.compile(r"^\|\s*Priority\s*\|\s*P(\d)\b", re.I | re.M)
DEPS = re.compile(r"^\|\s*Depends on\s*\|(.*)\|\s*$", re.I | re.M)
PROGRESS = re.compile(r"^##\s+Progress\b", re.I | re.M)
ID = re.compile(r"\bWI-(\d+)\b", re.I)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def ranking():
    p = os.path.join(WI, "scores.md")
    if not os.path.isfile(p):
        return {}
    order = {}
    for m in ID.finditer(read(p)):
        order.setdefault(int(m.group(1)), len(order))
    return order


def main():
    try:
        specs = {int(SPEC.match(f).group(1)): f for f in os.listdir(WI)
                 if SPEC.match(f) and os.path.isfile(os.path.join(WI, f))}
        texts = {n: read(os.path.join(WI, f)) for n, f in specs.items()}
        ranks = ranking()
    except OSError as e:
        return runlog.broken(TASK, "cannot read Work Items (%s)" % e)
    marked = [n for n, t in texts.items() if RUN.search(t)]
    ready, waiting = [], []
    for n in marked:
        dm = DEPS.search(texts[n])
        blockers = sorted(int(d) for d in ID.findall(dm.group(1))
                          if int(d) != n and int(d) in specs) if dm else []
        (waiting if blockers else ready).append(n)
    if not ready:
        why = "no work item marked for the launcher" if not marked else \
            "%d marked, all waiting on open work items" % len(marked)
        return runlog.empty(TASK, why)

    def key(n):
        pm = PRIO.search(texts[n])
        return (not PROGRESS.search(texts[n]), ranks.get(n, 10 ** 6),
                int(pm.group(1)) if pm else 9, n)
    pick = min(ready, key=key)
    if PROGRESS.search(texts[pick]):
        why = "resuming a run that stopped partway"
    elif pick in ranks:
        why = "first ready item in Work Items/scores.md"
    else:
        why = "highest priority ready item, lowest id on a tie"
    return runlog.work("%s - %s (%d ready, %d waiting)"
                       % (specs[pick], why, len(ready), len(waiting)))


if __name__ == "__main__":
    sys.exit(main())
