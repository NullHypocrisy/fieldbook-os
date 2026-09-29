"""attention.py - the waiting-on-you queue: everything that needs the user.

One file, attention.json at the workspace root. Any script or session that
finds something only the user can act on files it here; the board
(dashboard_build.py) renders it first, urgent items on top. Ids are A-1,
A-2, ... and are never reused.

Idempotent: every entry carries a key (--key, default the text itself). A
filing whose key matches an open entry returns that entry's id and writes
nothing, so a retried run never duplicates. Clearing is a --clear A-N call
by whoever records the resolution.

Filing never blocks its caller: file_item() and clear() swallow their own
errors and return None/False. Standard library only.

Usage:
  python Maintenance/attention.py --file "TEXT" [--urgent] [--source NAME]
                                  [--key KEY]
  python Maintenance/attention.py --list
  python Maintenance/attention.py --clear A-N
Exit codes (tools convention): 0 done; 1 crashed; 2 bad argument, unknown
id, or the file could not be read or written.
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from workspace_common import workspace_root  # noqa: E402

ROOT = workspace_root(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "attention.json")
ABOUT = ("Waiting-on-you queue. Written only through Maintenance/attention.py; "
         "'next' is the next id number, never reused. Each item: id, text, "
         "urgent, source, filed (local clock), key (idempotency).")


def load(path=QUEUE):
    """The queue as a dict; a missing file is an empty queue."""
    if not os.path.exists(path):
        return {"_about": ABOUT, "next": 1, "items": []}
    with open(path, encoding="utf-8") as f:
        q = json.load(f)
    q.setdefault("next", 1)
    q.setdefault("items", [])
    return q


def save(q, path=QUEUE):
    q["_about"] = ABOUT
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(q, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def ordered(items):
    """Urgent first, then oldest filing first."""
    return sorted(items, key=lambda i: (not i.get("urgent"),
                                        str(i.get("filed", "")),
                                        int(str(i.get("id", "A-0"))[2:] or 0)))


def file_item(text, urgent=False, source=None, key=None, path=QUEUE):
    """File one item; return its id (the existing one on a repeat key), or
    None if the write did not land. Never raises."""
    try:
        key = key or text
        q = load(path)
        for it in q["items"]:
            if it.get("key") == key:
                return it["id"]
        iid = "A-%d" % q["next"]
        q["next"] += 1
        q["items"].append({
            "id": iid, "text": text, "urgent": bool(urgent),
            "source": source or "unknown",
            "filed": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "key": key})
        save(q, path)
        return iid
    except Exception:
        return None


def clear(iid, path=QUEUE):
    """Remove one item by id; True if it was there and is now gone."""
    try:
        q = load(path)
        keep = [i for i in q["items"] if i.get("id") != iid]
        if len(keep) == len(q["items"]):
            return False
        q["items"] = keep
        save(q, path)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", metavar="TEXT")
    g.add_argument("--list", action="store_true")
    g.add_argument("--clear", metavar="A-N")
    ap.add_argument("--urgent", action="store_true")
    ap.add_argument("--source")
    ap.add_argument("--key")
    a = ap.parse_args()
    if a.file:
        iid = file_item(a.file, a.urgent, a.source, a.key)
        if not iid:
            print("BROKEN could not write %s" % QUEUE)
            sys.exit(2)
        print("FILED %s" % iid)
    elif a.clear:
        if not clear(a.clear):
            print("BROKEN no open item %s (or the queue is unreadable)"
                  % a.clear)
            sys.exit(2)
        print("CLEARED %s" % a.clear)
    else:
        try:
            items = ordered(load()["items"])
        except (OSError, ValueError) as e:
            print("BROKEN cannot read %s (%s)" % (QUEUE, e))
            sys.exit(2)
        for i in items:
            print("%s%s | %s | %s | %s" % (i["id"], " URGENT" if i.get(
                "urgent") else "", i.get("filed", ""), i.get("source", ""),
                i["text"]))
        print("%d waiting" % len(items))


if __name__ == "__main__":
    main()
