"""install.py - build a Fieldbook OS workspace from the setup interview.

The installing AI holds the interview; this script does every mechanical
step, so every install builds the same tree. Standard library only.
Supported on Windows; elsewhere it runs best-effort.

Usage (from the kit root, beside this file):
  python install.py --check
      Prerequisites as JSON on stdout. The AI reads it out and offers fixes;
      this script only reports.
  python install.py --answers FILE [--dry-run] [--stop-after PHASE]
                    [--no-register]
      Install into the answers' "workspace" folder.
  python install.py --workspace DIR [...same flags]
      Resume or rerun from the answers saved in DIR/Setup/answers.json.

Phases, in order; each ends in one git commit, so resume and rollback ride
on the workspace's history:
  workspace  create the folder, git init, save answers and .gitignore
  systems    copy the kit's workspace/ tree; list it in Setup/manifest.json
             (format: workspace_common.py), which the doctor checks
  config     workspace.json, the project rules template, and per answered
             project its tenant, Projects/ folder and inbox
  rules      place the account tier and working style (slot or AGENTS.md)
  scheduler  wire each task under Scheduled/ to the adopter's scheduler
  stamp      copy the kit VERSION to the workspace root; install complete
Completed phases are recorded in Setup/install-state.json and skipped on
rerun. A rerun with every phase done changes nothing and says so.

Never overwrite: where a file already exists with other content, the kit's
version is written beside it as NAME.fieldbook-new and listed in
Setup/install-report.md; the adopter and their AI merge it.

Setup/hashes.json records the sha256 of every file outside Setup/ as the
installer left it (sidecars excluded), so upgrade.py can tell a file the
adopter never touched from one they changed, including files rendered from
the answers.

Answers file (Setup/answers.json once saved; its "_about" key documents
every field, see ANSWERS_ABOUT below).

Scheduled tasks: every folder under the kit's workspace/Scheduled/ holding
INSTRUCTIONS.md is a task. Its schedule.json reads
  {"schedule": "DAILY" | "WEEKLY", "day": "SUN", "time": "HH:MM"}
("day" only for WEEKLY). answers scheduler.times.<task> overrides the time.
A task without schedule.json is reported, not wired.

Exit codes:
  0  done, stopped as asked, or nothing to do (the printed word says which)
  1  crashed (an uncaught error)
  2  broken: prerequisite missing, bad answers or arguments, git failed
  3  held: finished but left something to act on (sidecars to merge, a
     task not wired, answers differing from the saved ones)
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime

KIT = os.path.dirname(os.path.abspath(__file__))
KIT_WS = os.path.join(KIT, "workspace")
sys.path.insert(0, KIT_WS)
from workspace_common import (BOARD_THEMES, MANIFEST, MARK_BEGIN,  # noqa
                              MARK_END, PROJECT_NAME, PROJECT_TEMPLATE, git,
                              git_identity, manifest_text, project_files,
                              project_tenant)

PHASES = ["workspace", "systems", "config", "rules", "scheduler", "stamp"]
SIDECAR = ".fieldbook-new"
SETUP = "Setup"
HASHES = SETUP + "/hashes.json"
COPY_SKIP_DIRS = {"__pycache__", ".git", "index"}
COPY_SKIP_FILES = re.compile(r"(_log\.txt|\.pyc|\.db|" + re.escape(SIDECAR)
                             + r")$")
TASK_PREFIX = "Fieldbook OS"

ANSWERS_ABOUT = {
    "schema": "Answers format version; this file is format 1.",
    "workspace": "Absolute path of the workspace folder to build.",
    "timezone": "The adopter's time zone as they name it, e.g. "
                "Europe/Berlin; placed into the account tier.",
    "account_slot_chars": "Character limit of the tool's account-level "
                          "instructions slot; 0 means the tool has none.",
    "working_style": "Per default item (Decisions, Answers, ...): 'keep', "
                     "'drop', or the adopter's replacement text. A missing "
                     "item is kept.",
    "projects": "Project names, each getting its own memory tenant, "
                "Projects/<name>/ folder and bridge inbox. Empty keeps the "
                "kit's example-project tenant.",
    "backup": "daily_dest / weekly_dest: backup folders outside the "
              "workspace, or null for none.",
    "scheduler": "kind: 'windows' or 'none'. launch_command (windows): the "
                 "command that starts a file-capable AI session; {task}, "
                 "{instructions} and {workspace} are filled in. times: "
                 "optional per-task HH:MM overrides.",
    "services": "Keys and what each costs, from the interview; kept for "
                "the services file. Key names only, never values.",
    "about_user": "Who the adopter is, in their own words (name, what they do, what to keep in mind); fills Memory/global/core-profile.md's \"Who the user is\" section. Missing leaves the template.",
    "board_theme": "The dashboard's look: one of %s; missing means the "
                   "first. Written to workspace.json board.theme."
                   % ", ".join(BOARD_THEMES),
}
ANSWER_KEYS = set(ANSWERS_ABOUT) | {"_about"}


class Broken(Exception):
    """Could not do the job; exit 2."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def kit_files(skip_example=False):
    """Workspace-relative paths (OS separators) of the kit's workspace/ files
    the systems phase copies, sorted. The release manifest hashes the same
    set (skip_example False)."""
    out = []
    for dirpath, dirnames, files in os.walk(KIT_WS):
        relroot = os.path.relpath(dirpath, KIT_WS)
        dirnames[:] = sorted(d for d in dirnames
                             if d not in COPY_SKIP_DIRS and not (
                                 skip_example and d == "example-project"
                                 and relroot == "Memory"))
        for fn in sorted(files):
            if COPY_SKIP_FILES.search(fn) or fn == ".gitignore" \
                    and relroot == ".":
                continue
            out.append(os.path.normpath(os.path.join(relroot, fn)))
    return out


