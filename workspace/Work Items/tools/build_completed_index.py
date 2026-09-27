"""build_completed_index.py - regenerate the completed-work archive view.

Reads every spec in Work Items/completed/ and writes
completed/00_completed_index.md: one line per item with its project,
outcome sentence, and a link to the spec. The view is GENERATED - hand
edits to it are lost on the next run; the specs are the source.

Exit 0 on success. Usage:  python build_completed_index.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from workspace_common import workspace_root  # noqa: E402


ROOT = workspace_root(os.path.dirname(os.path.abspath(__file__)))
COMPLETED = os.path.join(ROOT, "Work Items", "completed")
OUT = os.path.join(COMPLETED, "00_completed_index.md")

WI = re.compile(r"^(WI-\d+)_(.+)\.md$")


def field(text, name):
    m = re.search(r"^%s:\s*(.+)$" % name, text, re.M)
    return m.group(1).strip() if m else ""


def main():
    os.makedirs(COMPLETED, exist_ok=True)
    rows = []
    for f in sorted(os.listdir(COMPLETED)):
        m = WI.match(f)
        if not m:
            continue
        text = open(os.path.join(COMPLETED, f),
                    encoding="utf-8", errors="replace").read()
        rows.append((m.group(1), f,
                     field(text, "project") or "?",
                     field(text, "outcome") or "(no outcome line)"))

    lines = [
        "# Completed work — GENERATED, do not hand-edit",
        "",
        "Built by tools/build_completed_index.py from the specs in this",
        "folder. Rerun it after every completion.",
        "",
        "| ID | Spec | Project | Outcome |",
        "|----|------|---------|---------|",
    ]
    for wid, fname, project, outcome in rows:
        lines.append("| %s | [%s](%s) | %s | %s |"
                     % (wid, fname, fname, project, outcome))
    if not rows:
        lines.append("| — | (nothing completed yet) | — | — |")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # Verify: every row's link resolves.
    for _, fname, _, _ in rows:
        if not os.path.exists(os.path.join(COMPLETED, fname)):
            sys.exit("stale row: " + fname)
    print("completed index rebuilt: %d items" % len(rows))


if __name__ == "__main__":
    main()
