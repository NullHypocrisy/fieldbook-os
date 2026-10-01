"""smoke_test.py - prove the installation works, end to end.

Works in a throwaway temp folder, so the real workspace is untouched. The
copy is a simulated fresh install: only the files the install manifest
lists (the kit's own file list inside the kit), never the adopter's
bridge messages, work items, memory logs or project folders, and none of
the runtime state the checks start without. The board
is built on the fresh copy (every section in its empty state), on the
populated tree, and with projects added by new_project.py (custom
panels fresh and stale, one broken tab definition, one name typed with
spaces). The procedure trigger index is regenerated, extended and
broken on purpose. Every scheduled task's precheck proves EMPTY on the
fresh copy and WORK on a planted case, and the wrappers run. The restore
drill passes on a real snapshot and fails on a planted corruption. Then the
doctor runs on a populated install (every check
PASS), writes its diagnostic report there (planted sidecar, byte-order mark,
odd journal line and fake .env key) and composes an issue body from it, and
runs on deliberately broken installs (each break named, with its fix);
that part is skipped when the doctor itself started this run.
Prints PASS/FAIL per check and exits nonzero on any failure.

Usage:  python Maintenance/smoke_test.py   (from anywhere)
"""

import fnmatch
import getpass
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from workspace_common import (JOURNAL, MANIFEST, MARK_BEGIN,  # noqa: E402
                              MARK_END, PROJECT_TEMPLATE, RULE_KEYS,
                              SMOKE_NESTED, git,
                              git_identity, manifest_text, project_files,
                              workspace_root)


SRC = workspace_root(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []
# Runtime state a fresh installation does not have yet.
RUNTIME = ("__pycache__", ".git", "memory.db", "*.log", "*_log.txt",
           "attention.json", "dashboard.html", "VERSION")
# Amber states the board also files (dashboard_build.py, marking principle).
NOTICES = ("board:backup:none",)


def ignore_rules():
    """[(pattern, anchored, dir_only)] git would apply to the workspace."""
    rules = []
    sources = [(os.path.join(SRC, ".gitignore"), "")]
    if os.path.exists(os.path.join(SRC, "..", "install.py")):
        sources.append((os.path.join(SRC, "..", ".gitignore"), "workspace/"))
    for gi, prefix in sources:
        if not os.path.exists(gi):
            continue
        for line in open(gi, encoding="utf-8"):
            pat = line.strip()
            if not pat or pat.startswith("#"):
                continue
            dir_only = pat.endswith("/")
            pat = pat.rstrip("/").lstrip("/")
            anchored = "/" in pat
            if anchored and prefix:
                if not pat.startswith(prefix):
                    continue
                pat = pat[len(prefix):]
            rules.append((pat, anchored, dir_only))
    rules += [(p, False, False) for p in RUNTIME]
    return rules


def clone_list(src):
    """Workspace-relative paths a fresh install of src holds: the install
    manifest's files plus the installer's .gitignore and project template
    in an installed workspace; the kit's own file list (what install.py
    copies) inside the kit; None for a workspace with neither."""
    extra = [".gitignore", PROJECT_TEMPLATE]
    mp = os.path.join(src, *MANIFEST.split("/"))
    if os.path.exists(mp):
        with open(mp, encoding="utf-8-sig") as f:
            return json.load(f)["files"] + extra
    kit = os.path.abspath(os.path.join(src, ".."))
    if os.path.exists(os.path.join(kit, "install.py")):
        sys.path.insert(0, kit)
        import install
        return [r.replace("\\", "/") for r in install.kit_files()] + extra
    return None


def scaffold_projects(ws):
    """Give each project tenant the copy's tenants.json names, and whose
    working memory the copy lacks, the fresh files a new project gets."""
    tp = os.path.join(ws, *PROJECT_TEMPLATE.split("/"))
    try:
        with open(os.path.join(ws, "Memory", "tenants.json"),
                  encoding="utf-8") as f:
            names = sorted(json.load(f).get("tenants", {}))
        with open(tp, encoding="utf-8") as f:
            template = f.read()
    except (OSError, ValueError):
        return
    for name in names:
        if os.path.exists(os.path.join(ws, "Memory", name,
                                       "working-memory.md")):
            continue
        for rel, text in project_files(name, template).items():
            to = os.path.join(ws, *rel.split("/"))
            os.makedirs(os.path.dirname(to), exist_ok=True)
            with open(to, "w", encoding="utf-8") as f:
                f.write(text)


def fresh_clone(src, dest):
    """Copy what a fresh install of src would hold into dest: only the
    files clone_list names, never the adopter's own content (bridge
    messages, work items, memory logs, project folders), each project
    re-scaffolded fresh. A workspace with no manifest falls back to what a
    git clone would carry."""
    rels = clone_list(src)
    if rels is None:
        return walk_clone(src, dest)
    for rel in rels:
        frm = os.path.join(src, *rel.split("/"))
        if not os.path.isfile(frm) or any(fnmatch.fnmatch(
                rel.rsplit("/", 1)[-1], p) for p in RUNTIME):
            continue
        to = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(to), exist_ok=True)
        shutil.copy2(frm, to)
    scaffold_projects(dest)


def walk_clone(src, dest):
    """Copy what a fresh git clone of src would hold into dest."""
    rules = ignore_rules()

    def ignored(rel, is_dir):
        name = rel.rsplit("/", 1)[-1]
        return any(fnmatch.fnmatch(rel if anch else name, pat)
                   for pat, anch, dir_only in rules
                   if is_dir or not dir_only)
    for dirpath, dirnames, files in os.walk(src):
        relroot = os.path.relpath(dirpath, src).replace("\\", "/")
        relroot = "" if relroot == "." else relroot + "/"
        dirnames[:] = [d for d in dirnames if not ignored(relroot + d, True)]
        for fn in files:
            if ignored(relroot + fn, False):
                continue
            to = os.path.join(dest, relroot, fn)
            os.makedirs(os.path.dirname(to), exist_ok=True)
            shutil.copy2(os.path.join(dirpath, fn), to)


