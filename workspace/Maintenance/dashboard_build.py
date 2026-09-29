"""dashboard_build.py - generate the board: one static HTML page of the
workspace's state, read only from the workspace's own files.

Shape: a tab selector, Global plus one tab per Projects/<name>/ folder.
Global opens on a ribbon of tiles - Waiting on you, Work, Memory, Scheduled
pieces, Backups and cleanup, Housekeeping, Bridge - over one glance card
per tile, and every tile and card opens its own drill-down page. Pages are
addressed by URL hash (#home, #g-<tile>, #p-<project>), so back, forward
and copied links work. A project tab renders Projects/<name>/dashboard.json
(format: Projects/README.md); a missing or bad one is a banner on its tab,
never a failed build. Header chips: the doctor's last result and the
installed kit version. Each tab's selector dot shows its worst state.

Marking principle: every not-desired state is marked - amber (warn) when
drifting, red (bad) when it needs the user's hand - and every red state is
ALSO filed to the attention queue under a "board:" key, so nothing
off-nominal appears without being pointed out. A board-filed item whose
state has gone back to normal is cleared by the next build.

Scheduled pieces, the doctor and restore drills are read from the run log,
Scheduled/runs.log, one line per run:
    YYYY-MM-DD HH:MM | task | exit N | result
task is the Scheduled/<task> folder name ("doctor" and "restore-drill" for
those two); the time is the local clock read when the line is written.
A task with no line renders "never run".

Usage:  python Maintenance/dashboard_build.py [--out FILE]
        (default FILE: dashboard.html at the workspace root)
Exit codes (tools convention): 0 built, nothing needs the user; 1 crashed;
2 could not write the page; 3 built, and red states are on it (filed).
"""

import argparse
import csv
import html
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)
from workspace_common import PROJECT_NAME, workspace_root  # noqa: E402
import attention  # noqa: E402

ROOT = workspace_root(HERE)
RUNS = os.path.join(ROOT, "Scheduled", "runs.log")
NOW = datetime.now()
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STALE_DAYS = {"DAILY": 2, "WEEKLY": 8, "daily": 2, "weekly": 8}
BRIDGE_STALE_DAYS = 2
GLANCE_ROWS = 5         # rows a glance card shows; its page shows all
TABLE_ROWS = 100        # rows a file panel shows
TEXT_LINES = 40         # lines a text file panel shows
WORD = {"ok": "OK", "warn": "CHECK", "bad": "PROBLEM", "idle": "QUIET"}
esc = html.escape


def when(dt):
    """today 06:00 / yesterday 06:00 / Fri 06:00 / 2026-09-01."""
    d = (NOW.date() - dt.date()).days
    if d == 0:
        return dt.strftime("today %H:%M")
    if d == 1:
        return dt.strftime("yesterday %H:%M")
    if 1 < d < 7:
        return dt.strftime("%a %H:%M")
    return dt.strftime("%Y-%m-%d")


def age_days(dt):
    return (NOW - dt).total_seconds() / 86400


def kchars(n):
    return ("%.1fk" % (n / 1000.0)).replace(".0k", "k")


def plural(n, word, many=None):
    return "%d %s" % (n, word if n == 1 else (many or word + "s"))


def read(path):
    # utf-8-sig: files saved by Windows tools may start with a byte-order mark.
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def worst(*kinds):
    """The most alarming state; a tile reports its worst, never an average."""
    for k in ("bad", "warn", "idle", "ok"):
        if k in kinds:
            return k
    return "ok"


def more(shown, total, cols=0):
    """The line a capped glance ends with, or nothing."""
    if total <= shown:
        return ""
    t = "+%d more — open for the full list" % (total - shown)
    return ('<tr class="more"><td colspan="%d">%s</td></tr>' % (cols, t)
            if cols else '<div class="note more">%s</div>' % t)


def run_log():
    """task -> (datetime, exit code, result) of its latest line."""
    last = {}
    if not os.path.exists(RUNS):
        return last
    for line in read(RUNS).splitlines():
        parts = [p.strip() for p in line.split("|", 3)]
        if len(parts) < 4:
            continue
        try:
            dt = datetime.strptime(parts[0], "%Y-%m-%d %H:%M")
            code = int(parts[2].split()[-1])
        except (ValueError, IndexError):
            continue
        if parts[1] not in last or dt >= last[parts[1]][0]:
            last[parts[1]] = (dt, code, parts[3])
    return last


def backup_runs():
    """tier -> (status, detail) of its last real run in backup_log.txt."""
    blog = os.path.join(ROOT, "Maintenance", "backup_log.txt")
    last = {}
    if os.path.exists(blog):
        for line in read(blog).splitlines():
            p = [x.strip() for x in line.split("|")]
            if len(p) >= 3 and p[1] in ("daily", "weekly") \
                    and p[2] != "DRY-RUN":
                last[p[1]] = (p[2], " | ".join(p[3:]))
    return last


def latest_snapshot(dest):
    """(datetime, by_name) of dest's newest dated snapshot, or None.

    A folder whose name disagrees with its modification date was copied or
    moved, so its name is the only true date (by_name True).
    """
    snaps = sorted(x for x in os.listdir(dest) if DATED.match(x)
                   and os.path.isdir(os.path.join(dest, x)))
    if not snaps:
        return None
    dt = datetime.fromtimestamp(os.path.getmtime(
        os.path.join(dest, snaps[-1])))
    if snaps[-1] != dt.strftime("%Y-%m-%d"):
        return datetime.strptime(snaps[-1], "%Y-%m-%d"), True
    return dt, False


def work_items():
    """Open work items, priority order: dicts id, name, status, prio,
    project (a spec's first line "project: NAME"; absent means global)."""
    wdir = os.path.join(ROOT, "Work Items")
    rows = []
    for fn in sorted(os.listdir(wdir)) if os.path.isdir(wdir) else []:
        m = re.match(r"^(WI-(\d+))_.*\.md$", fn)
        if not m:
            continue
        text = read(os.path.join(wdir, fn))
        proj = re.match(r"\s*project:\s*(\S+)", text)
        name = re.search(r"^name:\s*(.+)$", text, re.M) or re.search(
            r"^#\s+WI-\d+\s*[—-]+\s*(.+)$", text, re.M)
        status = re.search(r"^\|\s*Status\s*\|\s*(.+?)\s*\|", text, re.M)
        prio = re.search(r"^\|\s*Priority\s*\|.*?\b(P[0-3])\b", text, re.M)
        st = (status.group(1).upper() if status else "UNKNOWN")
        st = "IN PROGRESS" if st.startswith("IN PROGRESS") else st.split()[0]
        rows.append({"prio": prio.group(1) if prio else "P9",
                     "num": int(m.group(2)), "id": m.group(1),
                     "name": name.group(1).strip() if name else fn,
                     "status": st,
                     "project": proj.group(1) if proj else "global"})
    rows.sort(key=lambda r: (r["prio"], r["num"]))
    return rows


