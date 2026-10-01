"""upgrade.py - bring an installed Fieldbook OS workspace up to this kit.

Run from the newer kit, beside install.py. Standard library only.

Usage:
  python upgrade.py --workspace DIR [--dry-run]  preview: print every
                                               planned action, write nothing
                                               (--dry-run as in install.py)
  python upgrade.py --workspace DIR --apply    do it

What it reads: the workspace's VERSION (the installed kit version), its
saved answers (Setup/answers.json, never re-asked), its install hashes
(Setup/hashes.json, install.py) and this kit's manifests/<installed
version>.json (release_manifest.py). It renders what this kit would install
from the saved answers, then per file:
  same as installed, or the kit did not change it   nothing
  new in this kit                                  add
  installed and never modified                      replace
  installed and modified by the adopter             never overwritten: this
      kit's version lands beside it as NAME.fieldbook-new (install.py's
      sidecar, one meaning), listed in Setup/upgrade-report.md to merge
  removed by the adopter, changed by the kit        left removed, reported
  no longer in the kit, never modified              moved to Quarantine/ with
      a manifest line (the workspace's own retirement rule)
  no longer in the kit, modified                    kept, reported
"Never modified" means the file still hashes to what the installer or the
last upgrade left, or to what the installed version's manifest ships. No
merge is ever attempted; the adopter's AI merges each sidecar.

A question this kit's installer asks (install.ANSWERS_ABOUT) that the saved
answers never had is listed for the AI to ask; --apply refuses until each
is answered in Setup/answers.json. New scheduled tasks are copied, not
wired, and reported. Setup/ and VERSION are the installer's own and are
rewritten. --apply brackets the run in two git commits (before, after),
appends one line to today's day log, Memory/global/logs/YYYY-MM-DD.md, and
appends start and finish lines (or the failure) to the install journal
(Maintenance/README.md owns its format); a preview writes none.

Exit codes (tools/EXIT-CODES.md): 0 done, previewed, or nothing to do (the
printed word says which); 1 crashed; 2 broken (no VERSION or answers, not
its own git repository, staged changes, downgrade, git failed); 3 held
(questions to answer, sidecars to merge, or something else to act on).
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import install  # noqa: E402
from install import HASHES, SETUP, SIDECAR, Broken, sha  # noqa: E402
from release_manifest import MANIFESTS, kit_version  # noqa: E402
from workspace_common import (MANIFEST, git, git_identity,  # noqa: E402
                              journal, manifest_tracked)

REPORT = SETUP + "/upgrade-report.md"


class Renderer(install.Installer):
    """What this kit would install from the saved answers, captured."""

    def __init__(self, ans):
        super().__init__(ans, dry=False, register=False)
        self.out = {}

    def say(self, msg):
        pass

    def current(self, rel):
        return b""

    def put(self, rel, data, replace_if=()):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.out[rel.replace("\\", "/")] = data


def render(ans):
    r = Renderer(ans)
    r.put(".gitignore", install.read_kit(os.path.join("workspace",
                                                      ".gitignore")))
    for phase in ("systems", "config", "rules", "stamp"):
        getattr(r, "phase_" + phase)()
    return r.out, r.tasks()


def vt(v):
    return tuple(int(x) for x in v.split("."))


def load_json(p, key=None):
    try:
        with open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d[key] if key else d
    except (OSError, ValueError, KeyError, TypeError):
        return None


class Upgrade:
    def __init__(self, ws, cmdline="upgrade.py"):
        self.ws = os.path.abspath(ws)
        self.cmdline = cmdline
        self.plan = []          # (action, rel, data)
        self.lines = []         # report lines
        self.held = []

    def p(self, rel):
        return os.path.join(self.ws, *rel.split("/"))

    def cur(self, rel):
        try:
            with open(self.p(rel), "rb") as f:
                return f.read()
        except OSError:
            return None

    def note(self, line, held=False):
        self.lines.append(("- HELD " if held else "- ") + line)
        if held:
            self.held.append(line)

    # ------------------------------------------------------------ plan
    def load(self):
        if not os.path.isdir(self.ws):
            raise Broken("no workspace at " + self.ws)
        v = (self.cur("VERSION") or b"").decode("utf-8", "replace")
        self.old = v.splitlines()[0].strip() if v.strip() else ""
        if not re.match(r"^\d+\.\d+\.\d+$", self.old):
            raise Broken("the workspace has no readable VERSION, so there is "
                         "no baseline to upgrade from (run "
                         "Maintenance/doctor.py for the fix)")
        self.new = kit_version()
        ans = load_json(self.p(SETUP + "/answers.json"))
        if not isinstance(ans, dict) or ans.get("schema") != 1:
            raise Broken("no readable Setup/answers.json (format 1); the "
                         "upgrade reads the install's answers and never "
                         "re-asks them")
        self.ans = install.drop_retired(ans)
        asked = set(ans.get("_about") or {}) | set(ans)
        self.questions = [k for k in install.ANSWERS_ABOUT if k not in asked]
        self.oldman = load_json(os.path.join(
            MANIFESTS, self.old + ".json"), "files") or {}
        if not self.oldman and vt(self.old) < vt(self.new):
            self.note("this kit has no manifest for %s; only files the "
                      "installer recorded count as unmodified" % self.old)
        self.recorded = load_json(self.p(HASHES), "files") or {}

    def make_plan(self):
        out, tasks = render(self.ans)
        self.out = out
        for rel in sorted(out):
            if rel == "VERSION" or rel.startswith(SETUP + "/") \
                    or not manifest_tracked(rel):
                continue
            new, cur = out[rel], self.cur(rel)
            base = {h for h in (self.recorded.get(rel),
                                self.oldman.get(rel)) if h}
            if cur == new:
                self.recorded[rel] = sha(new)
                continue
            if sha(new) in base:
                continue
            if cur is None:
                self.plan.append(("removed" if base else "add", rel, new))
            elif sha(cur) in base:
                self.plan.append(("replace", rel, new))
            else:
                self.plan.append(("sidecar", rel, new))
        for rel in sorted(set(self.oldman) - set(out)):
            cur = self.cur(rel)
            if cur is None or not manifest_tracked(rel):
                continue
            base = {h for h in (self.recorded.get(rel),
                                self.oldman.get(rel)) if h}
            self.plan.append(("retire" if sha(cur) in base else "kept",
                              rel, None))
        self.new_tasks = [t for t in tasks if self.cur(
            "Scheduled/%s/INSTRUCTIONS.md" % t) is None]

    def describe(self, action, rel):
        return {
            "add": "add %s" % rel,
            "replace": "replace %s (unmodified)" % rel,
            "sidecar": "sidecar %s%s (you changed %s; yours is kept)"
                       % (rel, SIDECAR, rel),
            "removed": "skip %s (you removed it; the kit changed it)" % rel,
            "retire": "retire %s -> Quarantine/%s (no longer in the kit)"
                      % (rel, rel),
            "kept": "keep %s (no longer in the kit; you changed it)" % rel,
        }[action]

    def show(self):
        print("upgrade %s: %s -> %s" % (self.ws, self.old, self.new))
        for action, rel, _ in self.plan:
            print("PLAN  " + self.describe(action, rel))
        for t in self.new_tasks:
            print("PLAN  new scheduled task %s: copied, not wired" % t)
        print("PLAN  VERSION %s -> %s; Setup/ refreshed" % (self.old,
                                                           self.new))
        print("PLAN  git commits before and after; one day-log line")
        for q in self.questions:
            print("QUESTION %s: %s" % (q, install.ANSWERS_ABOUT[q]))

    # ----------------------------------------------------------- apply
    def git(self, *args):
        rc, out = git(self.ws, *args)
        if rc != 0:
            raise Broken("git %s failed: %s" % (args[0], out))
        return out

    def commit(self, msg, paths=None):
        if paths:
            self.git("add", "-A", "--", *paths)
        else:
            self.git("add", "-A")
        self.git(*(git_identity(self.ws) +
                   ["commit", "-q", "--allow-empty", "-m", msg]))

    def write(self, rel, data):
        path = self.p(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        self.touched.append(rel)

    def check_repo(self):
        rc, top = git(self.ws, "rev-parse", "--show-toplevel")
        if rc != 0 or os.path.normcase(os.path.abspath(top)) != \
                os.path.normcase(self.ws):
            raise Broken("the workspace is not its own git repository; the "
                         "upgrade commits before and after so it can be "
                         "rolled back")
        rc, _ = git(self.ws, "diff", "--cached", "--quiet")
        if rc != 0:
            raise Broken("the workspace repository has staged changes; "
                         "commit or unstage them, then rerun")

    def retire(self, rel):
        dest = "Quarantine/" + rel
        if os.path.exists(self.p(dest)):
            self.note("%s: no longer in the kit, but %s already exists; "
                      "left in place" % (rel, dest), held=True)
            return
        os.makedirs(os.path.dirname(self.p(dest)), exist_ok=True)
        shutil.move(self.p(rel), self.p(dest))
        self.touched += [rel, dest]
        cfg = load_json(self.p("workspace.json")) or {}
        days = int((cfg.get("cleanup") or {}).get("cooling_days", 14))
        today = date.today()
        with open(self.p("Quarantine/manifest.md"), "a",
                  encoding="utf-8") as f:
            f.write("%s | %s | %s | retired by upgrade %s -> %s\n" % (
                today, today + timedelta(days=days), rel, self.old,
                self.new))
        self.touched.append("Quarantine/manifest.md")
        self.recorded.pop(rel, None)
        self.note("retired %s to %s" % (rel, dest))

    def sidecar(self, rel, new):
        side = rel + SIDECAR
        old = self.cur(side)
        if old == new:
            self.note("%s: unmerged, the kit's version is still in %s"
                      % (rel, side), held=True)
            return
        base = {h for h in (self.recorded.get(rel), self.oldman.get(rel))
                if h}
        if old is not None and sha(old) not in base:
            self.note("%s: you changed it and %s holds edits; left both "
                      "alone, this kit's version not placed" % (rel, side),
                      held=True)
            return
        self.write(side, new)
        self.recorded[rel] = sha(new)
        self.note("%s: you changed it, so it was kept; this kit's version "
                  "is beside it as %s to merge" % (rel, side), held=True)

    def apply(self):
        self.check_repo()
        self.touched = []
        tag = "Fieldbook OS upgrade %s -> %s" % (self.old, self.new)
        self.commit(tag + ": before")
        self.journal("start", "%s -> %s, %d planned file action(s)" % (
            self.old, self.new, len(self.plan)))
        for action, rel, data in self.plan:
            if action in ("add", "replace"):
                self.write(rel, data)
                self.recorded[rel] = sha(data)
                self.note(("added " if action == "add" else "replaced ")
                          + rel)
            elif action == "sidecar":
                self.sidecar(rel, data)
            elif action == "retire":
                self.retire(rel)
            elif action == "removed":
                self.note("%s: you removed it; this kit's newer version was "
                          "not placed" % rel, held=True)
            elif action == "kept":
                self.note("%s: no longer in the kit, but you changed it, so "
                          "it was kept" % rel, held=True)
        for t in self.new_tasks:
            self.note("new scheduled task %s: copied to Scheduled/%s/ but "
                      "not wired; add it to your scheduler, or run it by "
                      "hand as Setup/hand-run-tasks.md describes" % (t, t),
                      held=True)
        for rel, data in self.out.items():
            if rel.startswith(SETUP + "/") and self.cur(rel) != data:
                self.write(rel, data)
                if rel == SETUP + "/account-slot.txt":
                    self.note("the account-level text changed: paste "
                              "Setup/account-slot.txt into your AI tool's "
                              "account-level instructions again", held=True)
        self.write("VERSION", self.out["VERSION"])
        self.write(SETUP + "/answers.json",
                   install.saved_answers_text(self.ans))
        st = load_json(self.p(SETUP + "/install-state.json"))
        if isinstance(st, dict):
            st["kit_version"] = self.new
            self.write(SETUP + "/install-state.json",
                       json.dumps(st, indent=2) + "\n")
        self.write(HASHES, json.dumps(
            {"_about": "sha256 of each file as the installer or upgrade.py "
             "last left it; upgrade.py treats a file still matching as "
             "unmodified.", "files": dict(sorted(self.recorded.items()))},
            indent=2) + "\n")
        now = datetime.now()
        counts = {}
        for action, _, _ in self.plan:
            counts[action] = counts.get(action, 0) + 1
        summary = ", ".join("%d %s" % (n, a) for a, n in sorted(
            counts.items())) or "no file changes"
        with open(self.p(REPORT), "a", encoding="utf-8") as f:
            if f.tell() == 0:
                f.write("# Upgrade report\n\nOne section per upgrade. HELD "
                        "lines need the adopter; everything else is a "
                        "record.\n")
            f.write("\n## %s -> %s (%s)\n\n%s\n" % (
                self.old, self.new, now.strftime("%Y-%m-%d %H:%M"),
                "\n".join(self.lines or ["- done, nothing to note"])))
        self.touched.append(REPORT)
        log = "Memory/global/logs/%s.md" % now.strftime("%Y-%m-%d")
        os.makedirs(os.path.dirname(self.p(log)), exist_ok=True)
        with open(self.p(log), "a", encoding="utf-8") as f:
            f.write("- %s Fieldbook OS upgraded %s -> %s: %s; %d to act on "
                    "(Setup/upgrade-report.md)\n" % (
                        now.strftime("%H:%M"), self.old, self.new, summary,
                        len(self.held)))
        self.touched.append(log)
        self.commit(tag, sorted(set(self.touched)))
        for h in self.held:
            print("HELD " + h)
        self.journal("finish", "upgraded %s -> %s: %s; %d held (exit %d)" % (
            self.old, self.new, summary, len(self.held),
            3 if self.held else 0))
        if self.held:
            print("DONE %s -> %s with %d item(s) to act on; see %s"
                  % (self.old, self.new, len(self.held), REPORT))
            return 3
        print("DONE: upgraded %s -> %s" % (self.old, self.new))
        return 0

    def journal(self, step, result):
        journal(self.ws, "upgrade.py", step, self.cmdline, result)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workspace", required=True)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true",
                      help="preview (the default; install.py's flag)")
    a = ap.parse_args(argv)
    cmdline = "python upgrade.py " + " ".join(
        sys.argv[1:] if argv is None else argv)
    try:
        if not shutil.which("git"):
            raise Broken("git is not installed")
        up = Upgrade(a.workspace, cmdline)
        up.load()
        if vt(up.old) > vt(up.new):
            raise Broken("the workspace is at %s, newer than this kit (%s); "
                         "upgrade from a newer kit" % (up.old, up.new))
        if up.old == up.new:
            print("NOTHING TO DO: the workspace is already at %s" % up.new)
            return 0
        up.make_plan()
        up.show()
        if up.questions:
            print("HELD: answer each QUESTION above in Setup/answers.json "
                  "(ask the adopter; never guess), then rerun")
            return 3
        if not a.apply:
            print("PREVIEW: nothing was written; rerun with --apply")
            return 0
        try:
            return up.apply()
        except Broken as e:
            up.journal("apply", "BROKEN: %s" % e)
            raise
        except Exception as e:
            up.journal("apply", "CRASHED: %r" % e)
            raise
    except Broken as e:
        print("BROKEN: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