def rmtree(p):
    """Remove a tree, clearing the read-only bit git sets on objects."""
    def fix(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if sys.version_info >= (3, 12):
        shutil.rmtree(p, onexc=fix)
    else:
        shutil.rmtree(p, onerror=fix)


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        (" - " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(ws, *args):
    r = subprocess.run([sys.executable] + list(args), cwd=ws,
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


TILES = (("g-waiting", "Waiting on you"), ("g-work", "Work"),
         ("g-memory", "Memory"), ("g-scheduled", "Scheduled pieces"),
         ("g-backups", "Backups and cleanup"),
         ("g-housekeeping", "Housekeeping"), ("g-bridge", "Bridge"))
# The ribbon's labelled tiles, left to right; the Work tile ends the ribbon
# with its own headline pair instead of a label. Every section has a card.
RIBBON_LABELS = ["Waiting on you", "Scheduled pieces", "Backups and cleanup",
                 "Memory"]
DESIGN_CLASSES = ('class="brand"', 'class="chips"', 'class="stamp"',
                  'class="nav"', 'id="nav-home"', 'class="ribbon"',
                  'class="rt ', 'class="heads"', 'class="wrow ',
                  'class="cols"', 'class="lnk"', 'class="stack"',
                  'class="legend"', 'class="gbars"', 'class="tcell ',
                  'class="crumb"', 'class="card"', 'class="row"',
                  'class="mem"', 'class="bar"', 'class="note"',
                  'class="dot ', "<footer>")


def board(ws, label):
    """Build the board in ws; assert structure and the marking principle.
    Returns (page text, queue items)."""
    rc, out = run(ws, os.path.join("Maintenance", "dashboard_build.py"))
    page_path = os.path.join(ws, "dashboard.html")
    check("board %s: builds, no traceback" % label, rc in (0, 3)
          and "Traceback" not in out and os.path.exists(page_path), out)
    page = open(page_path, encoding="utf-8").read() \
        if os.path.exists(page_path) else ""
    ribbon = page.split('class="ribbon"', 1)[-1].split('class="cols"')[0]
    missing = [c for c in DESIGN_CLASSES if c not in page]
    check("board %s: Global tiles in order, each with its page" % label,
          not missing
          and re.findall(r'<div class="lab">([^<]*)<', ribbon)
          == RIBBON_LABELS
          and ribbon.rfind('class="heads"') > ribbon.rfind('class="lab"')
          and all('id="page-%s"' % p in page and page.count('href="#%s"' % p)
                  >= 1 for p, _ in TILES)
          and all(page.count('href="#%s"' % p) >= 2 for p, _ in TILES
                  if p not in ("g-housekeeping", "g-bridge")),
          missing or out)
    pdir = os.path.join(ws, "Projects")
    projects = sorted(d for d in os.listdir(pdir) if os.path.isdir(
        os.path.join(pdir, d))) if os.path.isdir(pdir) else []
    check("board %s: Global plus one tab per project" % label,
          re.findall(r'<a id="nav-([^"]+)"', page)
          == ["home"] + ["p-" + p for p in projects], projects)
    check("board %s: single file, no external assets" % label,
          not re.search(r'(src|href)="(https?:)?//|<link |<script[^>]*src',
                        page))
    qp = os.path.join(ws, "attention.json")
    items = json.load(open(qp, encoding="utf-8"))["items"] \
        if os.path.exists(qp) else []
    ids = {i["id"] for i in items}
    marks = set(re.findall(
        r'class="(?:dot|chip) bad"[^>]*?data-attn="([^"]*)"', page))
    bare = re.findall(r'class="(?:dot|chip) bad"(?![^>]*data-attn)', page)
    board_filed = {i["id"] for i in items if i["key"].startswith("board:")
                   and i["key"] not in NOTICES}
    check("board %s: every red state is filed" % label, not bare
          and marks == board_filed, (sorted(marks), sorted(ids)))
    return page, items


def projects_checks(ws):
    """Projects: new_project.py creates, dry-runs and never overwrites; a
    tab renders standard and custom panels; stale is amber, or red and
    filed when the definition says so; a broken definition is a banner."""
    tp = os.path.join(ws, *PROJECT_TEMPLATE.split("/"))
    kit_tp = os.path.join(SRC, "..", "tiers", "project.md")
    if not os.path.exists(tp) and os.path.exists(kit_tp):
        os.makedirs(os.path.dirname(tp), exist_ok=True)
        shutil.copy2(kit_tp, tp)
    np = os.path.join("Maintenance", "new_project.py")
    ten = os.path.join(ws, "Memory", "tenants.json")
    before = open(ten, encoding="utf-8").read()
    rc, out = run(ws, np, "smoke-alpha", "--dry-run")
    check("projects: dry-run plans, writes nothing", rc == 0
          and "PLAN  write Projects/smoke-alpha/PROJECT.md" in out
          and not os.path.exists(os.path.join(ws, "Projects", "smoke-alpha"))
          and open(ten, encoding="utf-8").read() == before, out)
    for name in ("smoke-alpha", "smoke-beta"):
        rc, out = run(ws, np, name)
        check("projects: %s created" % name, rc == 0 and "CREATED" in out
              and name in json.load(open(ten, encoding="utf-8"))["tenants"]
              and all(os.path.exists(os.path.join(ws, *p.split("/"))) for p in (
                  "Projects/%s/PROJECT.md" % name,
                  "Projects/%s/dashboard.json" % name,
                  "Memory/%s/working-memory.md" % name,
                  "Agent Bridge/to-%s" % name)), out)
    pa = os.path.join(ws, "Projects", "smoke-alpha")
    rules = open(os.path.join(pa, "PROJECT.md"), encoding="utf-8").read()
    check("projects: rules file filled from the template",
          rules.startswith("# smoke-alpha") and "{PROJECT}" not in rules,
          rules[:80])
    open(os.path.join(pa, "PROJECT.md"), "a", encoding="utf-8").write("mine\n")
    rc, out = run(ws, np, "smoke-alpha")
    check("projects: rerun refuses to overwrite (held, exit 3)", rc == 3
          and "KEPT Projects/smoke-alpha/PROJECT.md" in out and open(
              os.path.join(pa, "PROJECT.md"), encoding="utf-8").read()
          .endswith("mine\n"), out)
    rc, out = run(ws, np, "global")
    check("projects: a bad name is refused (exit 2)", rc == 2, out)
    rc, out = run(ws, np, "Raised Bed Garden")
    rbg = os.path.join(ws, "Projects", "Raised-Bed-Garden", "dashboard.json")
    check("projects: a typed name with spaces gets a folder-safe short "
          "name, the tab keeps the typed name", rc == 0
          and os.path.exists(rbg) and json.load(open(
              rbg, encoding="utf-8")).get("title") == "Raised Bed Garden"
          and "Raised-Bed-Garden" in json.load(open(
              ten, encoding="utf-8"))["tenants"]
          and os.path.isdir(os.path.join(ws, "Agent Bridge",
                                         "to-Raised-Bed-Garden")), out)

    json.dump([{"crop": "beans", "kg": 3}, {"crop": "kale", "kg": 1}],
              open(os.path.join(pa, "harvest.json"), "w"))
    open(os.path.join(pa, "notes.md"), "w").write("tomatoes staked\n")
    stale = os.path.join(pa, "plan.csv")
    open(stale, "w").write("week,task\n1,sow\n")
    old = (datetime.now() - timedelta(days=30)).timestamp()
    os.utime(stale, (old, old))
    old_kv = os.path.join(pa, "gear.json")
    json.dump({"hoe": "ok"}, open(old_kv, "w"))
    os.utime(old_kv, (old, old))
    rel = "Projects/smoke-alpha/"
    json.dump({"title": "Smoke Alpha", "panels": [
        {"type": "work"}, {"type": "attention"}, {"type": "memory"},
        {"type": "inbox"},
        {"type": "file", "title": "Harvest", "path": rel + "harvest.json",
         "render": "table", "stale_days": 7},
        {"type": "file", "title": "Notes", "path": rel + "notes.md",
         "render": "text"},
        {"type": "file", "title": "Plan", "path": rel + "plan.csv",
         "render": "table", "stale_days": 7, "stale_state": "bad"},
        {"type": "file", "title": "Gear", "path": rel + "gear.json",
         "render": "kv", "stale_days": 7},
        {"type": "file", "title": "Gone", "path": rel + "missing.csv"}]},
        open(os.path.join(pa, "dashboard.json"), "w"))
    with open(os.path.join(ws, "Work Items", "WI-07_alpha-task.md"), "w",
              encoding="utf-8") as f:
        f.write("project: smoke-alpha\nname: alpha project task\n\n# WI-07 - "
                "x\n\n| Field | Value |\n|---|---|\n| Status | OPEN |\n")
    run(ws, os.path.join("Maintenance", "attention.py"), "--file",
        "Pick seeds for smoke-alpha.", "--source", "smoke")
    open(os.path.join(ws, "Projects", "smoke-beta", "dashboard.json"),
         "w").write("{not json")

    page, items = board(ws, "projects")
    tab = page.split('id="page-p-smoke-alpha"', 1)[-1].split(
        '<div class="page"', 1)[0]
    check("projects: tab shows standard and custom panels", all(s in tab for s in (
        "alpha project task", "Pick seeds for smoke-alpha.",
        "smoke-alpha <span>", "to-smoke-alpha", "<th>crop</th>",
        "<td>beans</td>", "tomatoes staked", "<td>sow</td>",
        '<td class="k">hoe</td>', "File not found: " + rel + "missing.csv"))
          and "Smoke Alpha" in page, tab[-2000:])
    check("projects: stale file amber, or red and filed as defined",
          re.search(r'dot warn"></span>Stale: updated [^<]*limit 7 days\.'
                    r'</div>', tab.split("Gear", 1)[-1])
          and any(i["key"] == "board:project:smoke-alpha:stale:" + rel
                  + "plan.csv" for i in items)
          and "Stale:" not in tab.split("Harvest", 1)[-1].split("Notes")[0],
          tab[-2000:])
    beta = page.split('id="page-p-smoke-beta"', 1)[-1].split(
        '<div class="page"', 1)[0]
    check("projects: the tab is labelled with the typed name",
          'href="#p-Raised-Bed-Garden">Raised Bed Garden<' in page)
    check("projects: a broken dashboard.json is a banner, not a traceback",
          'class="banner"' in beta and "not valid JSON" in beta, beta[:500])
    check("projects: work stays out of other tabs, global lists it",
          "alpha project task" not in beta
          and "alpha project task" in page.split('id="page-g-work"')[1])


RUN_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} \| [\w.-]+ \| exit \d+ "
                      r"\| \S.*$")


def tasks(ws):
    """The scheduled tasks installed in ws: folders holding INSTRUCTIONS.md."""
    sdir = os.path.join(ws, "Scheduled")
    return sorted(d for d in os.listdir(sdir) if os.path.isfile(
        os.path.join(sdir, d, "INSTRUCTIONS.md"))) \
        if os.path.isdir(sdir) else []


def run_prechecks(ws):
    """Every task's precheck; {task: (exit code, output)}."""
    return {t: run(ws, os.path.join("Scheduled", t, "precheck.py"))
            for t in tasks(ws)}


def runs_lines(ws):
    p = os.path.join(ws, "Scheduled", "runs.log")
    return open(p, encoding="utf-8").read().splitlines() \
        if os.path.exists(p) else []


def scheduled_checks(tmp):
    """Each task's precheck: EMPTY on a bare install, WORK on a planted
    case; the wrappers run and every line lands in the run-log format."""
    ws = os.path.join(tmp, "sched")
    fresh_clone(SRC, ws)
    cfgp = os.path.join(ws, "workspace.json")
    cfg = json.load(open(cfgp, encoding="utf-8"))
    cfg["backup"].update(daily_dest=None, weekly_dest=None)
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), indent=2)
    shipped = tasks(ws)
    want = ["backup-daily", "backup-weekly", "bridge-reader", "cleanup",
            "memory-sweep", "work-item-launcher"]
    check("scheduled: every task ships instructions, precheck and schedule",
          shipped == want and all(os.path.exists(os.path.join(
              ws, "Scheduled", t, f)) for t in shipped
              for f in ("precheck.py", "schedule.json")), shipped)
    res = run_prechecks(ws)
    lines = runs_lines(ws)
    check("scheduled bare: every precheck EMPTY, exit 0",
          all(rc == 0 and out == "EMPTY" for rc, out in res.values()), res)
    check("scheduled bare: one empty line per task, in the run-log format",
          len(lines) == len(shipped) and all(RUN_LINE.match(x)
                                             and "| exit 0 | empty: " in x
                                             for x in lines), lines)

    def pre(t):
        return run(ws, os.path.join("Scheduled", t, "precheck.py"))

    def wrap(t):
        return run(ws, os.path.join("Scheduled", t, "run.py"))

    # Launcher: marked, waiting, priority, ranking, resume.
    wid = os.path.join(ws, "Work Items")

    def spec(n, slug, rows, extra=""):
        with open(os.path.join(wid, "WI-%02d_%s.md" % (n, slug)), "w",
                  encoding="utf-8") as f:
            f.write("project: global\n\n# WI-%02d - %s\n\n| Field | Value |"
                    "\n|---|---|\n%s\n%s" % (n, slug, "".join(
                        "| %s | %s |\n" % r for r in rows), extra))
    spec(3, "waits", [("Run", "launcher"), ("Priority", "P0"),
                      ("Depends on", "WI-04 lands first")])
    spec(4, "unmarked", [("Priority", "P0")])
    spec(5, "later", [("Run", "launcher"), ("Priority", "P2")])
    spec(6, "sooner", [("Run", "launcher"), ("Priority", "P1")])
    rc, out = pre("work-item-launcher")
    check("launcher: marked item picked by priority, waiting one skipped",
          rc == 0 and out.startswith("WORK WI-06_sooner.md")
          and "1 waiting" in out, out)
    open(os.path.join(wid, "scores.md"), "w").write("1. WI-05\n2. WI-06\n")
    rc, out = pre("work-item-launcher")
    check("launcher: scores file order wins over priority",
          out.startswith("WORK WI-05_later.md"), out)
    spec(6, "sooner", [("Run", "launcher"), ("Priority", "P1")],
         "\n## Progress\n\nHalf done.\n")
    rc, out = pre("work-item-launcher")
    check("launcher: a run that stopped partway resumes first",
          out.startswith("WORK WI-06_sooner.md") and "resuming" in out, out)

    # Bridge reader: an open message is WORK and, being old, is filed.
    old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    msg = os.path.join(ws, "Agent Bridge", "to-global",
                       "FROM-smoke_%s_ask.md" % old)
    open(msg, "w", encoding="utf-8").write(
        "---\nfrom: smoke\nkind: question\nstatus: open\n---\nask\n")
    rc, out = pre("bridge-reader")
    qp = os.path.join(ws, "attention.json")

    def keys():
        return [i["key"] for i in json.load(open(qp, encoding="utf-8"))[
            "items"]] if os.path.exists(qp) else []
    stale_key = "bridge:stale:to-global/" + os.path.basename(msg)
    check("bridge: open message is WORK", rc == 0
          and out == "WORK 1 open message(s) in to-global", out)
    check("bridge: stale message filed to the attention queue once",
          keys().count(stale_key) == 1 and pre("bridge-reader")[0] == 0
          and keys().count(stale_key) == 1, keys())
    open(msg, "w", encoding="utf-8").write(
        "---\nfrom: smoke\nkind: question\nstatus: answered\n---\nask\n")
    rc, out = pre("bridge-reader")
    check("bridge: closed message is EMPTY and its filing cleared",
          out == "EMPTY" and stale_key not in keys(), (out, keys()))

    # Memory sweep: an over-cap working memory is drift.
    wm = os.path.join(ws, "Memory", "global", "working-memory.md")
    keep = open(wm, encoding="utf-8").read()
    open(wm, "a", encoding="utf-8").write("x" * 2100 + "\n")
    rc, out = pre("memory-sweep")
    check("memory sweep: over-cap working memory is WORK",
          rc == 0 and out.startswith("WORK drift: global: working memory"),
          out)
    open(wm, "w", encoding="utf-8").write(keep)

    # Backups: due, run, landed; unreachable is BROKEN.
    for tier in ("daily", "weekly"):
        cfg["backup"][tier + "_dest"] = os.path.join(tmp, "sched-" + tier)
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), indent=2)
    for tier in ("daily", "weekly"):
        t = "backup-" + tier
        rc, out = pre(t)
        check("%s: snapshot due is WORK" % t, rc == 0
              and out.startswith("WORK %s snapshot due" % tier), out)
        before = len(runs_lines(ws))
        rc, out = wrap(t)
        new = runs_lines(ws)[before:]
        check("%s: wrapper takes it and logs exit 0" % t, rc == 0
              and re.search(r"\| %s \| exit 0 \| snapshot landed: " % t,
                            new[0]), out)
        drilled = [x for x in new if "| restore-drill |" in x]
        check("%s: %s" % (t, "the landed snapshot is drilled, passed" if
                          tier == "weekly" else "no restore drill"),
              [bool(re.search(r"\| exit 0 \| passed: daily \d{4}-.*; "
                              r"weekly \d{4}-", x))
               for x in drilled] == ([True] if tier == "weekly" else []),
              new)
        rc, out = pre(t)
        check("%s: landed snapshot is EMPTY" % t, out == "EMPTY", out)
    cfg["backup"]["daily_dest"] = os.path.join(tmp, "no-such-drive", "x")
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), indent=2)
    rc, out = pre("backup-daily")
    check("backup-daily: unreachable destination is BROKEN, logged exit 2",
          rc == 2 and out.startswith("BROKEN")
          and "| backup-daily | exit 2 | broken: " in runs_lines(ws)[-1],
          out)

    # Cleanup: an expired quarantined file is WORK; the wrapper deletes it
    # (this week's backup landed above) and logs exit 0.
    qname = "sched_" + "exp" + "ired.txt"
    open(os.path.join(ws, "Quarantine", qname), "w").write("old")
    with open(os.path.join(ws, "Quarantine", "manifest.md"), "a",
              encoding="utf-8") as f:
        f.write("2020-01-01 | 2020-01-15 | Quarantine/%s | smoke\n" % qname)
    rc, out = pre("cleanup")
    check("cleanup: expired file is WORK", rc == 0
          and out == "WORK 1 file(s) past expiry", out)
    rc, out = wrap("cleanup")
    check("cleanup: wrapper deletes it and logs exit 0", rc == 0
          and not os.path.exists(os.path.join(ws, "Quarantine", qname))
          and "| cleanup | exit 0 | done: deleted 1" in runs_lines(ws)[-1],
          out)

    # A session finishing an agenda logs through runlog.py.
    rc, out = run(ws, os.path.join("Scheduled", "runlog.py"),
                  "work-item-launcher", "3", "WI-05 handed | back")
    check("runlog: a session's line lands, pipes kept out of the result",
          rc == 0 and runs_lines(ws)[-1].endswith(
              "| work-item-launcher | exit 3 | WI-05 handed / back"), out)
    check("runlog: every line in the format the board reads",
          all(RUN_LINE.match(x) for x in runs_lines(ws)), runs_lines(ws))