def inboxes():
    """{inbox folder: [age in days of each open message]}."""
    bdir = os.path.join(ROOT, "Agent Bridge")
    out = {}
    for box in sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []:
        if not (box.startswith("to-")
                and os.path.isdir(os.path.join(bdir, box))):
            continue
        ages = []
        for f in os.listdir(os.path.join(bdir, box)):
            p = os.path.join(bdir, box, f)
            if not (f.endswith(".md") and os.path.isfile(p)):
                continue
            st = re.search(r"^status:\s*(\S+)", read(p), re.M)
            if st and st.group(1).lower() in ("done", "answered", "closed"):
                continue
            m = re.search(r"_(\d{4}-\d{2}-\d{2})_", f)
            dt = datetime.strptime(m.group(1), "%Y-%m-%d") if m else \
                datetime.fromtimestamp(os.path.getmtime(p))
            ages.append(age_days(dt))
        out[box] = ages
    return out


def projects():
    """Project folder names under Projects/, sorted."""
    pdir = os.path.join(ROOT, "Projects")
    return sorted(d for d in os.listdir(pdir) if re.match(PROJECT_NAME, d)
                  and os.path.isdir(os.path.join(pdir, d))) \
        if os.path.isdir(pdir) else []


def names_project(item, name):
    """True when a queue entry's source or text names the project."""
    pat = r"(?<![\w-])%s(?![\w-])" % re.escape(name)
    return bool(re.search(pat, "%s %s" % (item.get("source", ""),
                                          item.get("text", "")), re.I))


def render_file(path, mode):
    """(html, misfit note or "") for a file panel. JSON list of objects or
    CSV -> table; JSON object -> kv; anything else -> text."""
    raw = read(path)
    ext = os.path.splitext(path)[1].lower()
    shape, rows, data = "text", None, None
    if ext == ".json":
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
            cols = []
            for x in data:
                cols += [k for k in x if k not in cols]
            rows = [cols] + [[x.get(c) for c in cols] for x in data]
            shape = "table"
        elif isinstance(data, dict):
            shape = "kv"
    elif ext == ".csv":
        rows = list(csv.reader(raw.splitlines()))
        shape = "table" if rows else "text"
    mode = mode if mode in ("table", "kv", "text") else shape
    misfit = "" if mode in ("text", shape) else \
        "This file does not fit a %s, so it shows as text." % mode
    mode = shape if misfit else mode

    def cell(v):
        return esc(v if isinstance(v, str) else "" if v is None
                   else json.dumps(v))
    if mode == "table":
        head, body = rows[0], rows[1:]
        out = ['<div class="tw"><table><tr>%s</tr>'
               % "".join("<th>%s</th>" % cell(h) for h in head)]
        out += ["<tr>%s</tr>" % "".join("<td>%s</td>" % cell(v) for v in r)
                for r in body[:TABLE_ROWS]]
        if not body:
            out.append('<tr><td colspan="%d">No rows.</td></tr>'
                       % max(len(head), 1))
        out.append('</table></div>')
        if len(body) > TABLE_ROWS:
            out.append('<div class="note">First %d of %d rows.</div>'
                       % (TABLE_ROWS, len(body)))
        return "".join(out), misfit
    if mode == "kv":
        return ('<table>%s</table>' % "".join(
            '<tr><td class="k">%s</td><td>%s</td></tr>' % (esc(str(k)),
                                                           cell(v))
            for k, v in data.items())), misfit
    lines = raw.splitlines()
    tail = '<div class="note">First %d of %d lines.</div>' % (
        TEXT_LINES, len(lines)) if len(lines) > TEXT_LINES else ""
    return ('<pre class="mono">%s</pre>%s'
            % (esc("\n".join(lines[:TEXT_LINES])), tail)), misfit


