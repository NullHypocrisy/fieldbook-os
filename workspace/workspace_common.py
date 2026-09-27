"""workspace_common.py - helpers every workspace script shares.

Lives at the workspace root, beside workspace.json. Each script puts this
folder on sys.path from its own location and imports from here, so the
scripts work from any current directory. Keep the scripts where the kit
places them; the import depends on that layout.
"""

import os
import sys
from datetime import datetime


def workspace_root(start):
    """Walk up from start to the folder holding workspace.json."""
    p = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(p, "workspace.json")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            sys.exit("workspace.json not found above " + start)
        p = parent


def log_line(log_path, msg):
    """Append a timestamped line to log_path and echo it."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("%s | %s\n" % (stamp, msg))
    print(msg)
