"""doctor.py - is this installation healthy? One pass, any time.

Each check prints PASS, WARN (drifting) or FAIL (needs your hand) and, for
anything short of PASS, the fix. The doctor names fixes; it never applies
them, and it changes nothing except its own run-log line.

  tree             every file in Setup/manifest.json is present (format:
                   workspace_common.py); no unmerged .fieldbook-new sidecar
  workspace rules  AGENTS.md present and carrying what the installer placed
  account tier     the account-level text ready (Setup/account-slot.txt) or
                   the no-slot fallback in AGENTS.md; no script can read an
                   AI tool's settings, so it prints what to confirm with it
  answers          Setup/answers.json present and parseable
  version          VERSION present, line 1 major.minor.patch
  scheduled        each scheduled piece's last run, or "never run"
  backup           a destination set, reachable, and fresh; the last restore
                   drill passed (never run is no verdict)
  git              the workspace is its own git repository, with history
  smoke            Maintenance/smoke_test.py passes (it works in a copy)
  dashboard        the board builds from a copy of this workspace, and the
                   smoke test's empty and populated builds passed

Thresholds and log readers are the board's own (dashboard_build.py), so the
doctor and the board never disagree. The doctor's line goes to
Scheduled/runs.log as task "doctor"; the board's Doctor chip reads it.

Usage:  python Maintenance/doctor.py [--no-smoke]
  --no-smoke  skip the smoke and dashboard checks (seconds, not a minute);
              the log line says they were skipped
Exit codes (tools convention): 0 every check PASS; 1 crashed; 2 at least
one FAIL; 3 WARNs and no FAIL.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)
from workspace_common import (MANIFEST, MARK_BEGIN, MARK_END,  # noqa: E402
                              SMOKE_NESTED, git, workspace_root)
import dashboard_build as board  # noqa: E402

ROOT = workspace_root(HERE)
SIDECAR = ".fieldbook-new"
RANK = {"PASS": 0, "WARN": 1, "FAIL": 2}
RESULTS = []    # (name, status, detail, fix)
CONFIRM = []
PLACE_FIX = ("place the rule tiers: paste the kit's tiers/account.md "
             "({WORKSPACE} and {TIMEZONE} filled in) into your AI tool's "
             "account-level instructions and the kept lines of "
             "tiers/working-style.md into AGENTS.md between the lines "
             "%s and %s; a tool with no account-level slot takes both in "
             "AGENTS.md" % (MARK_BEGIN, MARK_END))


def path(rel):
    return os.path.join(ROOT, *rel.split("/"))


def read(p):
    with open(p, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def result(name, status, detail, fix=None):
    RESULTS.append((name, status, detail, fix))


def worst(found):
    """found: [(status, detail, fix)] -> the most severe entry."""
    return max(found, key=lambda f: RANK[f[0]])


def placed_block():
    """Text between the placed-rules markers; None if absent, False if the
    markers are broken."""
    text = read(path("AGENTS.md"))
    b, e = text.count(MARK_BEGIN), text.count(MARK_END)
    if b == e == 0:
        return None
    if b != 1 or e != 1 or text.index(MARK_BEGIN) > text.index(MARK_END):
        return False
    return text.split(MARK_BEGIN, 1)[1].split(MARK_END, 1)[0].strip()


def answers():
    """(parsed answers dict or None, error text or None)."""
    p = path("Setup/answers.json")
    if not os.path.exists(p):
        return None, None
    try:
        ans = json.loads(read(p))
    except ValueError as e:
        return None, "not readable JSON (%s)" % e
    if not isinstance(ans, dict) or ans.get("schema") != 1:
        return None, "not an answers file of format 1"
    return ans, None


# ---------------------------------------------------------------- checks

def check_tree():
    found = []
    sidecars = []
    for dirpath, dirnames, files in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git",
                                                        "__pycache__")]
        sidecars += [os.path.relpath(os.path.join(dirpath, f), ROOT)
                     .replace("\\", "/") for f in files
                     if f.endswith(SIDECAR)]
    if sidecars:
        found.append(("WARN", "unmerged kit version%s: %s" % (
            "s" if len(sidecars) > 1 else "", ", ".join(sidecars)),
            "merge each NAME%s into NAME with your AI, then delete the "
            "sidecar" % SIDECAR))
    mp = path(MANIFEST)
    if not os.path.exists(mp):
        found.append(("WARN", "no %s, so the tree cannot be checked (this "
                      "workspace was not built by install.py)" % MANIFEST,
                      "have your AI compare this folder with the kit's "
                      "workspace/ folder and add anything missing"))
        return worst(found)
    try:
        files = json.loads(read(mp))["files"]
        assert isinstance(files, list)
    except (ValueError, KeyError, TypeError, AssertionError):
        return ("FAIL", "%s is unreadable" % MANIFEST,
                "restore it: git checkout -- %s" % MANIFEST)
    missing = [f for f in files if not os.path.exists(path(f))]
    if missing:
        found.append(("FAIL", "%d of %d files missing: %s%s" % (
            len(missing), len(files), ", ".join(missing[:5]),
            ", ..." if len(missing) > 5 else ""),
            "restore them from git (git checkout -- PATH), a backup, or "
            "the kit's workspace/ folder"))
    found.append(("PASS", "all %d installed files present" % len(files),
                  None))
    return worst(found)


def check_workspace_rules():
    if not os.path.exists(path("AGENTS.md")):
        return ("FAIL", "AGENTS.md is missing, so sessions start without "
                "the workspace rules", "restore it: git checkout -- "
                "AGENTS.md, or copy the kit's workspace/AGENTS.md")
    block = placed_block()
    if block is False:
        return ("FAIL", "the placed-rules markers in AGENTS.md are broken "
                "(each must appear once, begin before end)",
                "repair the two marker lines; git diff AGENTS.md shows what "
                "changed")
    if os.path.exists(path("AGENTS.md" + SIDECAR)):
        return ("WARN", "the kit's newer AGENTS.md waits beside it as "
                "AGENTS.md" + SIDECAR, "merge it into AGENTS.md with your "
                "AI, then delete the sidecar")
    slot = os.path.exists(path("Setup/account-slot.txt"))
    ans, _ = answers()
    if block == "":
        return ("WARN", "the placed-rules block in AGENTS.md is empty",
                PLACE_FIX)
    if block is None and (not slot or (ans and not ans.get(
            "account_slot_chars"))):
        return ("WARN", "AGENTS.md carries no placed rule tiers (an "
                "installation from before the tiers, or rules placed "
                "elsewhere by hand)", PLACE_FIX)
    return ("PASS", "AGENTS.md present, carrying the placed rules"
            if block else "AGENTS.md present; the rules sit in the account "
            "slot", None)


def check_account_tier():
    sp = path("Setup/account-slot.txt")
    block = placed_block() if os.path.exists(path("AGENTS.md")) else None
    if os.path.exists(sp):
        text = read(sp).strip()
        if not text:
            return ("WARN", "Setup/account-slot.txt is empty", PLACE_FIX)
        ans, _ = answers()
        limit = (ans or {}).get("account_slot_chars") or 0
        CONFIRM.append('Ask your AI to quote the first line of its '
                       'account-level instructions. It should read: "%s". '
                       'If not, paste Setup/account-slot.txt into that slot.'
                       % text.splitlines()[0])
        if limit and len(text) > limit:
            return ("WARN", "the account text is %d characters, over the "
                    "%d your tool's slot holds" % (len(text), limit),
                    "move the working-style lines from "
                    "Setup/account-slot.txt into AGENTS.md between the "
                    "placed-rules markers, then paste the shorter text")
        return ("PASS", "account text ready in Setup/account-slot.txt (%d "
                "characters)" % len(text), None)
    if block:
        CONFIRM.append("Ask your AI whether it read AGENTS.md at the start "
                       "of this session. If not, point its read-this-first "
                       "setting at AGENTS.md.")
        return ("PASS", "no account slot in use; the rules ride in "
                "AGENTS.md (the no-slot fallback)", None)
    return ("WARN", "the account-level rules are not placed", PLACE_FIX)


def check_answers():
    ans, err = answers()
    if err:
        return ("FAIL", "Setup/answers.json is %s" % err,
                "restore it: git checkout -- Setup/answers.json, or fix "
                "the syntax where the error points")
    if ans is None:
        return ("WARN", "no Setup/answers.json: this workspace was not "
                "built by install.py, so reruns and upgrades have no saved "
                "answers", "have your AI hold the setup interview and save "
                "the answers as Setup/answers.json (fields: the kit's "
                "install.py, ANSWERS_ABOUT)")
    ws = ans.get("workspace") or ""
    if os.path.normcase(os.path.abspath(ws)) != os.path.normcase(ROOT):
        return ("WARN", "the answers name %s but the workspace is at %s"
                % (ws, ROOT), "set workspace in Setup/answers.json to "
                "this folder")
    return ("PASS", "setup answers saved (format 1)", None)


def check_version():
    p = path("VERSION")
    if not os.path.exists(p):
        return ("WARN", "no VERSION file, so an upgrade has no baseline",
                "copy VERSION from the kit you installed from into this "
                "folder")
    first = (read(p).splitlines() or [""])[0].strip()
    if not re.match(r"^\d+\.\d+\.\d+$", first):
        return ("FAIL", "VERSION line 1 is not a version number (%r)"
                % first[:40], "restore it: git checkout -- VERSION, or "
                "copy it from the kit")
    return ("PASS", "kit version " + first, None)


def check_scheduled():
    sdir = path("Scheduled")
    runs = board.run_log()
    tasks = set(d for d in os.listdir(sdir) if os.path.isfile(
        os.path.join(sdir, d, "INSTRUCTIONS.md"))) \
        if os.path.isdir(sdir) else set()
    tasks |= set(runs) - {"doctor", "restore-drill"}
    if not tasks:
        return ("PASS", "no scheduled pieces installed", None)
    found = []
    for t in sorted(tasks):
        sched = {}
        sj = os.path.join(sdir, t, "schedule.json")
        if os.path.isfile(sj):
            try:
                sched = json.loads(read(sj))
            except ValueError:
                sched = {}
        last = runs.get(t)
        if not last:
            found.append(("WARN", "%s: never run" % t, "check %s is "
                          "registered with your scheduler "
                          "(Setup/install-report.md) or run it by hand "
                          "(Setup/hand-run-tasks.md)" % t))
            continue
        dt, code, res = last
        if code not in (0, 3):
            found.append(("FAIL", "%s: failed on its last run (exit %d, %s)"
                          % (t, code, res), "run %s by hand from "
                          "Scheduled/%s/ and fix what it reports" % (t, t)))
        elif code == 3 or board.age_days(dt) > board.STALE_DAYS.get(
                sched.get("schedule"), 10 ** 6):
            found.append(("WARN", "%s: %s, last run %s" % (
                t, "flagged something" if code == 3 else "overdue",
                dt.strftime("%Y-%m-%d %H:%M")), "read %s's last result in "
                "Scheduled/runs.log; if overdue, check its scheduler "
                "entry" % t))
        else:
            found.append(("PASS", "%s: ran %s" % (
                t, dt.strftime("%Y-%m-%d %H:%M")), None))
    status = worst(found)[0]
    bad = [f for f in found if f[0] != "PASS"]
    detail = "; ".join(f[1] for f in (bad or found))
    fix = " / ".join(f[2] for f in bad) or None
    return (status, detail, fix)


def check_backup():
    try:
        cfg = json.loads(read(path("workspace.json"))).get("backup", {})
    except (OSError, ValueError) as e:
        return ("FAIL", "workspace.json is unreadable (%s)" % e,
                "restore it: git checkout -- workspace.json")
    tiers = [t for t in ("daily", "weekly") if cfg.get(t + "_dest")]
    if not tiers:
        return ("FAIL", "no backup destination is set",
                "set daily_dest or weekly_dest in workspace.json")
    runs = board.backup_runs()
    found = []
    for t in tiers:
        dest = cfg[t + "_dest"]
        dest = dest if os.path.isabs(dest) else os.path.join(ROOT, dest)
        status = runs.get(t, ("", ""))[0]
        if status in ("CRASH", "REFUSED"):
            found.append(("FAIL", "%s: last run %s" % (t, status),
                          "read Maintenance/backup_log.txt, fix what it "
                          "names, then python Maintenance/backup.py --tier "
                          + t))
        elif not os.path.isdir(dest):
            found.append(("FAIL", "%s: destination %s is not reachable"
                          % (t, dest), "reconnect it, or set a new %s_dest "
                          "in workspace.json" % t))
        else:
            snap = board.latest_snapshot(dest)
            if not snap:
                found.append(("WARN", "%s: no backup has landed yet" % t,
                              "run python Maintenance/backup.py --tier "
                              + t))
            elif board.age_days(snap[0]) > board.STALE_DAYS[t]:
                found.append(("WARN", "%s: overdue, last %s" % (
                    t, snap[0].strftime("%Y-%m-%d")), "run python "
                    "Maintenance/backup.py --tier %s and check its "
                    "schedule" % t))
            else:
                found.append(("PASS", "%s: last %s" % (
                    t, snap[0].strftime("%Y-%m-%d")), None))
    import restore_drill  # same folder; the board reads the drill the same way
    drill = board.run_log().get(restore_drill.TASK)
    if not drill:
        found.append(("PASS", "restore drill not run yet", None))
    elif drill[1]:
        found.append(("FAIL", "restore drill failed %s: %s" % (
            drill[0].strftime("%Y-%m-%d %H:%M"), drill[2]),
            "fix what it names, then python Maintenance/restore_drill.py"))
    else:
        found.append(("PASS", "restore drill %s %s" % (
            drill[2].split(":")[0], drill[0].strftime("%Y-%m-%d")), None))
    bad = [f for f in found if f[0] != "PASS"]
    return (worst(found)[0], "; ".join(f[1] for f in (bad or found)),
            " / ".join(f[2] for f in bad) or None)


def check_git():
    if not shutil.which("git"):
        return ("FAIL", "git is not installed", "install Git (git-scm.com, "
                "or 'winget install Git.Git' on Windows)")
    fix = ('run git init in this folder, then python '
           'Maintenance/close_commit.py -m "start history"')
    rc, top = git(ROOT, "rev-parse", "--show-toplevel")
    if rc != 0 or os.path.normcase(os.path.abspath(top)) != \
            os.path.normcase(ROOT):
        return ("FAIL", "this workspace has no git history of its own", fix)
    rc, n = git(ROOT, "rev-list", "--count", "HEAD")
    if rc != 0:
        return ("FAIL", "the repository has no commits yet", fix)
    return ("PASS", "%s commit%s" % (n, "" if n == "1" else "s"), None)


def check_smoke():
    """Returns (result tuple, smoke output)."""
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE,
                            "smoke_test.py")], cwd=ROOT, capture_output=True,
                           text=True, timeout=900,
                           env=dict(os.environ, **{SMOKE_NESTED: "1"}))
    except subprocess.TimeoutExpired:
        return ("FAIL", "the smoke test did not finish in 15 minutes",
                "run python Maintenance/smoke_test.py and see where it "
                "stops"), ""
    out = r.stdout + r.stderr
    passed = len(re.findall(r"^PASS ", out, re.M))
    failed = re.findall(r"^FAIL  (.*)$", out, re.M)
    if r.returncode == 0 and "ALL CHECKS PASSED" in out:
        return ("PASS", "all %d checks passed" % passed, None), out
    return ("FAIL", "%d check%s failed: %s" % (
        len(failed), "" if len(failed) == 1 else "s",
        "; ".join(failed[:3]) or out.strip()[-200:]),
        "run python Maintenance/smoke_test.py and fix the first failing "
        "check"), out


def check_dashboard(smoke_out):
    tmp = tempfile.mkdtemp(prefix="fieldbook-doctor-")
    try:
        ws = os.path.join(tmp, "ws")
        shutil.copytree(ROOT, ws, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "dashboard.html"))
        r = subprocess.run([sys.executable, os.path.join(
            "Maintenance", "dashboard_build.py"), "--out",
            os.path.join(tmp, "page.html")], cwd=ws, capture_output=True,
            text=True, timeout=300)
        out = (r.stdout + r.stderr).strip()
        built = r.returncode in (0, 3) and "Traceback" not in out and \
            os.path.exists(os.path.join(tmp, "page.html"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    fix = ("run python Maintenance/dashboard_build.py and fix what it "
           "reports")
    if not built:
        return ("FAIL", "the board does not build from this workspace "
                "(exit %d): %s" % (r.returncode, out[-200:]), fix)
    missing = [k for k in ("empty", "populated") if not re.search(
        r"^PASS  board %s: builds" % k, smoke_out, re.M)]
    if missing:
        return ("FAIL", "the smoke test's %s board build%s did not pass"
                % (" and ".join(missing), "s" if len(missing) > 1 else ""),
                fix)
    return ("PASS", "builds from this workspace; empty and populated builds "
            "pass in the smoke test", None)


# ------------------------------------------------------------------ main

def log_run(code, summary):
    """The doctor's own line, through the run log's one writer."""
    sys.path.insert(0, os.path.join(ROOT, "Scheduled"))
    import runlog
    runlog.record("doctor", code, summary, path=board.RUNS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-smoke", action="store_true")
    args = ap.parse_args()
    checks = [("tree", check_tree), ("workspace rules", check_workspace_rules),
              ("account tier", check_account_tier),
              ("answers", check_answers), ("version", check_version),
              ("scheduled", check_scheduled), ("backup", check_backup),
              ("git", check_git)]
    smoke_out = [""]

    def smoke():
        res, smoke_out[0] = check_smoke()
        return res
    if not args.no_smoke:
        checks += [("smoke", smoke),
                   ("dashboard", lambda: check_dashboard(smoke_out[0]))]
    for name, fn in checks:
        try:
            result(name, *fn())
        except Exception as e:  # a check that cannot tell is a FAIL
            result(name, "FAIL", "the check could not run: %r" % e,
                   "report this with the doctor's output")
    for name, status, detail, fix in RESULTS:
        print("%-4s  %-15s  %s" % (status, name, detail))
        if fix:
            print("%23s%s" % ("fix: ", fix))
    if CONFIRM:
        print("\nConfirm with your AI (no script can read its settings):")
        for c in CONFIRM:
            print("- " + c)
    bad = {s: [n for n, st, _, _ in RESULTS if st == s]
           for s in ("FAIL", "WARN")}
    code = 2 if bad["FAIL"] else 3 if bad["WARN"] else 0
    summary = "; ".join("%s: %s" % (s, ", ".join(n)) for s, n in bad.items()
                        if n) or "PASS"
    if args.no_smoke:
        summary += " (smoke and dashboard skipped)"
    log_run(code, summary)
    print("\nDOCTOR: %s" % (summary if code else
                            "PASS - every check passed" + summary[4:]))
    return code


if __name__ == "__main__":
    sys.exit(main())