class Board:
    def __init__(self):
        self.reds = {}          # key -> (text, urgent)
        self.kinds = []         # states marked in the tile being built
        self.runs = run_log()
        self.pages = []         # drill-down pages
        self.parent = {"home": "home"}
        self.tabs = [("home", "Global")]
        self.tab_kind = {}
        self.deferred = {}      # placeholder -> project, for attention panels
        self._items = None

    def seen(self, kind):
        self.kinds.append(kind)
        return kind

    def flag(self, key, text, urgent=False):
        """Register a red state; returns the id placeholder for the page."""
        self.reds[key] = (text, urgent)
        return "\x00%s\x00" % key

    def dot(self, state, key=None, text=None, urgent=False):
        self.seen(state)
        if state == "bad":
            ph = self.flag(key, text, urgent)
            return '<span class="dot bad" data-attn="%s"></span>' % ph
        return '<span class="dot %s"></span>' % state

    def filed(self, key):
        return " Filed as \x00%s\x00." % key

    def items(self):
        if self._items is None:
            self._items = work_items()
        return self._items

    def page(self, pid, parent, title, body):
        self.parent[pid] = parent
        label = dict(self.tabs).get(parent, "Back")
        self.pages.append(
            '<div class="page" id="page-%s"><div class="crumb"><a href="#%s">'
            '&larr; %s</a><span class="ctx"> · %s</span></div><h2>%s</h2>%s'
            '</div>' % (pid, parent, esc(label), esc(title), esc(title), body))

    # ------------------------------------------------------------ header
    def header(self):
        chips = []
        doc = self.runs.get("doctor")
        if not doc:
            chips.append('<div class="chip warn">Doctor <b>never run</b></div>')
        elif doc[1] == 0:
            chips.append('<div class="chip ok">Doctor <b>PASS</b> · %s</div>'
                         % when(doc[0]))
        elif doc[1] == 3:
            chips.append('<div class="chip warn">Doctor <b>WARN</b> · %s</div>'
                         % when(doc[0]))
        else:
            ph = self.flag("doctor", "The doctor failed its last check - run "
                           "python Maintenance/doctor.py and apply the fix "
                           "it names for each FAIL.")
            chips.append('<div class="chip bad" data-attn="%s">Doctor <b>FAIL'
                         '</b> · %s</div>' % (ph, when(doc[0])))
        vf = os.path.join(ROOT, "VERSION")
        if os.path.exists(vf):
            v = (read(vf).splitlines() or ["?"])[0].strip()
            chips.append('<div class="chip">Kit <b>v%s</b></div>' % esc(v))
        else:
            chips.append('<div class="chip warn">Kit <b>not stamped</b> · '
                         'install unfinished</div>')
        return ('<header>\n  <div class="wordmark">Fieldbook <span>OS</span>'
                '</div>\n  <div class="ws">%s</div>\n  <div class="chips">\n'
                '    %s\n  </div>\n  <div class="stamp">Board generated %s · '
                'static page, regenerate any time</div>\n</header>\n'
                % (esc(ROOT), "\n    ".join(chips),
                   NOW.strftime("%a %Y-%m-%d %H:%M")))

    # -------------------------------------------------------------- tiles
    def tile(self, pid, label, fn):
        """Run one Global section: returns (kind, ribbon tile, glance card)
        and adds its drill-down page. A section that cannot read its
        sources renders a red, filed note instead of failing the page."""
        self.kinds = []
        try:
            r = fn()
        except Exception as e:  # noqa: BLE001 - the page must still build
            k = "unreadable:" + pid
            print("WARN %s: %s: %s" % (label, type(e).__name__, e))
            d = self.dot("bad", k, "The board could not read its %s tile - "
                         "run python Maintenance/dashboard_build.py and fix "
                         "the error it prints." % label)
            note = '<div class="note">%sCould not read: %s.%s</div>' % (
                d, esc(type(e).__name__), self.filed(k))
            r = {"sub": "could not read", "glance": note, "detail": note}
        kind = r.get("kind") or worst(*self.kinds)
        self.page(pid, "home", label, r["detail"])
        rt = ('<a class="lnk" href="#%s"><div class="rt %s"><div class="lab">'
              '%s</div><div class="big">%s</div><div class="sub">%s</div>'
              '</div></a>' % (pid, kind, esc(label),
                              esc(r.get("big") or WORD[kind]),
                              esc(r.get("sub", ""))))
        card = ('<a class="lnk" href="#%s"><div class="card"><h3>%s</h3>%s'
                '<div class="opens">Open %s &rarr;</div></div></a>'
                % (pid, esc(label), r["glance"], esc(label)))
        return kind, rt, card

    # --------------------------------------------------- waiting on you
    @staticmethod
    def attn_list(items, limit=None, empty="Nothing is waiting on you."):
        out = ['<ul class="wl">']
        for i in items[:limit]:
            tag = '<span class="tag urgent">URGENT</span>' if i.get("urgent") \
                else '<span class="tag normal">%s</span>' % esc(i["id"])
            try:
                fdt = when(datetime.strptime(i.get("filed", ""),
                                             "%Y-%m-%d %H:%M"))
            except ValueError:
                fdt = esc(i.get("filed", ""))
            src = "%s%s · %s" % ("%s · " % esc(i["id"]) if i.get("urgent")
                                 else "", "filed by " + esc(
                                     i.get("source", "unknown")), fdt)
            out.append('<li>%s<div>%s<div class="src">%s</div></div></li>'
                       % (tag, esc(i["text"]), src))
        if not items:
            out.append('<li>%s</li>' % esc(empty))
        out.append('</ul>')
        if limit is not None and len(items) > limit:
            out.append(more(limit, len(items)))
        return "".join(out)

    @staticmethod
    def attn_kind(items):
        return "bad" if any(i.get("urgent") for i in items) else \
            ("warn" if items else "ok")

    def waiting(self, items):
        u = sum(1 for i in items if i.get("urgent"))
        return {"kind": self.attn_kind(items), "big": str(len(items)),
                "sub": ("%d urgent" % u) if u else "only you can act on these",
                "glance": self.attn_list(items, GLANCE_ROWS),
                "detail": '<div class="card">%s</div>' % self.attn_list(items)}

    # -------------------------------------------------------------- work
    def work_table(self, rows, project_col=True, limit=None):
        out = ['<table><tr><th>Item</th><th>Name</th>%s<th>Status</th>'
               '<th style="text-align:right">Priority</th></tr>'
               % ("<th>Project</th>" if project_col else "")]
        for r in rows[:limit]:
            cls = "prog" if r["status"] == "IN PROGRESS" else "ready"
            out.append('<tr><td>%s</td><td>%s</td>%s<td><span class="st %s">'
                       '%s</span></td><td class="num">%s</td></tr>'
                       % (r["id"], esc(r["name"]), "<td>%s</td>" % esc(
                           r["project"]) if project_col else "", cls,
                          esc(r["status"]),
                          r["prio"] if r["prio"] != "P9" else "—"))
        cols = 5 if project_col else 4
        if not rows:
            out.append('<tr><td colspan="%d">No open work items.</td></tr>'
                       % cols)
        if limit is not None:
            out.append(more(limit, len(rows), cols))
        out.append('</table>')
        return "".join(out)

    def work(self):
        rows = self.items()
        by = {}
        for r in rows:
            by[r["project"]] = by.get(r["project"], 0) + 1
        glance = "".join('<div class="row"><div>%s</div><div class="r">%s'
                         '</div></div>' % (esc(p), plural(n, "open item"))
                         for p, n in sorted(by.items())) or \
            '<div class="row"><div>No open work items.</div></div>'
        return {"kind": "idle", "big": str(len(rows)),
                "sub": "across %s" % plural(len(by), "project")
                if len(by) > 1 else "open items",
                "glance": glance,
                "detail": '<div class="card">%s</div>'
                          % self.work_table(rows)}

    # ------------------------------------------------------------ memory
    def tenant_row(self, name, t):
        wm = os.path.join(ROOT, t.get("working_memory", ""))
        cap = int(t.get("cap_chars", 0) or 0)
        if not t.get("working_memory") or not os.path.isfile(wm):
            return ('<div class="mem"><div class="t"><div>%s%s</div> <span>'
                    'working-memory file missing</span></div></div>'
                    % (self.dot("warn"), esc(name)))
        n = len(read(wm))
        pct = int(100 * n / cap) if cap else 0
        note, cls = "", ""
        if cap and n > cap:
            note, cls = " — over cap, re-home lines", "warn"
        elif pct >= 75:
            note, cls = " — homing check due", "warn"
        self.seen(cls or "ok")
        return ('<div class="mem"><div class="t">%s <span>%s / %s chars%s'
                '</span></div><div class="bar"><i%s style="width:%d%%"></i>'
                '</div></div>' % (esc(name), kchars(n), kchars(cap), note,
                                  ' class="%s"' % cls if cls else "",
                                  min(pct, 100)))

    def tenants(self):
        reg = json.loads(read(os.path.join(ROOT, "Memory", "tenants.json")))
        return [("global", reg.get("global", {}))] + \
            sorted(reg.get("tenants", {}).items())

    def memory(self):
        rows = [self.tenant_row(n, t) for n, t in self.tenants()]
        db = os.path.join(ROOT, "Memory", "index", "memory.db")
        if not os.path.exists(db):
            idx = ('<div class="note">%sSearch index never built — run '
                   '<code>python Memory/engine/indexer.py</code></div>'
                   % self.dot("warn"))
            sub = "search index never built"
        else:
            built = datetime.fromtimestamp(os.path.getmtime(db))
            con = sqlite3.connect(db)
            try:
                logs = con.execute(
                    "SELECT COUNT(*) FROM files WHERE path LIKE ? OR path "
                    "LIKE ?", ("%/logs/%", "%\\logs\\%")).fetchone()[0]
            finally:
                con.close()
            mark = self.dot("warn") if age_days(built) > 2 else ""
            idx = ('<div class="note">%sSearch index rebuilt %s · %d day-log '
                   'entr%s indexed</div>' % (mark, when(built), logs,
                                             "y" if logs == 1 else "ies"))
            sub = "index rebuilt " + when(built)
        return {"sub": "%s · %s" % (plural(len(rows), "tenant"), sub),
                "glance": "".join(rows[:GLANCE_ROWS])
                + more(GLANCE_ROWS, len(rows)) + idx,
                "detail": '<div class="card">%s%s</div>'
                          % ("".join(rows), idx)}

    # -------------------------------------------------- scheduled pieces
    def scheduled(self):
        sdir = os.path.join(ROOT, "Scheduled")
        tasks = set(d for d in os.listdir(sdir) if os.path.isfile(
            os.path.join(sdir, d, "INSTRUCTIONS.md"))) \
            if os.path.isdir(sdir) else set()
        tasks |= set(self.runs) - {"doctor", "restore-drill"}
        rows, never, failed = [], 0, 0
        for t in sorted(tasks):
            label = esc(t.replace("-", " ").replace("_", " ").capitalize())
            sched = {}
            sj = os.path.join(sdir, t, "schedule.json")
            if os.path.isfile(sj):
                try:
                    sched = json.loads(read(sj))
                except ValueError:
                    sched = {}
            last = self.runs.get(t)
            if not last:
                never += 1
                rows.append((1, '<tr><td>%s%s</td><td>never run</td><td>—'
                             '</td></tr>' % (self.dot("warn"), label)))
                continue
            dt, code, result = last
            tail, rank = "", 2
            if code not in (0, 3):
                failed += 1
                k = "task:%s:failed" % t
                d = self.dot("bad", k, "The scheduled task %s failed on its "
                             "last run (exit %d) - run it by hand from "
                             "Scheduled/%s/ and fix what it reports."
                             % (t, code, t))
                tail, rank = "." + self.filed(k), 0
            elif code == 3 or age_days(dt) > STALE_DAYS.get(
                    sched.get("schedule"), 10 ** 6):
                d, rank = self.dot("warn"), 1
                if code == 0:
                    tail = " (overdue)"
            elif result.lower().startswith(("empty", "nothing")):
                d = self.dot("idle")
            else:
                d = self.dot("ok")
            rows.append((rank, '<tr><td>%s%s</td><td>%s</td><td>%s%s</td>'
                         '</tr>' % (d, label, when(dt), esc(result), tail)))
        head = '<table><tr><th>Task</th><th>Last run</th><th>Result</th></tr>'
        empty = '<tr><td colspan="3">No scheduled pieces installed yet.' \
                '</td></tr>' if not rows else ""
        first = [r for _, r in sorted(rows, key=lambda x: x[0])]
        sub = [plural(len(rows), "task")]
        if failed:
            sub.append("%d failed" % failed)
        if never:
            sub.append("%d never run" % never)
        return {"sub": " · ".join(sub),
                "glance": head + "".join(first[:GLANCE_ROWS]) + empty
                + more(GLANCE_ROWS, len(rows), 3) + '</table>',
                "detail": '<div class="card">%s%s%s</table></div>'
                          % (head, "".join(r for _, r in rows), empty)}

    # ------------------------------------------------ backups and cleanup
    def backups(self):
        cfg = json.loads(read(os.path.join(ROOT, "workspace.json"))) \
            .get("backup", {})
        lastlog = backup_runs()
        out, sub, dests = [], [], []
        for tier in ("daily", "weekly"):
            label = tier.capitalize()
            dest = cfg.get(tier + "_dest")
            if not dest:
                out.append('<div class="row"><div>%s%s</div><div class="r">'
                           'off — no destination</div></div>'
                           % (self.dot("idle"), label))
                continue
            dest = dest if os.path.isabs(dest) else os.path.join(ROOT, dest)
            status, _ = lastlog.get(tier, ("", ""))
            if status in ("CRASH", "REFUSED"):
                k = "backup:%s:failed" % tier
                d = self.dot("bad", k, "The %s backup failed on its last run "
                             "- read Maintenance/backup_log.txt, fix what it "
                             "names, and rerun python Maintenance/backup.py "
                             "--tier %s." % (tier, tier))
                out.append('<div class="row"><div>%s%s</div><div class="r">'
                           'last run %s.%s</div></div>'
                           % (d, label, esc(status), self.filed(k)))
                sub.append("%s failed" % tier)
                continue
            if not os.path.isdir(dest):
                k = "backup:%s:unreachable" % tier
                d = self.dot("bad", k, "The %s backup destination %s is not "
                             "reachable - reconnect it or set a new %s_dest "
                             "in workspace.json." % (tier, dest, tier))
                out.append('<div class="row"><div>%s%s</div><div class="r">'
                           'destination unreachable.%s</div></div>'
                           % (d, label, self.filed(k)))
                sub.append("%s unreachable" % tier)
                continue
            dests.append(dest)
            snap = latest_snapshot(dest)
            if not snap:
                out.append('<div class="row"><div>%s%s</div><div class="r">'
                           'never landed</div></div>'
                           % (self.dot("warn"), label))
                sub.append("%s never landed" % tier)
                continue
            dt, by_name = snap
            shown = when(dt).split()[0] if by_name else when(dt)
            stale = age_days(dt) > STALE_DAYS[tier]
            out.append('<div class="row"><div>%s%s</div><div class="r">%s · %s'
                       '</div></div>' % (self.dot("warn" if stale else "ok"),
                                         label, shown,
                                         "overdue" if stale else "OK"))
            sub.append("%s %s" % (tier, "overdue" if stale else shown))
        self.backups_tail(out, cfg, dests)
        body = "".join(out)
        return {"sub": " · ".join(sub) or "no destination set",
                "glance": body, "detail": '<div class="card">%s</div>' % body}

    def backups_tail(self, out, cfg, dests):
        if not cfg.get("daily_dest") and not cfg.get("weekly_dest"):
            k = "backup:none"
            d = self.dot("bad", k, "No backup destination is set - set "
                         "daily_dest or weekly_dest in workspace.json.")
            out.append('<div class="row"><div>%sDestination</div><div '
                       'class="r">none set.%s</div></div>' % (d, self.filed(k)))
        for dest in sorted(set(dests)):
            u = shutil.disk_usage(dest)
            pct = int(100 * u.used / u.total) if u.total else 0
            if pct >= 90:
                k = "backup:full:" + dest
                d = self.dot("bad", k, "Backup destination %s is %d%% full - "
                             "pick a new destination or clear space."
                             % (dest, pct), urgent=True)
                tail = self.filed(k)
            else:
                d = self.dot("warn") if pct >= 80 else ""
                tail = ""
            out.append('<div class="row"><div>%sDestination</div><div '
                       'class="r">%s · %d%% full%s</div></div>'
                       % (d, esc(dest), pct, tail))
        import restore_drill  # same folder; owns the failure's key and text
        drill = self.runs.get(restore_drill.TASK)
        if not drill:
            out.append('<div class="note">%sLast restore drill: not run yet'
                       '</div>' % self.dot("idle"))
        elif drill[1]:
            k = restore_drill.FAIL_KEY
            d = self.dot("bad", k, restore_drill.FAIL_TEXT)
            out.append('<div class="note">%sLast restore drill: %s · %s.%s'
                       '</div>' % (d, when(drill[0]), esc(drill[2]),
                                   self.filed(k)))
        else:
            out.append('<div class="note">%sLast restore drill: %s · %s</div>'
                       % (self.dot("idle" if drill[2].startswith("nothing")
                                   else "ok"), when(drill[0]),
                          esc(drill[2])))
        cl = self.runs.get("cleanup")
        out.append('<div class="note">Last cleanup: %s</div>' % (
            "%s · %s" % (when(cl[0]), esc(cl[2])) if cl else "not run yet"))

    # ------------------------------------------------------ housekeeping
    def housekeeping(self):
        import cleanup  # same folder; its rules decide expiry and holds
        cooling_days = int(json.loads(read(os.path.join(
            ROOT, "workspace.json"))).get("cleanup", {})
            .get("cooling_days", 14))
        today = NOW.date()
        cooling, past, held, scratch = 0, 0, [], []
        surfaces = None
        for folder in (cleanup.QUARANTINE, cleanup.MANAGED):
            if not os.path.isdir(folder):
                continue
            recorded = cleanup.read_manifest(folder)
            for dirpath, _, files in os.walk(folder):
                for f in files:
                    if f.lower() in cleanup.NEVER_DELETE:
                        continue
                    exp = cleanup.expiry_for(os.path.join(dirpath, f),
                                             recorded, cooling_days)
                    if folder == cleanup.MANAGED:
                        scratch.append(exp)
                    if exp > today:
                        cooling += folder == cleanup.QUARANTINE
                        continue
                    if surfaces is None:
                        surfaces = "".join(
                            read(p).lower()
                            for p in cleanup.load_bearing_files())
                    if cleanup.referenced(f, surfaces):
                        held.append(f)
                    else:
                        past += 1
        out = ['<div class="row"><div>Cooling off</div><div class="r">%s'
               '</div></div>' % plural(cooling, "file")]
        out.append('<div class="row"><div>%sPast expiry</div><div class="r">'
                   '%s%s</div></div>'
                   % (self.dot("warn") if past else "", plural(past, "file"),
                      " · removed at next cleanup" if past else ""))
        if held:
            k = "quarantine:held"
            d = self.dot("bad", k, "%d file(s) past expiry are held because "
                         "something still references them (%s) - remove the "
                         "reference or restore the file."
                         % (len(held), ", ".join(sorted(held)[:5])))
            out.append('<div class="row"><div>%sHeld (your decision)</div>'
                       '<div class="r">%d.%s</div></div>'
                       % (d, len(held), self.filed(k)))
        else:
            out.append('<div class="row"><div>Held (your decision)</div>'
                       '<div class="r">0</div></div>')
        near = (", nearest expiry %s" % min(scratch).strftime("%b %d")
                .replace(" 0", " ")) if scratch else ""
        out.append('<div class="row"><div>Managed scratch</div><div '
                   'class="r">%s%s</div></div>'
                   % (plural(len(scratch), "file"), near))
        body = "".join(out)
        return {"sub": "%d cooling · %d past expiry · %d held"
                       % (cooling, past, len(held)),
                "glance": body, "detail": '<div class="card">%s</div>' % body}

    # ------------------------------------------------------------ bridge
    def inbox_row(self, box, ages):
        if not ages:
            return 2, ('<div class="row"><div>%s%s</div><div class="r">0 '
                       'unread</div></div>' % (self.dot("ok"), esc(box)))
        oldest = int(max(ages))
        stale = max(ages) > BRIDGE_STALE_DAYS
        return (1 if stale else 2), (
            '<div class="row"><div>%s%s</div><div class="r">%d unread · '
            'oldest %s</div></div>' % (
                self.dot("warn" if stale else "ok"), esc(box), len(ages),
                "today" if oldest == 0 else plural(oldest, "day")))

    def bridge(self):
        boxes = inboxes()
        rows = [self.inbox_row(b, a) for b, a in sorted(boxes.items())]
        first = [r for _, r in sorted(rows, key=lambda x: x[0])]
        note = '<div class="note">Unread past %d days is flagged.</div>' \
            % BRIDGE_STALE_DAYS
        empty = '<div class="row"><div>No inboxes yet</div><div class="r">' \
            '—</div></div>' if not rows else ""
        unread = sum(len(a) for a in boxes.values())
        return {"sub": "%d unread in %s" % (unread,
                                            plural(len(boxes), "inbox",
                                                   "inboxes")),
                "glance": "".join(first[:GLANCE_ROWS]) + empty
                + more(GLANCE_ROWS, len(rows)) + note,
                "detail": '<div class="card">%s%s%s</div>'
                          % ("".join(r for _, r in rows), empty, note)}

    # ------------------------------------------------------- project tabs
    def project_tab(self, name):
        """A project's tab from its dashboard.json; returns the page."""
        pid = "p-" + name
        self.kinds = []
        rel = "Projects/%s/dashboard.json" % name
        spec, problem = None, None
        try:
            spec = json.loads(read(os.path.join(ROOT, *rel.split("/"))))
            if not isinstance(spec, dict) or not isinstance(
                    spec.get("panels"), list) or not all(
                    isinstance(p, dict) for p in spec["panels"]):
                problem = "it needs an object with a \"panels\" list"
        except OSError:
            problem = "it is missing"
        except ValueError as e:
            problem = "it is not valid JSON (%s)" % e
        title = str(spec.get("title") or name) if isinstance(spec, dict) \
            else name
        self.tabs.append((pid, title))
        self.parent[pid] = pid
        if problem:
            self.seen("warn")
            body = ('<div class="banner">This tab cannot be drawn: %s is '
                    'unreadable because %s. Fix it to the format in '
                    'Projects/README.md.</div>' % (esc(rel), esc(problem)))
        else:
            cards = []
            for p in spec["panels"]:
                try:
                    cards.append(self.panel(name, p))
                except Exception as e:  # noqa: BLE001 - one panel, not the tab
                    cards.append('<div class="card"><h3>%s</h3><div '
                                 'class="note">%sCould not draw this panel: '
                                 '%s.</div></div>' % (
                                     esc(str(p.get("title") or p.get("type"))),
                                     self.dot("warn"), esc(str(e))))
            body = '<div class="grid">%s</div>' % "".join(cards) if cards \
                else '<div class="note">No panels defined.</div>'
        self.tab_kind[pid] = list(self.kinds)
        return ('<div class="page" id="page-%s"><h2>%s</h2>%s</div>'
                % (pid, esc(title), body))

    def panel(self, name, p):
        typ = p.get("type")
        titles = {"work": "Open work", "memory": "Memory", "inbox": "Inbox",
                  "attention": "Waiting on you"}
        title = esc(str(p.get("title") or titles.get(typ) or typ or "Panel"))
        if typ == "work":
            rows = [r for r in self.items() if r["project"] == name]
            body = self.work_table(rows, project_col=False)
        elif typ == "memory":
            t = dict(self.tenants()).get(name)
            body = self.tenant_row(name, t) if t else (
                '<div class="note">%sNo memory tenant named %s in '
                'Memory/tenants.json.</div>' % (self.dot("warn"), esc(name)))
        elif typ == "inbox":
            box = "to-" + name
            ages = inboxes().get(box)
            body = self.inbox_row(box, ages)[1] if ages is not None else (
                '<div class="note">%sNo inbox: Agent Bridge/%s/ is missing.'
                '</div>' % (self.dot("warn"), esc(box)))
        elif typ == "attention":
            ph = "\x01%d\x01" % len(self.deferred)
            self.deferred[ph] = name
            body = ph
        elif typ == "file":
            body = self.file_panel(name, p)
        else:
            body = ('<div class="note">%sUnknown panel type %s; see '
                    'Projects/README.md.</div>'
                    % (self.dot("warn"), esc(json.dumps(typ))))
        return '<div class="card"><h3>%s</h3>%s</div>' % (title, body)

    def file_panel(self, name, p):
        rel = str(p.get("path") or "")
        full = os.path.abspath(os.path.join(ROOT, rel))
        try:
            inside = bool(rel) and os.path.normcase(os.path.commonpath(
                [full, ROOT])) == os.path.normcase(ROOT)
        except ValueError:
            inside = False
        if not inside:
            return ('<div class="note">%sThe path must be a file inside the '
                    'workspace: %s.</div>' % (self.dot("warn"), esc(rel)))
        if not os.path.isfile(full):
            return ('<div class="note">%sFile not found: %s.</div>'
                    % (self.dot("warn"), esc(rel)))
        body, misfit = render_file(full, p.get("render"))
        if misfit:
            body = '<div class="note">%s%s</div>%s' % (self.dot("warn"),
                                                        esc(misfit), body)
        mt = datetime.fromtimestamp(os.path.getmtime(full))
        limit = p.get("stale_days")
        if isinstance(limit, (int, float)) and not isinstance(limit, bool) \
                and age_days(mt) > limit:
            if p.get("stale_state") == "bad":
                k = "project:%s:stale:%s" % (name, rel)
                d = self.dot("bad", k, "%s (project %s) was last updated %s, "
                             "past its %s-day limit - update it."
                             % (rel, name, when(mt), limit))
                tail = self.filed(k)
            else:
                d, tail = self.dot("warn"), ""
            return body + ('<div class="note">%sStale: updated %s, limit %s '
                           'days.%s</div>' % (d, when(mt), limit, tail))
        return body + '<div class="note">Updated %s</div>' % when(mt)