def corrupt(snap):
    """Plant two faults in a snapshot: AGENTS.md changed at the same size
    and time, and a database header broken. Returns the undo."""
    kept = []
    agents = os.path.join(snap, "AGENTS.md")
    db = next(os.path.join(d, f) for d, _, fs in os.walk(snap) for f in fs
              if f.endswith(".db"))
    for p, at, new in ((agents, 0, None), (db, 16, b"\x00\x03")):
        st, data = os.stat(p), open(p, "rb").read()
        kept.append((p, st, data))
        new = new or bytes([data[0] ^ 1])
        open(p, "wb").write(data[:at] + new + data[at + len(new):])
        os.utime(p, (st.st_atime, st.st_mtime))

    def undo():
        for p, st, data in kept:
            open(p, "wb").write(data)
            os.utime(p, (st.st_atime, st.st_mtime))
    return undo


def drill_checks(ws, snap):
    """The restore drill on a real snapshot, then on a planted corruption."""
    drill = os.path.join("Maintenance", "restore_drill.py")
    rc, out = run(ws, drill)
    line = runs_lines(ws)[-1]
    check("drill: passes on a real snapshot, logged exit 0", rc == 0
          and re.search(r"\| restore-drill \| exit 0 \| passed: weekly "
                        r"\d{4}-\d{2}-\d{2}: \d+ files read, [1-9]\d* "
                        r"databases checked, [1-9]\d* matched", line), out)
    managed = os.path.join(ws, "Temp", "managed")
    check("drill: scratch removed, its manifest line written",
          not any(d.startswith("restore-drill-") for d in os.listdir(managed))
          and "| restore drill scratch" in open(os.path.join(
              managed, "manifest.md"), encoding="utf-8").read())
    blog = open(os.path.join(ws, "Maintenance", "backup_log.txt"),
                encoding="utf-8").read()
    check("drill: the backup log carries no drill line", "drill" not in blog,
          blog)
    undo = corrupt(snap)
    rc, out = run(ws, drill)
    q = json.load(open(os.path.join(ws, "attention.json"), encoding="utf-8"))
    check("drill: planted corruption fails, logged exit 3, filed", rc == 3
          and re.search(r"\| restore-drill \| exit 3 \| failed: weekly \S+: "
                        r"AGENTS\.md differs from its unchanged live copy "
                        r"\(\+1 more\); ", runs_lines(ws)[-1])
          and any(i["key"] == "board:backup:drill-failed"
                  for i in q["items"]), out)
    undo()
    return lambda: corrupt(snap)


