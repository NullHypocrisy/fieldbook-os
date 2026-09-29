"""precheck.py - is anything waiting in the global inbox? One call, before
any session reads anything. Read-only on the bridge.

WORK when Agent Bridge/to-global/ holds a message whose frontmatter status
is not done, answered or closed (a message with no readable status counts
as open). EMPTY otherwise, logged by this check. BROKEN (exit 2, logged)
when the bridge folder cannot be read.

Staleness, every run and for every inbox: an open message older than the
board's threshold (dashboard_build.BRIDGE_STALE_DAYS; date from the
filename's _YYYY-MM-DD_, else the file's age) is filed to the attention
queue once, under the key "bridge:stale:<inbox>/<file>". An inbox with no
reader never empties, so this is how its mail reaches the user. A filing
whose message has since closed, moved or gone is cleared.

Exit codes: 0 EMPTY or WORK; 1 crashed; 2 broken.
"""

import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE),
                os.path.join(os.path.dirname(os.path.dirname(HERE)),
                             "Maintenance")]
import runlog  # noqa: E402
import attention  # noqa: E402
from dashboard_build import BRIDGE_STALE_DAYS  # noqa: E402
from workspace_common import workspace_root  # noqa: E402

TASK = os.path.basename(HERE)
ROOT = workspace_root(HERE)
BRIDGE = os.path.join(ROOT, "Agent Bridge")
INBOX = "to-global"
CLOSED = ("done", "answered", "closed")
KEY = "bridge:stale:"


FRONT = re.compile(r"\A---[ \t]*\n(.*?)\n---", re.S)
STATUS = re.compile(r"^status[ \t]*:[ \t]*(\S+)", re.I | re.M)


def status_of(path):
    """The message's frontmatter status, lower case; None if it has none."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        head = FRONT.match(f.read(4000).replace("\r\n", "\n"))
    found = STATUS.search(head.group(1)) if head else None
    return found.group(1).lower() if found else None


def age_days(name, path):
    m = re.search(r"_(\d{4}-\d{2}-\d{2})_", name)
    dt = datetime.strptime(m.group(1), "%Y-%m-%d") if m else \
        datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - dt).total_seconds() / 86400


def open_messages():
    """{inbox: [(file, age in days)]} of every open message."""
    out = {}
    for box in sorted(os.listdir(BRIDGE)):
        d = os.path.join(BRIDGE, box)
        if not (box.startswith("to-") and os.path.isdir(d)):
            continue
        names = [f for f in sorted(os.listdir(d)) if f.endswith(".md")]
        paths = [(f, os.path.join(d, f)) for f in names]
        out[box] = [(f, age_days(f, p)) for f, p in paths
                    if os.path.isfile(p) and status_of(p) not in CLOSED]
    return out


def file_staleness(msgs):
    stale = set()
    for box, items in msgs.items():
        for f, age in items:
            if age > BRIDGE_STALE_DAYS:
                k = KEY + box + "/" + f
                stale.add(k)
                attention.file_item(
                    "A message in the %s inbox has waited %d days unread: "
                    "%s. Its inbox's reader has not closed it; read it, or "
                    "give that inbox a reader." % (box, int(age), f),
                    source=TASK, key=k)
    for it in attention.load()["items"]:
        if it.get("key", "").startswith(KEY) and it["key"] not in stale:
            attention.clear(it["id"])


def main():
    try:
        msgs = open_messages()
    except OSError as e:
        return runlog.broken(TASK, "cannot read the bridge folder (%s)" % e)
    try:
        file_staleness(msgs)
    except (OSError, ValueError):
        pass                    # filing never blocks the check
    mine = msgs.get(INBOX, [])
    if not mine:
        return runlog.empty(TASK, "nothing open in %s" % INBOX)
    return runlog.work("%d open message(s) in %s" % (len(mine), INBOX))


if __name__ == "__main__":
    sys.exit(main())