CSS = """
:root{
  box-sizing:border-box;
  padding-top:env(safe-area-inset-top,0px);
  padding-bottom:env(safe-area-inset-bottom,0px);
  --bg:#f7f5f0; --card:#ffffff; --ink:#22271f; --muted:#6f7568;
  --line:#e4e1d8; --accent:#1f6f46; --ok:#1f7a4d; --warn:#a8730a;
  --bad:#b3382f; --chip:#efece4; --urgent-bg:#fbeeec;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#14171a; --card:#1c2024; --ink:#e7e9e4; --muted:#98a094;
    --line:#2b3036; --accent:#4fae7e; --ok:#4fae7e; --warn:#d59b3a;
    --bad:#d96b62; --chip:#262b30; --urgent-bg:#33231f;
  }
}
:root[data-theme="dark"]{
  --bg:#14171a; --card:#1c2024; --ink:#e7e9e4; --muted:#98a094;
  --line:#2b3036; --accent:#4fae7e; --ok:#4fae7e; --warn:#d59b3a;
  --bad:#d96b62; --chip:#262b30; --urgent-bg:#33231f;
}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
*{box-sizing:inherit}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:26px 16px 56px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 18px;
  border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:0}
.wordmark{font-family:Georgia,"Times New Roman",serif;font-size:26px;
  font-weight:700;letter-spacing:.2px}
.wordmark span{color:var(--accent)}
.ws{color:var(--muted);font-size:13px;overflow-wrap:anywhere}
.chips{margin-left:auto;display:flex;flex-wrap:wrap;gap:8px}
.chip{background:var(--chip);border:1px solid var(--line);border-radius:999px;
  padding:3px 11px;font-size:12.5px;white-space:nowrap}
.chip b{font-weight:600}
.chip.ok b{color:var(--ok)} .chip.warn b{color:var(--warn)}
.chip.bad b{color:var(--bad)}
.stamp{width:100%;color:var(--muted);font-size:12.5px}
.nav{display:flex;flex-wrap:wrap;gap:2px;border-bottom:1px solid var(--line);
  margin:0 0 18px;position:sticky;top:0;background:var(--bg);z-index:5}
.nav a{padding:9px 13px;font-size:13.5px;font-weight:600;color:var(--muted);
  text-decoration:none;border-bottom:2px solid transparent}
.nav a:hover{color:var(--ink)}
.nav a.active{color:var(--ink);border-bottom-color:var(--accent)}
.tabdot{display:inline-block;width:7px;height:7px;border-radius:50%;
  margin-left:7px;vertical-align:middle;background:var(--muted)}
.tabdot.ok{background:var(--ok)} .tabdot.warn{background:var(--warn)}
.tabdot.bad{background:var(--bad)}
.page{display:none} .page.show{display:block}
h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);margin:0 0 12px;font-weight:600}
.card h3{font-size:14.5px;margin:0 0 8px;font-weight:600}
a.lnk{text-decoration:none;color:inherit;display:block;min-width:0}
a.lnk .card,a.lnk .rt{transition:border-color .12s}
a.lnk:hover .card,a.lnk:hover .rt{border-color:var(--accent)}
.opens{font-size:12.5px;color:var(--accent);margin-top:10px;font-weight:600}
.ribbon{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:10px;margin-bottom:16px}
.ribbon a.lnk{display:flex}
.rt{flex:1;background:var(--card);border:1px solid var(--line);
  border-radius:10px;padding:8px 12px 9px 15px;position:relative;
  overflow:hidden}
.rt:before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;
  background:var(--muted)}
.rt.ok:before{background:var(--ok)} .rt.warn:before{background:var(--warn)}
.rt.bad:before{background:var(--bad)}
.rt .lab{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);font-weight:600}
.rt .big{font-size:21px;font-weight:700;line-height:1.25}
.rt.ok .big{color:var(--ok)} .rt.warn .big{color:var(--warn)}
.rt.bad .big{color:var(--bad)}
.rt .sub{font-size:12px;color:var(--muted);line-height:1.3}
.cols{display:grid;gap:16px;align-items:start;
  grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
@media (min-width:1000px){.cols{grid-template-columns:repeat(3,1fr)}}
.col{display:flex;flex-direction:column;gap:16px;min-width:0}
@media (max-width:660px){.cols{display:flex;flex-direction:column}
  .col{display:contents}}
.hint{color:var(--muted);font-size:12.5px;margin-top:16px}
.crumb{font-size:13px;margin:0 0 8px}
.crumb a{color:var(--accent);text-decoration:none;font-weight:600}
.crumb .ctx{color:var(--muted)}
.banner{border:1px solid var(--warn);color:var(--warn);border-radius:8px;
  padding:9px 12px;font-size:14px;font-weight:600;background:var(--card)}
.wl{margin:0;padding:0;list-style:none;display:grid;gap:9px}
.wl li{display:flex;gap:10px;align-items:baseline}
.tag{font-size:11px;font-weight:700;letter-spacing:.05em;border-radius:5px;
  padding:1px 7px;white-space:nowrap}
.tag.urgent{background:var(--urgent-bg);color:var(--bad)}
.tag.normal{background:var(--chip);color:var(--muted)}
.wl .src{color:var(--muted);font-size:12.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:15px 17px;min-width:0}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--muted);font-weight:600;font-size:12px;
  letter-spacing:.05em;text-transform:uppercase;padding:4px 8px 6px 0}
td{padding:6px 8px 6px 0;border-top:1px solid var(--line);vertical-align:top;
  overflow-wrap:anywhere}
td.num{text-align:right;white-space:nowrap}
td.k{color:var(--muted);white-space:nowrap}
tr.more td,.note.more{color:var(--muted);font-style:italic}
.tw{overflow-x:auto}
.st{font-size:12px;font-weight:600;border-radius:5px;padding:1px 7px;white-space:nowrap}
.st.prog{background:var(--chip);color:var(--accent)}
.st.ready{background:var(--chip);color:var(--muted)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px;
  vertical-align:baseline}
.dot.ok{background:var(--ok)} .dot.warn{background:var(--warn)} .dot.idle{background:var(--muted)}
.dot.bad{background:var(--bad)}
.row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;
  border-top:1px solid var(--line);font-size:14px}
.row:first-of-type{border-top:0}
.row .r{color:var(--muted);text-align:right;overflow-wrap:anywhere}
.bar{height:7px;background:var(--chip);border-radius:99px;overflow:hidden;margin-top:5px}
.bar i{display:block;height:100%;background:var(--accent);border-radius:99px}
.bar i.warn{background:var(--warn)}
.mem{padding:7px 0;border-top:1px solid var(--line)}
.mem:first-of-type{border-top:0}
.mem .t{display:flex;justify-content:space-between;gap:10px;font-size:14px}
.mem .t span{color:var(--muted);font-size:12.5px}
.note{color:var(--muted);font-size:12.5px;margin-top:9px}
pre.mono{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;
  font:12.5px/1.45 Consolas,Menlo,monospace}
footer{margin-top:26px;color:var(--muted);font-size:12.5px;display:flex;
  flex-wrap:wrap;gap:6px 18px}
code{background:var(--chip);border-radius:5px;padding:1px 6px;font-size:12.5px}
"""