def doctor_status(out, name):
    m = re.search(r"^(PASS|WARN|FAIL)  %s +" % re.escape(name), out, re.M)
    return m.group(1) if m else None


def doctor_checks(tmp):
    """The doctor on a populated install, then on five deliberate breaks."""
    dws = os.path.join(tmp, "doctor")
    fresh_clone(SRC, dws)
    # What install.py leaves: rules placed (no-slot fallback), answers,
    # manifest, version, a landed backup, git history.
    agents_p = os.path.join(dws, "AGENTS.md")
    agents = open(agents_p, encoding="utf-8").read()
    if MARK_BEGIN not in agents:
        with open(agents_p, "w", encoding="utf-8") as f:
            f.write(agents.rstrip("\n") + "\n\n%s\nPlaced rules (smoke).\n%s\n"
                    % (MARK_BEGIN, MARK_END))
    for leftover in ("account-slot.txt", "answers.json"):
        p = os.path.join(dws, "Setup", leftover)
        if os.path.exists(p):
            os.remove(p)
    rels = [os.path.relpath(os.path.join(d, f), dws)
            for d, _, fs in os.walk(dws) for f in fs]
    os.makedirs(os.path.join(dws, "Setup"), exist_ok=True)
    open(os.path.join(dws, *MANIFEST.split("/")), "w",
         encoding="utf-8").write(manifest_text(rels))
    kit_tp = os.path.join(SRC, "..", "tiers", "project.md")
    if os.path.exists(kit_tp):
        shutil.copy2(kit_tp, os.path.join(dws, *PROJECT_TEMPLATE.split("/")))
    keys_src = os.path.join(SRC, "..", "tiers", "keys.json")
    if not os.path.exists(keys_src):
        keys_src = os.path.join(SRC, *RULE_KEYS.split("/"))
    keys_p = os.path.join(dws, *RULE_KEYS.split("/"))
    if os.path.exists(keys_src):
        shutil.copy2(keys_src, keys_p)
    ans_p = os.path.join(dws, "Setup", "answers.json")
    json.dump({"schema": 1, "workspace": dws, "account_slot_chars": 0,
               "backup": {"weekly_dest": os.path.join(tmp, "doctor-bk"),
                          "encrypted": True}},
              open(ans_p, "w", encoding="utf-8"))
    open(os.path.join(dws, "VERSION"), "w").write("9.9.9\n")
    cfgp = os.path.join(dws, "workspace.json")
    cfg_text = open(cfgp, encoding="utf-8").read()
    cfg = json.loads(cfg_text)
    cfg["backup"]["weekly_dest"] = os.path.join(tmp, "doctor-bk")
    cfg["backup"]["daily_dest"] = None
    good_cfg = json.dumps(cfg, indent=2)
    open(cfgp, "w", encoding="utf-8").write(good_cfg)
    run(dws, os.path.join("Maintenance", "backup.py"), "--tier", "weekly")
    git(dws, "init", "-q")
    git(dws, "add", "-A")
    rc, out = git(dws, *(git_identity(dws) + ["commit", "-q", "-m", "smoke"]))
    # Every scheduled piece has run once (bare: each precheck finds nothing).
    run_prechecks(dws)
    doc = os.path.join("Maintenance", "doctor.py")

    rc, out = run(dws, doc)
    names = ("tree", "workspace rules", "account tier", "answers", "version",
             "scheduled", "backup", "rule keys", "git", "smoke", "dashboard")
    check("doctor: populated install exits 0, every check PASS",
          rc == 0 and all(doctor_status(out, n) == "PASS" for n in names),
          out[-1500:])
    check("doctor: tier checks pass and name what to confirm with the AI",
          "Confirm with your AI" in out and "AGENTS.md" in out)
    check("doctor: a backup on the workspace's own disk passes, its "
          "tradeoff named", doctor_status(out, "backup") == "PASS"
          and "same disk as the workspace" in out, out)
    runs = open(os.path.join(dws, "Scheduled", "runs.log"),
                encoding="utf-8").read()
    check("doctor: writes the line the board's Doctor chip reads",
          re.search(r"\| doctor \| exit 0 \| PASS$", runs, re.M), runs)
    report_checks(dws, doc)

    # Break 1: a removed folder.
    held = os.path.join(tmp, "held-bridge")
    shutil.move(os.path.join(dws, "Agent Bridge"), held)
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: removed folder is a tree FAIL with a fix, exit 2",
          rc == 2 and doctor_status(out, "tree") == "FAIL"
          and "Agent Bridge/" in out and "fix: restore" in out, out)
    shutil.move(held, os.path.join(dws, "Agent Bridge"))

    # Break 2: an unparseable answers file.
    good_ans = open(ans_p, encoding="utf-8").read()
    open(ans_p, "w", encoding="utf-8").write("{not json")
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: unparseable answers is an answers FAIL, exit 2",
          rc == 2 and doctor_status(out, "answers") == "FAIL"
          and "fix: restore it" in out, out)
    open(ans_p, "w", encoding="utf-8").write(good_ans)

    # Break 3: a stale backup.
    stale = os.path.join(tmp, "stale-bk")
    os.makedirs(os.path.join(stale, "2020-01-01"))
    cfg["backup"]["weekly_dest"] = stale
    open(cfgp, "w", encoding="utf-8").write(json.dumps(cfg, indent=2))
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: stale backup is a backup WARN with a fix, exit 3",
          rc == 3 and doctor_status(out, "backup") == "WARN"
          and "overdue, last 2020-01-01" in out and "backup.py --tier "
          "weekly" in out, out)
    open(cfgp, "w", encoding="utf-8").write(good_cfg)

    # Break 4: a failed restore drill; then a passing one.
    runs_p = os.path.join(dws, "Scheduled", "runs.log")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(runs_p, "a", encoding="utf-8") as f:
        f.write("%s | restore-drill | exit 3 | failed: weekly x: a.txt "
                "differs\n" % stamp)
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: failed drill is a backup FAIL with a fix, exit 2",
          rc == 2 and doctor_status(out, "backup") == "FAIL"
          and "restore drill failed" in out and "restore_drill.py" in out,
          out)
    with open(runs_p, "a", encoding="utf-8") as f:
        f.write("%s | restore-drill | exit 0 | passed: weekly x\n" % stamp)
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: passed drill is PASS with its date",
          doctor_status(out, "backup") == "PASS"
          and "restore drill passed %s" % stamp[:10] in out, out)

    # Break 5: backups recorded as none.
    cfg["backup"].update(daily_dest=None, weekly_dest=None)
    open(cfgp, "w", encoding="utf-8").write(json.dumps(cfg, indent=2))
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: no backups is one backup WARN, not a FAIL, exit 3",
          rc == 3 and doctor_status(out, "backup") == "WARN"
          and "no destination is set" in out, out)
    open(cfgp, "w", encoding="utf-8").write(good_cfg)

    # Break 6: a byte-order mark on AGENTS.md.
    raw = open(agents_p, "rb").read()
    open(agents_p, "wb").write(b"\xef\xbb\xbf" + raw)
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: a byte-order mark on AGENTS.md is a rules WARN naming it",
          rc == 3 and doctor_status(out, "workspace rules") == "WARN"
          and "AGENTS.md starts with a byte-order mark" in out, out)
    open(agents_p, "wb").write(raw)

    # Break 8: backup encryption recorded false, then not recorded. The
    # doctor WARNs and the board's backup card is amber, never filed; true
    # (the populated run above) gives neither.
    page_p = os.path.join(tmp, "doctor-board.html")

    def enc_board():
        run(dws, os.path.join("Maintenance", "dashboard_build.py"), "--out",
            page_p)
        page = open(page_p, encoding="utf-8").read() \
            if os.path.exists(page_p) else ""
        m = re.search(r'dot (\w+)"></span>Encryption</div><div class="r">'
                      r'([^<]*)<', page)
        qp = os.path.join(dws, "attention.json")
        filed = "ncrypt" in (open(qp, encoding="utf-8").read()
                             if os.path.exists(qp) else "")
        return (m.groups() if m else (None, None)), filed
    (dot, _), filed = enc_board()
    check("board: encrypted backups recorded true are not amber",
          dot == "ok" and not filed, dot)
    for value, word in ((False, "not encrypted, by your recorded choice"),
                        (None, "not recorded whether the destination is "
                         "encrypted")):
        ans = json.loads(good_ans)
        if value is None:
            ans["backup"].pop("encrypted")
        else:
            ans["backup"]["encrypted"] = value
        open(ans_p, "w", encoding="utf-8").write(json.dumps(ans))
        rc, out = run(dws, doc, "--no-smoke")
        (dot, text), filed = enc_board()
        label = "false" if value is False else "missing"
        check("doctor: backup.encrypted %s is a backup WARN with its fix, "
              "exit 3" % label, rc == 3 and doctor_status(out, "backup")
              == "WARN" and word in out and "backup.encrypted" in out, out)
        check("board: backup.encrypted %s marks the backup card amber, "
              "nothing filed" % label, dot == "warn" and text == word
              and not filed, (dot, text, filed))
    open(ans_p, "w", encoding="utf-8").write(good_ans)

    # Break 9: rule keys. An unknown key and a renamed one in the placed
    # rules, an unknown heading in a project's rules file.
    good_keys = open(keys_p, encoding="utf-8").read()
    keys = json.loads(good_keys)
    keys["working-style"]["renamed"]["Choices"] = "Decisions"
    open(keys_p, "w", encoding="utf-8").write(json.dumps(keys))
    placed = open(agents_p, encoding="utf-8").read()
    open(agents_p, "w", encoding="utf-8").write(placed.replace(
        MARK_END, "- Coffee: strong.\n- Choices: mine.\n" + MARK_END))
    pdir = os.path.join(dws, "Projects", "smoke-keys")
    os.makedirs(pdir, exist_ok=True)
    open(os.path.join(pdir, "PROJECT.md"), "w", encoding="utf-8").write(
        "# smoke-keys: project rules\n\n## What this project is\n\nx\n\n"
        "## Notes\n\ny\n")
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: planted unknown and renamed rule keys are rule-keys "
          "WARNs naming each, exit 3", rc == 3
          and doctor_status(out, "rule keys") == "WARN"
          and "unknown key 'Coffee'" in out
          and "'Choices' was renamed to 'Decisions'" in out
          and "Projects/smoke-keys/PROJECT.md: unknown key 'Notes'" in out,
          out)
    shutil.rmtree(pdir)
    open(keys_p, "w", encoding="utf-8").write(good_keys)
    open(agents_p, "w", encoding="utf-8").write(placed)
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: rule keys pass again once the plants are gone",
          doctor_status(out, "rule keys") == "PASS", out)

    # Break 7: an installation from before the rule tiers.
    open(agents_p, "w", encoding="utf-8").write(agents.split(MARK_BEGIN)[0])
    os.remove(ans_p)
    rc, out = run(dws, doc, "--no-smoke")
    check("doctor: pre-tier install WARNs with placement steps, no FAIL",
          rc == 3 and doctor_status(out, "workspace rules") == "WARN"
          and doctor_status(out, "account tier") == "WARN"
          and "FAIL" not in re.sub(r"^DOCTOR.*$", "", out, flags=re.M)
          and "tiers/account.md" in out, out)