# ---------------------------------------------------------------- checks

def check_prereqs():
    py_ok = sys.version_info >= (3, 10)
    res = {"file_access": {"ok": True, "detail": "this script is running, "
                           "so the AI can run commands on this machine"},
           "python": {"ok": py_ok, "version": platform.python_version(),
                      "need": "3.10 or newer"}}
    if not py_ok:
        res["python"]["fix"] = "install Python 3.10+ from python.org"
    gpath = shutil.which("git")
    gver = None
    if gpath:
        r = subprocess.run(["git", "--version"], capture_output=True,
                           text=True)
        gver = r.stdout.strip() if r.returncode == 0 else None
    res["git"] = {"ok": bool(gver), "version": gver}
    if not gver:
        res["git"]["fix"] = ("install Git (git-scm.com, or "
                             "'winget install Git.Git' on Windows)")
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        fts = True
    except sqlite3.Error:
        fts = False
    res["sqlite_fts5"] = {"ok": fts, "detail": "memory search needs it"}
    if not fts:
        res["sqlite_fts5"]["fix"] = "use a python.org Python build"
    res["os"] = {"ok": True, "name": platform.system(),
                 "supported": platform.system() == "Windows",
                 "detail": "Windows is supported; elsewhere best-effort"}
    res["ok"] = all(v["ok"] for v in res.values() if isinstance(v, dict))
    return res


# --------------------------------------------------------------- answers

def validate(ans):
    errs = []
    unknown = set(ans) - ANSWER_KEYS
    if unknown:
        errs.append("unknown keys: " + ", ".join(sorted(unknown)))
    ws = ans.get("workspace")
    if not ws or not os.path.isabs(ws):
        errs.append("workspace must be an absolute path")
    else:
        try:
            inside = os.path.commonpath([os.path.abspath(ws), KIT]) == KIT
        except ValueError:
            inside = False
        if inside:
            errs.append("workspace must be outside the kit folder")
    if not ans.get("timezone"):
        errs.append("timezone is required")
    slot = ans.get("account_slot_chars", 0)
    if not isinstance(slot, int) or slot < 0:
        errs.append("account_slot_chars must be a whole number >= 0")
    items = [i[0] for i in style_items()]
    for k in ans.get("working_style", {}) or {}:
        if k not in items:
            errs.append("working_style item %r is not one of %s" % (k, items))
    for p in ans.get("projects", []) or []:
        if not re.match(PROJECT_NAME, str(p)) or p == "global":
            errs.append("project name %r: letters, digits, - and _ only "
                        "(and not 'global')" % p)
    sch = ans.get("scheduler") or {"kind": "none"}
    if ans.get("board_theme", BOARD_THEMES[0]) not in BOARD_THEMES:
        errs.append("board_theme must be one of " + ", ".join(BOARD_THEMES))
    if sch.get("kind") not in ("windows", "none"):
        errs.append("scheduler.kind must be 'windows' or 'none'")
    if sch.get("kind") == "windows" and not sch.get("launch_command"):
        errs.append("scheduler.launch_command is required for 'windows'")
    for t, hhmm in (sch.get("times") or {}).items():
        if not re.match(r"^\d\d:\d\d$", str(hhmm)):
            errs.append("scheduler.times.%s must be HH:MM" % t)
    if errs:
        raise Broken("bad answers: " + "; ".join(errs))