# Hash router: shows the page the address names (home when it names none),
# lights its tab, and keeps back/forward and copied links working. Inline,
# so the page stays one self-contained file.
JS = """
(function(){
  var PARENT = %s;
  function route(){
    var h = (location.hash || '#home').slice(1);
    if (!PARENT.hasOwnProperty(h)) { h = 'home'; }
    var pages = document.querySelectorAll('.page');
    for (var i = 0; i < pages.length; i++) {
      pages[i].className = 'page' + (pages[i].id === 'page-' + h ? ' show' : '');
    }
    var tabs = document.querySelectorAll('.nav a');
    for (var j = 0; j < tabs.length; j++) {
      tabs[j].className = tabs[j].id === 'nav-' + PARENT[h] ? 'active' : '';
    }
    window.scrollTo(0, 0);
  }
  window.addEventListener('hashchange', route);
  route();
})();
"""


def columns(cards, n=3):
    """Glance cards round-robin into n self-packing columns."""
    n = max(1, min(n, len(cards)))
    # The order style puts the cards back in tile order when a narrow
    # screen collapses the columns into one (see .cols in CSS).
    cards = [c.replace('<a class="lnk"', '<a class="lnk" style="order:%d"'
                       % i, 1) for i, c in enumerate(cards)]
    cols = [cards[i::n] for i in range(n)]
    return '<div class="cols">%s</div>' % "".join(
        '<div class="col">%s</div>' % "".join(c) for c in cols)