REPORT_ITEMS = ("tree", "workspace rules", "account tier", "answers",
                "version", "scheduled", "backup", "git", "journal",
                "installer state", "time zone", "leftover sidecars",
                "byte-order marks", "git history", "python", "git version",
                "AI tool", "kit version")
REPORT_FILES = ("summary.md", "doctor.txt", "smoke.txt", "journal.txt",
                "scheduler.txt", "git-log.txt", "env-keys.txt")


def report_status(summary, item):
    m = re.search(r"^\| %s \| (PASS|WARN|FAIL|UNKNOWN) \|" % re.escape(item),
                  summary, re.M)
    return m.group(1) if m else None


def report_checks(dws, doc):
    """doctor --report on the populated install, with planted trouble, and
    the issue body built from it."""
    fake = "smoke-" + "fake-value-" + "7f3a9c"
    plants = [os.path.join(dws, ".env"),
              os.path.join(dws, "Maintenance", "README.md.fieldbook-new")]
    open(plants[0], "w", encoding="utf-8").write("SMOKE_KEY=%s\n" % fake)
    open(plants[1], "w", encoding="utf-8").write("kit version\n")
    agents_p = os.path.join(dws, "AGENTS.md")
    raw = open(agents_p, "rb").read()
    open(agents_p, "wb").write(b"\xef\xbb\xbf" + raw)
    jp = os.path.join(dws, *JOURNAL.split("/"))
    with open(jp, "a", encoding="utf-8") as f:
        f.write("2026-01-01 09:00 | ai | install python | winget install "
                "Python.Python.3.12 | exit 0\nan unformatted note\n")
    rc, out = run(dws, doc, "--report", "--no-smoke")
    m = re.search(r"^REPORT: (.+)/summary\.md$", out, re.M)
    bundle = os.path.join(dws, *m.group(1).split("/")) if m else ""
    summary = open(os.path.join(bundle, "summary.md"), encoding="utf-8")\
        .read() if m and os.path.isdir(bundle) else ""
    man = open(os.path.join(dws, "Temp", "managed", "manifest.md"),
               encoding="utf-8").read()
    check("report: bundle and summary written, 14-day manifest line",
          summary and re.search(r"^(\S+) \| (\S+) \| %s \| doctor"
                                % re.escape(m.group(1)), man, re.M), out)
    missing = [i for i in REPORT_ITEMS if not report_status(summary, i)]
    missing += [f for f in REPORT_FILES
                if not os.path.isfile(os.path.join(bundle, f))]
    check("report: summary covers every item, bundle holds every file",
          not missing and re.search(r"^\| job \S+ \| (PASS|WARN|FAIL|"
                                    r"UNKNOWN) \|", summary, re.M), missing)
    check("report: planted sidecar and byte-order mark are not PASS, the "
          "odd journal line kept", report_status(summary, "leftover "
                                                 "sidecars") == "WARN"
          and report_status(summary, "byte-order marks") == "WARN"
          and "1 not in the line format" in summary and "an unformatted "
          "note" in open(os.path.join(bundle, "journal.txt"),
                         encoding="utf-8").read(), summary[:2500])
    leaked = [f for f in os.listdir(bundle) if fake in open(os.path.join(
        bundle, f), encoding="utf-8", errors="replace").read()]
    check("report: no .env value in the bundle, key names only",
          not leaked and "SMOKE_KEY" in open(os.path.join(
              bundle, "env-keys.txt"), encoding="utf-8").read(), leaked)
    runs = open(os.path.join(dws, "Scheduled", "runs.log"),
                encoding="utf-8").read().splitlines()
    check("report: the doctor's run-log line is still written",
          runs and "| doctor | exit " in runs[-1], runs[-1:])
    sanitize = os.path.join(SRC, "..", "sanitize.py")
    if os.path.exists(sanitize):
        rc, out = run(dws, sanitize, bundle)
        check("report: sanitize.py passes on the bundle", rc == 0, out)
    problem = os.path.join(dws, "Temp", "managed", "problem.md")
    open(problem, "w", encoding="utf-8").write(
        "It broke in %s for %s. " % (dws, getpass.getuser()) + "x" * 5000)
    issue = os.path.join(dws, "Temp", "managed", "feedback", "report.md")
    rc, out = run(dws, doc, "--issue", bundle, "--problem", problem,
                  "--out", issue)
    body = open(issue, encoding="utf-8").read() if rc == 0 else ""
    check("report: issue body fits 6,000, keeps the table, trims details",
          0 < len(body) <= 6000 and "| Item | Status | Detail |" in body
          and "| kit version |" in body and "trimmed" in body.lower(),
          "%d chars: %s" % (len(body), out))
    check("report: issue body holds no .env value, workspace path or "
          "user name", fake not in body and dws.lower() not in body.lower()
          and not re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])"
                            % re.escape(getpass.getuser()), body, re.I)
          and "<workspace>" in body and "<user>" in body, body[:400])
    for p in plants:
        os.remove(p)
    open(agents_p, "wb").write(raw)


