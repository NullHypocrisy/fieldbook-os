"""close_commit.py - commit the workspace at session close.

Stages everything git does not ignore and commits it with the message
given. A session calls this last, after its day log and memory writes, so
they are in the commit. Nothing changed: says so and exits clean.

Usage:  python Maintenance/close_commit.py -m "what changed and why"

Exit codes:
  0  committed, or nothing to commit (the printed word says which)
  1  crashed (an uncaught error)
  2  broken: git missing, not a git repository, or the commit failed
"""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from workspace_common import git, git_identity, workspace_root  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", required=True)
    args = ap.parse_args()
    root = workspace_root(os.path.dirname(os.path.abspath(__file__)))
    if not shutil.which("git"):
        print("BROKEN: git is not installed")
        return 2
    rc, out = git(root, "rev-parse", "--show-toplevel")
    if rc != 0:
        print("BROKEN: %s is not a git repository" % root)
        return 2
    rc, out = git(root, "add", "-A")
    if rc != 0:
        print("BROKEN: git add failed: %s" % out)
        return 2
    rc, _ = git(root, "diff", "--cached", "--quiet")
    if rc == 0:
        print("NOTHING TO COMMIT: the workspace is unchanged")
        return 0
    rc, out = git(root, *(git_identity(root) +
                          ["commit", "-q", "-m", args.message]))
    if rc != 0:
        print("BROKEN: git commit failed: %s" % out)
        return 2
    _, head = git(root, "rev-parse", "--short", "HEAD")
    print("COMMITTED %s: %s" % (head, args.message))
    return 0


if __name__ == "__main__":
    sys.exit(main())