def comparable(ans):
    return {k: v for k, v in ans.items() if k != "_about"}


def saved_answers_text(ans):
    out = {"_about": ANSWERS_ABOUT, "schema": 1}
    out.update(comparable(ans))
    out["schema"] = 1
    return json.dumps(out, indent=2) + "\n"


# ----------------------------------------------------------- tier texts

def read_kit(rel):
    with open(os.path.join(KIT, rel), encoding="utf-8") as f:
        return f.read()


def style_items():
    """[(label, placed line)] from tiers/working-style.md, Ask lines out."""
    text = read_kit(os.path.join("tiers", "working-style.md"))
    body = text.split("\n---\n", 1)[1]
    items = []
    for line in body.splitlines():
        m = re.match(r"^- ([^:]+): ", line)
        if m:
            items.append((m.group(1), line))
    return items


def style_header():
    body = read_kit(os.path.join("tiers", "working-style.md")).split(
        "\n---\n", 1)[1]
    return next(l for l in body.splitlines() if l.strip())


def placed_texts(ans):
    """Return (slot_text or None, agents_block or None, where-note).

    B-2 placement: principles are written to fit a small slot; the working
    style joins them in the slot when both fit, else goes to AGENTS.md. No
    slot, or a slot too small for the principles: both go to AGENTS.md.
    """
    principles = read_kit(os.path.join("tiers", "account.md")).strip()
    principles = principles.replace("{WORKSPACE}", ans["workspace"]) \
                           .replace("{TIMEZONE}", ans["timezone"])
    choices = ans.get("working_style") or {}
    lines = [style_header()]
    for label, line in style_items():
        c = choices.get(label, "keep")
        if c == "drop":
            continue
        lines.append(line if c == "keep" else "- %s: %s" % (label, c))
    style = "\n".join(lines) if len(lines) > 1 else ""
    both = principles + ("\n\n" + style if style else "")
    slot = ans.get("account_slot_chars", 0)
    if slot and len(both) <= slot:
        return both, None, "principles and working style in the slot"
    if slot and len(principles) <= slot:
        return principles, style or None, \
            "principles in the slot, working style in AGENTS.md"
    why = "tool has no slot" if not slot else \
        "slot of %d is smaller than the principles (%d)" % (slot,
                                                           len(principles))
    return None, both, "both in AGENTS.md (%s)" % why


def agents_with_block(template, block):
    if block is None:
        return template
    wrapped = "%s\n%s\n%s" % (MARK_BEGIN, block, MARK_END)
    if MARK_BEGIN in template and MARK_END in template:
        a, rest = template.split(MARK_BEGIN, 1)
        return a + wrapped + rest.split(MARK_END, 1)[1]
    return template.rstrip("\n") + "\n\n" + wrapped + "\n"


# ---------------------------------------------------------- the installer