def procedures(ws):
    """The trigger index: shipped current, complete, idempotent, strict."""
    skills = os.path.join(ws, "Skills")
    gen = os.path.join("Skills", "tools", "build_trigger_index.py")
    idx = os.path.join(skills, "00_triggers.md")
    rc, out = run(ws, gen)
    check("procedures: shipped index is current", rc == 0
          and out.startswith("unchanged"), out)
    index = open(idx, encoding="utf-8").read()
    missing = []
    for fn in sorted(os.listdir(skills)):
        if fn.endswith("-SKILL.md"):
            head = open(os.path.join(skills, fn),
                        encoding="utf-8").read().split("\n---", 1)[0]
            trig = re.findall(r'^\s+-\s+"(.+)"$', head, re.M)
            if not trig or "](%s)" % fn not in index \
                    or any('"%s"' % t not in index for t in trig):
                missing.append(fn)
    check("procedures: every file indexed with all its triggers",
          not missing, missing)
    unsourced = [c for fn in sorted(os.listdir(skills)) if fn.endswith(".md")
                 for c in re.findall(r"`[^`]*attention\.py --file[^`]*`",
                                     open(os.path.join(skills, fn),
                                          encoding="utf-8").read())
                 if "--source" not in c]
    check("procedures: every waiting-on-you filing names its source",
          not unsourced, unsourced)
    probe = os.path.join(skills, "smoke-probe-SKILL.md")
    open(probe, "w", encoding="utf-8").write(
        '---\nname: smoke-probe\ndescription: Smoke probe.\ntriggers:\n'
        '  - "probe the smoke"\n---\n\n# Probe\n')
    rc, out = run(ws, gen)
    first = open(idx, encoding="utf-8").read()
    check("procedures: new procedure indexed", rc == 0
          and out.startswith("written") and '"probe the smoke"' in first
          and "](smoke-probe-SKILL.md)" in first, out)
    rc, out = run(ws, gen)
    check("procedures: rerun changes nothing", rc == 0
          and out.startswith("unchanged")
          and open(idx, encoding="utf-8").read() == first, out)
    bad = os.path.join(skills, "smoke-bad-SKILL.md")
    open(bad, "w", encoding="utf-8").write(
        "---\nname: smoke-bad\ndescription: >\n  folded\ntriggers:\n"
        '  - "x"\n---\n')
    rc, out = run(ws, gen)
    check("procedures: broken frontmatter is exit 2, index untouched",
          rc == 2 and "smoke-bad-SKILL.md" in out
          and open(idx, encoding="utf-8").read() == first, out)
    os.remove(bad)
    os.remove(probe)
    rc, out = run(ws, gen)
    check("procedures: index restored", rc == 0
          and open(idx, encoding="utf-8").read() == index, out)