def build(out_path):
    b = Board()
    try:
        head = b.header()
    except Exception as e:  # noqa: BLE001 - the page must still build
        print("WARN header: %s: %s" % (type(e).__name__, e))
        head = '<header><div class="wordmark">Fieldbook <span>OS</span>' \
               '</div></header>'
    sections = [("g-waiting", "Waiting on you", None),
                ("g-work", "Work", b.work), ("g-memory", "Memory", b.memory),
                ("g-scheduled", "Scheduled pieces", b.scheduled),
                ("g-backups", "Backups and cleanup", b.backups),
                ("g-housekeeping", "Housekeeping", b.housekeeping),
                ("g-bridge", "Bridge", b.bridge)]
    built = {pid: b.tile(pid, label, fn)
             for pid, label, fn in sections if fn}
    tabs = [b.project_tab(n) for n in projects()]

    # File every red state, then clear board-filed items now back to normal.
    ids = {}
    for k, (text, urgent) in b.reds.items():
        ids[k] = attention.file_item(text, urgent, "dashboard",
                                     "board:" + k) or "not filed"
    try:
        q = attention.load()
    except (OSError, ValueError):
        q = {"items": []}
    for it in q["items"]:
        key = str(it.get("key", ""))
        if key.startswith("board:") and key[6:] not in b.reds:
            attention.clear(it["id"])
    try:
        items = attention.ordered(attention.load()["items"])
    except (OSError, ValueError):
        items = []

    # What reads the queue renders last, so it shows this build's filings.
    built["g-waiting"] = b.tile("g-waiting", "Waiting on you",
                                lambda: b.waiting(items))
    order = [pid for pid, _, _ in sections]
    ribbon = '<div class="ribbon">%s</div>' % "".join(
        built[p][1] for p in order)
    home = ('<div class="page" id="page-home">%s%s<p class="hint">Every tile '
            'and card opens its own page.</p></div>'
            % (ribbon, columns([built[p][2] for p in order])))
    # Work is neutral by design and never colours the Global dot.
    kinds = {"home": worst(*[built[p][0] for p in order if p != "g-work"]
                           + ["bad" if "doctor" in b.reds else "ok"])}
    body_tabs = "".join(tabs)
    for ph, name in b.deferred.items():
        mine = [i for i in items if names_project(i, name)]
        b.tab_kind["p-" + name].append(b.attn_kind(mine))
        body_tabs = body_tabs.replace(ph, b.attn_list(
            mine, empty="Nothing is waiting on you for this project."))
    for pid, ks in b.tab_kind.items():
        kinds[pid] = worst(*ks)
    nav = '<nav class="nav">%s</nav>' % "".join(
        '<a id="nav-%s" href="#%s">%s<span class="tabdot %s"></span></a>'
        % (pid, pid, esc(label), kinds.get(pid, "ok"))
        for pid, label in b.tabs)

    body = "\n".join([head, nav, home, body_tabs] + b.pages)
    for k, iid in ids.items():
        body = body.replace("\x00%s\x00" % k, esc(iid))
    page = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">'
            '\n<meta name="viewport" content="width=device-width, '
            'initial-scale=1, viewport-fit=cover">\n<title>Fieldbook OS — '
            'Board</title>\n<style>%s</style>\n<noscript><style>.page{display:'
            'block;margin-bottom:28px}</style></noscript>\n</head>\n<body>\n'
            '<div class="wrap">\n%s\n<footer>\n  <div>Regenerate: <code>python '
            'Maintenance/dashboard_build.py</code></div>\n  <div>Everything '
            'above is read from your own files — nothing leaves this machine.'
            '</div>\n</footer>\n</div>\n<script>%s</script>\n</body>\n</html>\n'
            % (CSS, body, JS % json.dumps(b.parent, sort_keys=True)))
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page)
    os.replace(tmp, out_path)
    return b.reds, ids, items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "dashboard.html"))
    a = ap.parse_args()
    try:
        reds, ids, items = build(os.path.abspath(a.out))
    except OSError as e:
        print("BROKEN could not write the board: %s" % e)
        sys.exit(2)
    print("BUILT %s | %d red (filed %s) | %d waiting on you"
          % (a.out, len(reds), ", ".join(sorted(set(ids.values()))) or "-",
             len(items)))
    sys.exit(3 if reds else 0)


if __name__ == "__main__":
    main()