class Installer:
    def __init__(self, ans, dry, register):
        self.ans = ans
        self.ws = os.path.abspath(ans["workspace"])
        self.dry = dry
        self.register = register
        self.touched = []       # workspace-relative paths written this phase
        self.held = []          # report lines needing the adopter
        self.report = []
        try:
            with open(os.path.join(self.ws, HASHES), encoding="utf-8") as f:
                self.hashes = json.load(f)["files"]
        except (OSError, ValueError, KeyError):
            self.hashes = {}
        self.hashes_saved = dict(self.hashes)

    # -- primitives
    def say(self, msg):
        print(("PLAN  " if self.dry else "") + msg)

    def rel(self, path):
        return os.path.relpath(path, self.ws).replace("\\", "/")

    def put(self, rel, data, replace_if=()):
        """Write bytes at rel unless it holds other content: then sidecar.

        replace_if: contents the installer itself wrote earlier that may be
        replaced (a template it placed, now being filled in).
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        path = os.path.join(self.ws, rel)
        cur = None
        if os.path.exists(path):
            with open(path, "rb") as f:
                cur = f.read()
        if cur == data:
            self.record(rel, data)
            return
        ok = [r.encode("utf-8") if isinstance(r, str) else r
              for r in replace_if]
        if cur is not None and cur not in ok:
            side = path + SIDECAR
            if os.path.exists(side):
                with open(side, "rb") as f:
                    old = f.read()
                if old == data:
                    return
                if old in ok:
                    self.say("update %s%s" % (rel, SIDECAR))
                    if not self.dry:
                        with open(side, "wb") as f:
                            f.write(data)
                        self.touched.append(rel + SIDECAR)
                    return
                self.hold("%s: exists and differs, and a sidecar is already "
                          "there; left both alone" % rel)
                return
            self.say("sidecar %s%s (existing file kept)" % (rel, SIDECAR))
            self.hold("%s: already existed; the kit's version is beside it "
                      "as %s%s to merge" % (rel, rel, SIDECAR))
            path, rel = side, rel + SIDECAR
        else:
            self.say(("update " if cur is not None else "write ") + rel)
        if self.dry:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        self.touched.append(rel)
        if not rel.endswith(SIDECAR):
            self.record(rel, data)

    def record(self, rel, data):
        rel = rel.replace("\\", "/")
        if not rel.startswith(SETUP + "/"):
            self.hashes[rel] = sha(data)

    def save_hashes(self):
        if self.dry or self.hashes == self.hashes_saved:
            return
        p = os.path.join(self.ws, HASHES)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"_about": "sha256 of each file as the installer or "
                       "upgrade.py last left it; upgrade.py treats a file "
                       "still matching as unmodified.",
                       "files": dict(sorted(self.hashes.items()))}, f,
                      indent=2)
            f.write("\n")
        self.hashes_saved = dict(self.hashes)
        self.touched.append(HASHES)

    def hold(self, line):
        self.held.append(line)
        self.report.append("- HELD " + line)

    def git(self, *args):
        rc, out = git(self.ws, *args)
        if rc != 0:
            raise Broken("git %s failed: %s" % (args[0], out))
        return out

    def commit(self, n, name):
        msg = "Fieldbook OS install: phase %d/%d %s" % (n, len(PHASES), name)
        self.say("git commit: " + msg)
        if self.dry:
            return
        self.save_hashes()
        if self.touched:
            self.git("add", "--", *self.touched)
        self.git(*(git_identity(self.ws) +
                   ["commit", "-q", "--allow-empty", "-m", msg]))
        self.touched = []

    # -- state and report
    def state_path(self):
        return os.path.join(self.ws, SETUP, "install-state.json")

    def load_state(self):
        try:
            with open(self.state_path(), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"phases_done": []}

    def save_state(self, st):
        st["_about"] = ("Install progress: phases_done lists finished "
                        "phases, which a rerun skips. Written by install.py.")
        self.put(SETUP + "/install-state.json",
                 json.dumps(st, indent=2) + "\n",
                 replace_if=[self.current(SETUP + "/install-state.json")])

    def current(self, rel):
        p = os.path.join(self.ws, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                return f.read()
        return b""

    def flush_report(self, phase):
        if self.dry:
            for line in self.report:
                self.say("report: " + line)
            self.report = []
            return
        rel = SETUP + "/install-report.md"
        p = os.path.join(self.ws, rel)
        new = not os.path.exists(p)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            if new:
                f.write("# Install report\n\nOne section per phase. HELD "
                        "lines need the adopter; everything else is a "
                        "record.\n")
            f.write("\n## %s (%s)\n\n" % (
                phase, datetime.now().strftime("%Y-%m-%d %H:%M")))
            f.write("\n".join(self.report or ["- done, nothing to note"])
                    + "\n")
        self.touched.append(rel)
        self.report = []

    # -- phases
    def phase_workspace(self):
        if not os.path.isdir(self.ws):
            self.say("mkdir " + self.ws)
            if not self.dry:
                os.makedirs(self.ws)
        # The workspace keeps its own history: a repository counts only if
        # the workspace is its top level, never a folder inside another one.
        rc, top = git(self.ws, "rev-parse", "--show-toplevel") \
            if os.path.isdir(self.ws) else (1, "")
        repo = rc == 0 and os.path.normcase(os.path.abspath(top)) == \
            os.path.normcase(self.ws)
        if repo:
            rc, _ = git(self.ws, "diff", "--cached", "--quiet")
            if rc != 0:
                raise Broken("the workspace repository has staged changes; "
                             "commit or unstage them, then rerun")
            self.report.append("- existing git repository kept")
        else:
            self.say("git init " + self.ws)
            if not self.dry:
                self.git("init", "-q")
        self.put(".gitignore", read_kit(os.path.join("workspace",
                                                      ".gitignore")))
        self.put(SETUP + "/answers.json", saved_answers_text(self.ans))

    def phase_systems(self):
        placed = kit_files(bool(self.ans.get("projects")))
        for rel in placed:
            with open(os.path.join(KIT_WS, rel), "rb") as f:
                self.put(rel, f.read())
        self.put(MANIFEST, manifest_text(placed),
                 replace_if=[self.current(MANIFEST)])
        self.report.append("- %d kit files considered" % len(placed))

    def phase_config(self):
        cfg = json.loads(read_kit(os.path.join("workspace", "workspace.json")))
        for k in ("daily_dest", "weekly_dest"):
            v = (self.ans.get("backup") or {}).get(k)
            if v:
                cfg["backup"][k] = v
        cfg.setdefault("board", {})["theme"] = self.ans.get(
            "board_theme", BOARD_THEMES[0])
        tmpl_cfg = read_kit(os.path.join("workspace", "workspace.json"))
        about = str(self.ans.get("about_user") or "").strip()
        prof = read_kit(os.path.join("workspace", "Memory", "global",
                                     "core-profile.md"))
        blank = re.search(r"^\(Name, role[^)]*\)$", prof, re.M | re.S)
        if about and blank:
            self.put("Memory/global/core-profile.md",
                     prof.replace(blank.group(0), about), replace_if=[prof])
        self.put("workspace.json", json.dumps(cfg, indent=2) + "\n",
                 replace_if=[tmpl_cfg])
        template = read_kit(os.path.join("tiers", "project.md"))
        self.put(PROJECT_TEMPLATE, template,
                 replace_if=[self.current(PROJECT_TEMPLATE)])
        projects = self.ans.get("projects") or []
        if not projects:
            return
        tmpl_ten = read_kit(os.path.join("workspace", "Memory",
                                         "tenants.json"))
        ten = json.loads(tmpl_ten)
        ten["tenants"].pop("example-project")
        for p in projects:
            ten["tenants"][p] = project_tenant(p)
            for rel, text in sorted(project_files(p, template).items()):
                self.put(rel, text)
        self.put("Memory/tenants.json", json.dumps(ten, indent=2) + "\n",
                 replace_if=[tmpl_ten])

    def phase_rules(self):
        slot, block, where = placed_texts(self.ans)
        self.report.append("- placement: " + where)
        tmpl = read_kit(os.path.join("workspace", "AGENTS.md"))
        self.put("AGENTS.md", agents_with_block(tmpl, block),
                 replace_if=[tmpl])
        if slot:
            self.put(SETUP + "/account-slot.txt", slot + "\n")
            self.report.append("- paste Setup/account-slot.txt (%d chars) "
                               "into the tool's account-level instructions"
                               % len(slot))

    def tasks(self):
        root = os.path.join(KIT_WS, "Scheduled")
        if not os.path.isdir(root):
            return []
        return sorted(d for d in os.listdir(root) if os.path.exists(
            os.path.join(root, d, "INSTRUCTIONS.md")))

    def phase_scheduler(self):
        sch = self.ans.get("scheduler") or {"kind": "none"}
        tasks = self.tasks()
        if not tasks:
            self.report.append("- no scheduled tasks in this kit version; "
                               "nothing to wire")
            return
        hand = ["# Tasks to run by hand\n",
                "No scheduler is wired. At each time below, start an AI "
                "session that can read files and give it the task's "
                "INSTRUCTIONS.md.\n"]
        for t in tasks:
            tdir = os.path.join(KIT_WS, "Scheduled", t)
            try:
                with open(os.path.join(tdir, "schedule.json"),
                          encoding="utf-8") as f:
                    when = json.load(f)
            except (OSError, ValueError):
                self.hold("task %s has no readable schedule.json; not wired"
                          % t)
                continue
            when["time"] = (sch.get("times") or {}).get(t, when.get("time"))
            if when.get("schedule") not in ("DAILY", "WEEKLY") or not \
                    re.match(r"^\d\d:\d\d$", str(when.get("time"))):
                self.hold("task %s: schedule.json needs schedule DAILY or "
                          "WEEKLY and time HH:MM; not wired" % t)
                continue
            instr = os.path.join(self.ws, "Scheduled", t, "INSTRUCTIONS.md")
            label = "%s %s" % (when.get("schedule", "?"), when["time"]) + (
                " " + when["day"] if when.get("schedule") == "WEEKLY" else "")
            if sch.get("kind") == "none":
                hand.append("- **%s** - %s - `Scheduled/%s/INSTRUCTIONS.md`"
                            % (t, label, t))
                continue
            cmd = sch["launch_command"].format(
                task=t, instructions=instr, workspace=self.ws)
            launch = "Scheduled/%s/launch.cmd" % t
            self.put(launch, '@echo off\r\ncd /d "%s"\r\n%s\r\n'
                     % (self.ws, cmd))
            argv = ["schtasks", "/Create", "/TN", "%s\\%s" % (TASK_PREFIX, t),
                    "/TR", '"%s"' % os.path.join(self.ws, launch),
                    "/SC", when["schedule"], "/ST", when["time"]]
            if when["schedule"] == "WEEKLY":
                argv += ["/D", when.get("day", "SUN")]
            self.wire(t, argv)
        if sch.get("kind") == "none":
            self.put(SETUP + "/hand-run-tasks.md", "\n".join(hand) + "\n",
                     replace_if=[self.current(SETUP + "/hand-run-tasks.md")])
            for line in hand[2:]:
                print("HAND-RUN " + line[2:])

    def wire(self, task, argv):
        shown = " ".join(argv)
        if self.dry or not self.register:
            self.say("register: " + shown)
            if not self.dry:
                self.report.append("- not registered (--no-register): "
                                   + shown)
            return
        tn = argv[3]
        if subprocess.run(["schtasks", "/Query", "/TN", tn],
                          capture_output=True).returncode == 0:
            self.hold("scheduler entry %s already exists; left as is" % tn)
            return
        r = subprocess.run(argv, capture_output=True, text=True)
        if r.returncode != 0:
            self.hold("could not register %s: %s" % (
                tn, (r.stdout + r.stderr).strip()))
        else:
            self.report.append("- registered " + tn)

    def phase_stamp(self):
        self.put("VERSION", read_kit("VERSION"))

    # -- driver
    def run(self, stop_after=None):
        st = self.load_state()
        done = st.get("phases_done", [])
        if all(p in done for p in PHASES):
            print("NOTHING TO DO: every install phase is already done in "
                  + self.ws)
            return 0
        st["kit_version"] = read_kit("VERSION").splitlines()[0].strip()
        for n, name in enumerate(PHASES, 1):
            if name in done:
                print("skip phase %d %s (already done)" % (n, name))
                continue
            print("== phase %d/%d %s" % (n, len(PHASES), name))
            getattr(self, "phase_" + name)()
            self.flush_report(name)
            done.append(name)
            st["phases_done"] = done
            self.save_state(st)
            self.commit(n, name)
            if stop_after == name:
                print("STOPPED after phase %s, as asked; rerun to resume"
                      % name)
                return 3 if self.held else 0
        for h in self.held:
            print("HELD " + h)
        if self.dry:
            print("DRY RUN: nothing was written")
            return 0
        if self.held:
            print("DONE with %d item(s) to act on; see "
                  "Setup/install-report.md" % len(self.held))
            return 3
        print("DONE: installation complete in " + self.ws)
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--answers")
    g.add_argument("--workspace")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stop-after", choices=PHASES)
    ap.add_argument("--no-register", action="store_true")
    a = ap.parse_args(argv)
    try:
        pre = check_prereqs()
        if a.check:
            print(json.dumps(pre, indent=2))
            return 0 if pre["ok"] else 2
        if not pre["ok"]:
            missing = [k for k, v in pre.items()
                       if isinstance(v, dict) and not v["ok"]]
            raise Broken("prerequisite missing: " + ", ".join(missing) +
                         " (run --check for fixes)")
        code = 0
        if a.answers:
            # utf-8-sig: Windows PowerShell writes a byte-order mark.
            with open(a.answers, encoding="utf-8-sig") as f:
                ans = json.load(f)
            validate(ans)
            saved = os.path.join(ans["workspace"], SETUP, "answers.json")
            if os.path.exists(saved):
                with open(saved, encoding="utf-8-sig") as f:
                    old = json.load(f)
                if comparable(old) != comparable(dict(ans, schema=1)):
                    print("HELD answers differ from the saved %s; the saved "
                          "answers are used. Edit that file to change them."
                          % saved)
                    ans, code = old, 3
        else:
            saved = os.path.join(a.workspace, SETUP, "answers.json")
            if not os.path.exists(saved):
                raise Broken("no saved answers at " + saved)
            with open(saved, encoding="utf-8-sig") as f:
                ans = json.load(f)
            validate(ans)
        rc = Installer(ans, a.dry_run, not a.no_register).run(a.stop_after)
        return max(rc, code) if rc in (0, 3) else rc
    except Broken as e:
        print("BROKEN: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