def kit_checks():
    """Inside the kit only: the release manifest is current and the upgrade
    engine passes its own self-test. An installed workspace has no kit."""
    kit = os.path.abspath(os.path.join(SRC, ".."))
    if not os.path.exists(os.path.join(kit, "upgrade.py")):
        return
    rc, out = run(kit, "release_manifest.py", "--check")
    check("kit: release manifest current for VERSION", rc == 0, out)
    tiers = os.path.join(kit, "tiers")

    def tier(name):
        return open(os.path.join(tiers, name), encoding="utf-8").read()
    found = {
        "account": re.findall(r"^\d+\. ([^:\n]+): ", tier("account.md"),
                              re.M),
        "working-style": re.findall(r"^- ([^:\n]+): ", tier(
            "working-style.md").split("\n---\n", 1)[1], re.M),
        "project": re.findall(r"^## (.+?)\s*$", tier("project.md"), re.M)}
    known = json.load(open(os.path.join(tiers, "keys.json"),
                           encoding="utf-8"))
    check("kit: tiers/keys.json lists exactly the keys the tier files use",
          all(known[t]["keys"] == found[t] for t in found),
          {t: (known[t]["keys"], found[t]) for t in found})
    rc, out = run(kit, "upgrade_selftest.py")
    check("kit: upgrade self-test passes", rc == 0
          and "ALL UPGRADE CHECKS PASSED" in out, out[-1500:])


def main():
    tmp = tempfile.mkdtemp(prefix="workspace-smoke-")
    # The home-folder install journal: a throwaway one, never the user's.
    os.environ["FIELDBOOK_HOME"] = os.path.join(tmp, "home")
    ws = os.path.join(tmp, "ws")
    fresh_clone(SRC, ws)
    print("smoke workspace (simulated fresh clone): %s\n" % ws)
    check("fresh clone: machinery present, runtime state absent",
          os.path.exists(os.path.join(ws, "Maintenance", "doctor.py"))
          and not os.path.exists(os.path.join(ws, ".git"))
          and not os.path.exists(os.path.join(ws, "attention.json")))

    # --- Board, fresh install: every section in its empty state -----
    cfgp = os.path.join(ws, "workspace.json")
    cfg = json.load(open(cfgp, encoding="utf-8"))
    cfg["backup"].update(daily_dest=None, weekly_dest=None)
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), indent=2)
    page, items = board(ws, "empty")
    check("board empty: empty states render", all(s in page for s in (
        "Doctor <b>never run</b>", "Search index never built", "0 unread",
        "Cooling off</div><div class=\"r\">0 files")), page[-3000:])
    shipped = tasks(ws)
    check("board empty: every shipped task listed, never run", shipped
          and all(re.search(r"%s</td>\s*<td>never run" % re.escape(
              t.replace("-", " ").capitalize()), page) for t in shipped),
          shipped)
    again = board(ws, "rebuilt")[1]
    check("board empty: no backups is amber and filed once, never red",
          re.search(r'dot warn"></span>Destination</div><div class="r">none '
                    r'set\. Filed as A-\d+\.', page)
          and [i["key"] for i in again].count("board:backup:none") == 1
          and all(i["source"] == "dashboard" for i in again
                  if i["key"] == "board:backup:none"), again)

    # --- Attention queue: idempotent filing, clear, urgent first ----
    att = os.path.join("Maintenance", "attention.py")
    run(ws, att, "--file", "Normal item.", "--source", "smoke", "--key", "k1")
    rc, out = run(ws, att, "--file", "Normal item.", "--source", "smoke",
                  "--key", "k1")
    q = json.load(open(os.path.join(ws, "attention.json"), encoding="utf-8"))
    check("queue: same key files once", rc == 0 and
          sum(i["key"] == "k1" for i in q["items"]) == 1, out)
    first = [i["id"] for i in q["items"] if i["key"] == "k1"][0]
    rc, out = run(ws, att, "--clear", first)
    q = json.load(open(os.path.join(ws, "attention.json"), encoding="utf-8"))
    check("queue: --clear removes", rc == 0 and
          not any(i["id"] == first for i in q["items"]), out)
    rc, out = run(ws, att, "--clear", first)
    check("queue: clearing an unknown id is exit 2", rc == 2, out)
    run(ws, att, "--file", "Plain later item.", "--source", "smoke")
    run(ws, att, "--file", "Urgent item.", "--urgent", "--source", "smoke")

    # --- Memory: index, search, evict -------------------------------
    rc, out = run(ws, os.path.join("Memory", "engine", "indexer.py"))
    check("memory: indexer runs", rc == 0, out)
    check("memory: chunks indexed", "chunks total" in out and
          not out.startswith("indexed: 0 "), out)
    rc, out = run(ws, os.path.join("Memory", "engine", "search.py"),
                  "admission test")
    check("memory: search finds AGENTS.md content", rc == 0 and
          "AGENTS.md" in out, out[:200])
    rc, out = run(ws, os.path.join("Memory", "engine", "search.py"),
                  "zzz-no-such-term-zzz")
    check("memory: honest miss", "not found in memory" in out, out[:200])

    wm = os.path.join(ws, "Memory", "global", "working-memory.md")
    with open(wm, "a", encoding="utf-8") as f:
        f.write("evictable test line\n")
    rc, out = run(ws, os.path.join("Memory", "engine", "evict.py"),
                  wm, "evictable test line")
    logf = os.path.join(ws, "Memory", "global", "logs",
                        date.today().isoformat() + ".md")
    check("memory: evict records then removes", rc == 0
          and os.path.exists(logf)
          and "evictable test line" in open(logf, encoding="utf-8").read()
          and "evictable" not in open(wm, encoding="utf-8").read(), out)

    # --- Work items: complete the example item ----------------------
    spec = os.path.join(ws, "Work Items", "WI-01_example-item.md")
    if not os.path.exists(spec):    # an installed workspace's specs are its own
        with open(spec, "w", encoding="utf-8") as f:
            f.write("project: global\nname: example item\n\n# WI-01 - "
                    "example\n\n| Field | Value |\n|---|---|\n| Status | "
                    "OPEN |\n")
    with open(spec, "a", encoding="utf-8") as f:
        f.write("\noutcome: smoke test completion\n")
    os.makedirs(os.path.join(ws, "Work Items", "completed"), exist_ok=True)
    shutil.move(spec, os.path.join(ws, "Work Items", "completed",
                                   "WI-01_example-item.md"))
    rc, out = run(ws, os.path.join("Work Items", "tools",
                                   "build_completed_index.py"))
    idx = os.path.join(ws, "Work Items", "completed",
                       "00_completed_index.md")
    check("work items: completed index builds", rc == 0
          and os.path.exists(idx)
          and "WI-01" in open(idx, encoding="utf-8").read(), out)

    # --- Procedures: the generated trigger index --------------------
    procedures(ws)

    # --- Scheduled pieces: prechecks, wrappers, run log -------------
    scheduled_checks(tmp)

    # --- Backup: real snapshot to a temp destination ----------------
    dest = os.path.join(tmp, "backups")
    cfgp = os.path.join(ws, "workspace.json")
    cfg = json.load(open(cfgp, encoding="utf-8"))
    cfg["backup"]["weekly_dest"] = dest
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), indent=2)
    rc, out = run(ws, os.path.join("Maintenance", "backup.py"),
                  "--tier", "weekly")
    snap = os.path.join(dest, date.today().isoformat())
    check("backup: snapshot lands", rc == 0 and os.path.isdir(snap), out)
    check("backup: snapshot carries AGENTS.md",
          os.path.exists(os.path.join(snap, "AGENTS.md")))
    recorrupt = drill_checks(ws, snap)

    # --- Cleanup: expired file deleted, cooling file held -----------
    # Filenames are ASSEMBLED so their literals never appear in this file:
    # this script is itself a load-bearing surface the reference re-check
    # searches, and a spelled-out name here would hold the file forever.
    qname = "old_" + "scr" + "atch.txt"
    qfile = os.path.join(ws, "Quarantine", qname)
    open(qfile, "w").write("expired quarantined file")
    with open(os.path.join(ws, "Quarantine", "manifest.md"), "a",
              encoding="utf-8") as f:
        f.write("2020-01-01 | 2020-01-15 | Quarantine/%s | smoke\n" % qname)
    kfile = os.path.join(ws, "Temp", "managed",
                         "fresh_" + "scr" + "atch.txt")
    open(kfile, "w").write("fresh managed file")
    rc, out = run(ws, os.path.join("Maintenance", "cleanup.py"))
    check("cleanup: expired file deleted", rc == 0
          and not os.path.exists(qfile), out)
    check("cleanup: fresh file held (cooling)", os.path.exists(kfile), out)

    # --- Cleanup: boundary holds ------------------------------------
    outside = os.path.join(ws, "AGENTS.md")
    check("cleanup: boundary intact", os.path.exists(outside))

    # --- Board, populated: real values from the tree built above ----
    open(os.path.join(ws, "VERSION"), "w").write("9.9.9\n")
    with open(os.path.join(ws, "Work Items", "WI-02_smoke-item.md"), "w",
              encoding="utf-8") as f:
        f.write("project: global\nname: smoke populated item\n\n# WI-02 - x\n"
                "\n| Field | Value |\n|---|---|\n| Status | IN PROGRESS |\n"
                "| Priority | P1 |\n")
    old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    with open(os.path.join(ws, "Agent Bridge", "to-global",
                           "FROM-smoke_%s_ping.md" % old), "w",
              encoding="utf-8") as f:
        f.write("---\nfrom: smoke\nstatus: open\n---\nping\n")
    task = os.path.join(ws, "Scheduled", "smoke-task")
    os.makedirs(task)
    open(os.path.join(task, "INSTRUCTIONS.md"), "w").write("# smoke\n")
    json.dump({"schedule": "DAILY", "time": "06:00"},
              open(os.path.join(task, "schedule.json"), "w"))
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(ws, "Scheduled", "runs.log"), "w",
              encoding="utf-8") as f:
        f.write("%s | smoke-task | exit 0 | smoke run landed\n"
                "%s | broken-task | exit 2 | smoke failure\n"
                "%s | doctor | exit 0 | PASS\n" % (stamp, stamp, stamp))
    page, items = board(ws, "populated")
    check("board populated: real values shown", all(s in page for s in (
        "WI-02", "smoke populated item", "IN PROGRESS", "1 unread",
        "oldest 5 days", "smoke run landed", "Doctor <b>PASS</b>",
        "Kit <b>v9.9.9</b>", "Search index rebuilt", "Weekly",
        "Plain later item.")), page[-4000:])
    check("board populated: a backup destination clears the no-backups "
          "filing", not any(i["key"] == "board:backup:none" for i in items),
          items)
    check("board populated: urgent renders first",
          0 < page.find("Urgent item.") < page.find("Plain later item."))
    check("board populated: work states from Run, Status and Depends on",
          all(s in page for s in (
              'wrow ok">Ready for launcher<b>0</b>',
              'wrow bad">Blocked<b>0</b>',
              'wrow warn">Needs decisions<b>1</b>',
              'wrow acc">Attended session<b>0</b>',
              'wrow hold">On hold<b>0</b>'))
          and "Handed back" not in page, page[:3000])
    cfg = json.load(open(cfgp, encoding="utf-8"))
    looks = {}
    for look in ("dark", "colorful-light", "no-such-look"):
        cfg.setdefault("board", {})["theme"] = look
        json.dump(cfg, open(cfgp, "w", encoding="utf-8"), indent=2)
        looks[look] = board(ws, "look " + look)[0]
    cfg["board"]["theme"] = "auto"
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), indent=2)
    check("board: the look follows workspace.json, unknown falls back",
          "/* dark:" in looks["dark"] and "/* auto:" not in looks["dark"]
          and "/* auto:" in looks["no-such-look"]
          and "/* colorful light:" in looks["colorful-light"]
          and 'class="card c-work"' in looks["colorful-light"]
          and 'chip warn">Look <b>no-such-look</b> unknown'
          in looks["no-such-look"])
    check("board populated: never-run drill neutral, not filed",
          re.search(r'class="dot idle"></span>Last restore drill: not run '
                    r'yet', page)
          and not any("drill" in i["key"] for i in items))
    check("board populated: failed task filed",
          any(i["key"] == "board:task:broken-task:failed" for i in items))
    with open(os.path.join(ws, "Scheduled", "runs.log"), "a",
              encoding="utf-8") as f:
        f.write("%s | broken-task | exit 0 | fixed\n" % stamp)
    page, items = board(ws, "recovered")
    check("board: a state back to normal clears its filing",
          not any(i["key"] == "board:task:broken-task:failed"
                  for i in items))

    # --- Board and the drill: failed is red and filed, passed OK -----
    undo = recorrupt()
    run(ws, os.path.join("Maintenance", "restore_drill.py"))
    page, items = board(ws, "drill failed")
    check("board: failed drill red and filed", re.search(
        r'class="dot bad"[^>]*></span>Last restore drill: today \d\d:\d\d '
        r'· failed: ', page) and any(i["key"] == "board:backup:drill-failed"
                                     for i in items), page[-3000:])
    undo()
    run(ws, os.path.join("Maintenance", "restore_drill.py"))
    page, items = board(ws, "drill passed")
    check("board: passed drill OK with its date, filing cleared", re.search(
        r'class="dot ok"></span>Last restore drill: today \d\d:\d\d · '
        r'passed: ', page) and not any("drill" in i["key"] for i in items),
        page[-3000:])

    # --- Projects: creation, tabs, panels, stale and broken ---------
    projects_checks(ws)

    if os.environ.get(SMOKE_NESTED):
        print("\n(doctor checks skipped: the doctor started this run)")
    else:
        doctor_checks(tmp)
        kit_checks()

    try:
        rmtree(tmp)
    except OSError:
        pass
    print()
    if FAILURES:
        print("FAILED: %d check(s): %s" % (len(FAILURES),
                                           ", ".join(FAILURES)))
        sys.exit(1)
    print("ALL CHECKS PASSED - the installation works.")


if __name__ == "__main__":
    main()
