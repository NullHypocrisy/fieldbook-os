"""doctor.py - is this installation healthy? One pass, any time.

Each check prints PASS, WARN (drifting) or FAIL (needs your hand) and, for
anything short of PASS, the fix. The doctor names fixes; it never applies
them, and it changes nothing except its own run-log line and, with
--report, its own bundle.

  tree             every file in Setup/manifest.json is present (format:
                   workspace_common.py); no unmerged .fieldbook-new sidecar
  workspace rules  AGENTS.md present and carrying what the installer placed;
                   no rule file starting with a byte-order mark, which can
                   break CLAUDE.md's @AGENTS.md import
  account tier     the account-level text ready (Setup/account-slot.txt) or
                   the no-slot fallback in AGENTS.md; no script can read an
                   AI tool's settings, so it prints what to confirm with it
  answers          Setup/answers.json present and parseable
  version          VERSION present, line 1 major.minor.patch
  scheduled        each scheduled piece's last run, or "never run"
  backup           a destination set (none is a WARN), reachable, and fresh;
                   one on the workspace's own disk passes, its tradeoff
                   named; backup.encrypted recorded in the answers (false,
                   or not recorded, is a WARN; the board marks the same);
                   the last restore drill passed (never run is no verdict)
  rule keys        every rule key in the placed-rules block of AGENTS.md
                   and in each Projects/<name>/PROJECT.md is a known key
                   (Setup/rule-keys.json); unknown or renamed is a WARN
  git              the workspace is its own git repository, with history
  smoke            Maintenance/smoke_test.py passes (it works in a copy)
  dashboard        the board builds from a copy of this workspace, and the
                   smoke test's empty and populated builds passed

Thresholds and log readers are the board's own (dashboard_build.py), so the
doctor and the board never disagree. The doctor's line goes to
Scheduled/runs.log as task "doctor"; the board's Doctor chip reads it.

Usage:  python Maintenance/doctor.py [--no-smoke] [--report]
        python Maintenance/doctor.py --issue BUNDLE [--problem FILE]
                                     [--out FILE]
  --no-smoke  skip the smoke and dashboard checks (seconds, not a minute);
              the log line says they were skipped
  --report    also write a diagnostic bundle, Temp/managed/doctor-report-
              YYYYMMDD-HHMM/ (14-day manifest line): summary.md marking
              every item PASS / WARN / FAIL (UNKNOWN where this OS cannot
              tell), the doctor and smoke output, the install journal,
              installer state, each scheduled job as the scheduler reports
              it (Windows: Task Scheduler, folder "Fieldbook OS"), time
              zone, leftover sidecars, byte-order marks, the last 20
              commits, Python, Git and AI tool versions, kit VERSION, and
              .env key names. No .env value is ever written; any that
              shows up in a copied file is replaced with <redacted>.
  --issue     compose the public issue body from BUNDLE's summary: the
              problem text (FILE, the user's words) first, then the
              summary table, then not-passing details, trimmed from the
              end to 6,000 characters; workspace and home paths, login and
              machine names replaced. Written to --out (default
              BUNDLE/issue.md). The same text serves both filing routes.
Exit codes (tools convention): 0 every check PASS (--issue: written); 1
crashed; 2 at least one FAIL (--issue: no bundle there); 3 WARNs and no
FAIL.
"""

import argparse
import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)
from workspace_common import (JOURNAL, JOURNAL_LINE,  # noqa: E402
                              MANIFEST, MARK_BEGIN, MARK_END, RULE_KEYS,
                              SMOKE_NESTED,
                              git, home_journal, machine_zone,
                              workspace_root)
import dashboard_build as board  # noqa: E402

ROOT = workspace_root(HERE)
SIDECAR = ".fieldbook-new"
RANK = {"PASS": 0, "WARN": 1, "FAIL": 2}
RESULTS = []    # (name, status, detail, fix)
CONFIRM = []
PLACE_FIX = ("place the rule tiers: paste the kit's tiers/account.md "
             "({WORKSPACE} filled in, {TIMEZONE} with this machine's time "
             "zone) into your AI tool's "
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


RULE_FILES = ("AGENTS.md", "CLAUDE.md", "Setup/account-slot.txt")


def check_workspace_rules():
    res = workspace_rules()
    boms = []
    for rel in RULE_FILES:
        try:
            with open(path(rel), "rb") as f:
                if f.read(3) == b"\xef\xbb\xbf":
                    boms.append(rel)
        except OSError:
            pass
    if not boms or res[0] == "FAIL":
        return res
    return ("WARN", "%s start%s with a byte-order mark, which can break the "
            "@AGENTS.md import%s" % (", ".join(boms), "s" if len(boms) == 1
                                     else "", "; " + res[1] if res[0] ==
                                     "WARN" else ""),
            "save %s as UTF-8 without a byte-order mark%s" % (
                " and ".join(boms), " / " + res[2] if res[2] else ""))


def workspace_rules():
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


def same_disk(dest):
    """True when the backup destination sits on the workspace's own disk."""
    try:
        return os.stat(dest).st_dev == os.stat(ROOT).st_dev
    except OSError:
        return False


def check_backup():
    try:
        cfg = json.loads(read(path("workspace.json"))).get("backup", {})
    except (OSError, ValueError) as e:
        return ("FAIL", "workspace.json is unreadable (%s)" % e,
                "restore it: git checkout -- workspace.json")
    tiers = [t for t in ("daily", "weekly") if cfg.get(t + "_dest")]
    if not tiers:
        return ("WARN", "no backups: no destination is set (the board "
                "files this once to waiting-on-you)", "set daily_dest or "
                "weekly_dest in workspace.json to a folder outside the "
                "workspace: another drive or a synced cloud folder, or "
                "this disk if nothing else is available")
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
                found.append(("PASS", "%s: last %s%s" % (
                    t, snap[0].strftime("%Y-%m-%d"), " (same disk as the "
                    "workspace: it does not survive that disk failing)"
                    if same_disk(dest) else ""), None))
    enc = board.backup_encryption()
    if enc and enc[0] != "ok":
        found.append(("WARN", enc[1], "record the answer: set "
                      "backup.encrypted in Setup/answers.json to true "
                      "(the destination is encrypted) or false (you accept "
                      "unencrypted backups)" if "not recorded" in enc[1]
                      else "to clear it, move the backups to an encrypted "
                      "drive or folder, then set backup.encrypted to true "
                      "in Setup/answers.json"))
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


KEY_LINES = (("account", re.compile(r"^\d+\. ([^:\n]+): ")),
             ("working-style", re.compile(r"^- ([^:\n]+): ")))
PROJECT_KEY = re.compile(r"^## (.+?)\s*$")


def rule_keys():
    """The known-keys file (format: its _about): the installed copy, else
    the kit's own beside the workspace. None when neither reads."""
    for p in (path(RULE_KEYS), os.path.join(ROOT, "..", "tiers",
                                            "keys.json")):
        try:
            return json.loads(read(p))
        except (OSError, ValueError):
            continue
    return None


def key_findings(where, keys, tiers, known):
    """[(text, fix)] for each key found in where that tiers do not know."""
    out = []
    for k in keys:
        if any(k in known.get(t, {}).get("keys", []) for t in tiers):
            continue
        new = next((known[t]["renamed"][k] for t in tiers
                    if k in known.get(t, {}).get("renamed", {})), None)
        if new:
            out.append(("%s: %r was renamed to %r" % (where, k, new),
                        "in %s, change %r to %r" % (where, k, new)))
        else:
            out.append(("%s: unknown key %r" % (where, k), "in %s, change "
                        "%r to one of the known keys (%s); a rule of your "
                        "own goes %s" % (where, k, ", ".join(
                            k2 for t in tiers for k2 in known.get(t, {})
                            .get("keys", [])), "under 'Rules for this "
                            "project'" if tiers == ("project",) else
                            "outside the placed-rules markers")))
    return out


def check_rule_keys():
    known = rule_keys()
    if known is None:
        return ("WARN", "no known-keys list (%s), so rule keys cannot be "
                "checked" % RULE_KEYS, "run upgrade.py from the kit, or "
                "copy the kit's tiers/keys.json to " + RULE_KEYS)
    found, files = [], 0
    block = placed_block() if os.path.exists(path("AGENTS.md")) else None
    if block:
        files += 1
        keys = [m.group(1).strip() for line in block.splitlines()
                for _, rx in KEY_LINES for m in [rx.match(line)] if m]
        found += key_findings("AGENTS.md (placed rules)", keys,
                              ("account", "working-style"), known)
    pdir = path("Projects")
    for name in sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []:
        pf = os.path.join(pdir, name, "PROJECT.md")
        if not os.path.isfile(pf):
            continue
        files += 1
        keys = [m.group(1) for line in read(pf).splitlines()
                for m in [PROJECT_KEY.match(line)] if m]
        found += key_findings("Projects/%s/PROJECT.md" % name, keys,
                              ("project",), known)
    if found:
        return ("WARN", "; ".join(f[0] for f in found),
                " / ".join(f[1] for f in found))
    return ("PASS", "every rule key known (%d file%s)" % (
        files, "" if files == 1 else "s"), None)


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


# ---------------------------------------------------------------- report

REPORT_DAYS = 14
ISSUE_CAP = 6000
SCHED_FOLDER = "\\Fieldbook OS\\"   # install.py registers every job here
NEVER_RUN, RUNNING = 267011, 267009   # Task Scheduler result codes
SCHED_QUERY = r"""
$ProgressPreference = 'SilentlyContinue'
$t = @(Get-ScheduledTask -TaskPath '%s' -ErrorAction SilentlyContinue)
$o = foreach ($x in $t) {
  $i = Get-ScheduledTaskInfo -InputObject $x
  [pscustomobject]@{
    name = $x.TaskName; state = [string]$x.State
    action = (@($x.Actions | ForEach-Object {
      ($_.Execute + ' ' + $_.Arguments).Trim() }) -join '; ')
    triggers = (@($x.Triggers | ForEach-Object {
      [string]$_.StartBoundary }) -join '; ')
    last_run = $(if ($i.LastRunTime) {
      $i.LastRunTime.ToString('yyyy-MM-dd HH:mm') } else { '' })
    last_result = $i.LastTaskResult
    next_run = $(if ($i.NextRunTime) {
      $i.NextRunTime.ToString('yyyy-MM-dd HH:mm') } else { '' })
  }
}
ConvertTo-Json -InputObject @($o) -Depth 3
""" % SCHED_FOLDER


def env_entries():
    """[(key, value)] from every .env file in the workspace. Values are
    used only to scrub them out of the bundle, never written anywhere."""
    out = []
    for dirpath, dirnames, files in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git",
                                                        "__pycache__")]
        for fn in files:
            if fn == ".env" or fn.endswith(".env"):
                for line in read(os.path.join(dirpath, fn)).splitlines():
                    m = re.match(r"^\s*(?:export\s+)?([A-Za-z_]\w*)\s*=\s*"
                                 r"(.*?)\s*$", line)
                    if m:
                        out.append((m.group(1), m.group(2).strip("'\"")))
    return out


def scrub(text, values):
    for v in sorted(values, key=len, reverse=True):
        text = text.replace(v, "<redacted>")
    return text


def run_cmd(argv, timeout=60, merge=True):
    """(returncode, output) or (None, why) when it could not run; merge
    False returns stdout alone (stderr only when the run failed)."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL,
                           errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return None, repr(e)
    out = r.stdout if not merge and r.returncode == 0 else \
        r.stdout + r.stderr
    return r.returncode, out.strip()


def query_scheduler():
    """(jobs by name, raw text); jobs is None when the scheduler could
    not be asked (a different OS, or the query failed)."""
    if platform.system() != "Windows":
        return None, "this OS's scheduler is not queried (Windows only)"
    import base64
    enc = base64.b64encode(SCHED_QUERY.encode("utf-16-le")).decode()
    rc, out = run_cmd(["powershell", "-NoProfile", "-NonInteractive",
                       "-EncodedCommand", enc], timeout=120, merge=False)
    if rc != 0:
        return None, "query failed (%s): %s" % (rc, out[-500:])
    try:
        jobs = json.loads(out or "[]")
    except ValueError:
        return None, "query output is not JSON: " + out[-500:]
    if isinstance(jobs, dict):
        jobs = [jobs]
    return {j.get("name"): j for j in jobs if isinstance(j, dict)}, out


def job_rows(ans):
    """[(item, status, detail)] for every scheduled job, and the raw
    scheduler answer for the bundle."""
    sdir = path("Scheduled")
    tasks = sorted(d for d in os.listdir(sdir) if os.path.isfile(
        os.path.join(sdir, d, "INSTRUCTIONS.md"))) \
        if os.path.isdir(sdir) else []
    hand = ((ans or {}).get("scheduler") or {}).get("kind") == "none"
    jobs, raw = query_scheduler()
    rows = []
    for t in sorted(set(tasks) | set(jobs or {})):
        name = "job " + t
        if jobs is None:
            rows.append((name, "UNKNOWN", raw))
            continue
        j = jobs.get(t)
        if not j:
            rows.append((name, "PASS", "run by hand, as chosen at setup")
                        if hand else (name, "FAIL", "not registered with "
                                      "the scheduler (%s)" % SCHED_FOLDER))
            continue
        res, last = j.get("last_result"), j.get("last_run") or "never"
        if j.get("state") == "Disabled":
            rows.append((name, "WARN", "registered but disabled"))
        elif res == NEVER_RUN:
            rows.append((name, "WARN", "registered, never run; next %s"
                         % (j.get("next_run") or "not scheduled")))
        elif res in (0, RUNNING):
            rows.append((name, "PASS", "last run %s, %s" % (
                last, "running now" if res == RUNNING else "result 0")))
        else:
            rows.append((name, "FAIL", "last run %s, result %s (0x%X)" % (
                last, res, res & 0xFFFFFFFF if isinstance(res, int)
                else 0)))
    return rows, raw


def ai_tool_version(ans):
    cmd = (((ans or {}).get("scheduler") or {}).get("launch_command")
           or "").strip()
    m = re.match(r'"([^"]+)"|(\S+)', cmd)
    if not m:
        return "UNKNOWN", "no AI launch command recorded"
    tok = m.group(1) or m.group(2)
    rc, out = run_cmd([shutil.which(tok) or tok, "--version"])
    line = (out or "").splitlines()[0].strip() if out else ""
    if rc != 0 or not line:
        return "UNKNOWN", "%s --version did not answer (%s)" % (tok, rc)
    return "PASS", "%s: %s" % (tok, line)


def report_items(smoke_out):
    """[(item, status, detail)] beyond the doctor's own checks, and
    {bundle file name: text}."""
    items, files = [], {}
    jp, hp = path(JOURNAL), home_journal()
    text = read(jp) if os.path.isfile(jp) else ""
    home = read(hp) if os.path.isfile(hp) else ""
    lines = [l for l in (text + home).splitlines() if l.strip()]
    odd = sum(1 for l in lines if not JOURNAL_LINE.match(l))
    if not lines:
        items.append(("journal", "WARN", "no install journal (%s)" % JOURNAL))
    else:
        items.append(("journal", "WARN" if home else "PASS", "%d line%s%s%s"
                      % (len(lines), "" if len(lines) == 1 else "s",
                         ", %d not in the line format (kept as written)"
                         % odd if odd else "", "; %d still in the home-"
                         "folder journal" % len(home.splitlines())
                         if home else "")))
        files["journal.txt"] = text + ("\n# still in the home-folder "
                                       "journal:\n" + home if home else "")
    sp = path("Setup/install-state.json")
    if not os.path.isfile(sp):
        items.append(("installer state", "WARN", "no Setup/install-state."
                      "json (not built by install.py)"))
    else:
        try:
            done = json.loads(read(sp)).get("phases_done", [])
            items.append(("installer state", "PASS" if "stamp" in done
                          else "WARN", "phases done: %s" % (
                              ", ".join(done) or "none")))
        except (ValueError, AttributeError) as e:
            items.append(("installer state", "FAIL", "Setup/install-state."
                          "json unreadable (%s)" % e))
    for rel in ("install-state.json", "install-report.md",
                "upgrade-report.md", "hand-run-tasks.md"):
        if os.path.isfile(path("Setup/" + rel)):
            files["setup-" + rel] = read(path("Setup/" + rel))
    files["smoke.txt"] = smoke_out or "(smoke test skipped: --no-smoke)\n"
    ans, _ = answers()
    rows, raw = job_rows(ans)
    items += rows
    files["scheduler.txt"] = raw + "\n"
    zone = machine_zone()
    items.append(("time zone", "PASS" if zone else "UNKNOWN",
                  zone or "the machine's time zone could not be read"))
    sidecars = []
    for dirpath, dirnames, fs in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git",
                                                        "__pycache__")]
        sidecars += [os.path.relpath(os.path.join(dirpath, f), ROOT)
                     .replace("\\", "/") for f in fs if f.endswith(SIDECAR)]
    items.append(("leftover sidecars", "WARN" if sidecars else "PASS",
                  ", ".join(sidecars) or "none"))
    boms = []
    for rel in RULE_FILES:
        try:
            with open(path(rel), "rb") as f:
                if f.read(3) == b"\xef\xbb\xbf":
                    boms.append(rel)
        except OSError:
            pass
    items.append(("byte-order marks", "WARN" if boms else "PASS",
                  ", ".join(boms) or "none in " + ", ".join(RULE_FILES)))
    rc, log = git(ROOT, "log", "-20", "--date=format:%Y-%m-%d %H:%M",
                  "--format=%h %ad %s")
    items.append(("git history", "PASS" if rc == 0 else "FAIL",
                  "last %d commit%s in git-log.txt" % (
                      len(log.splitlines()), "" if len(log.splitlines()) == 1
                      else "s") if rc == 0 else "no history: " + log[:200]))
    files["git-log.txt"] = log + "\n"
    items.append(("python", "PASS", platform.python_version()))
    rc, out = run_cmd(["git", "--version"])
    items.append(("git version", "PASS" if rc == 0 else "UNKNOWN",
                  out if rc == 0 else "git --version did not answer"))
    items.append(("AI tool",) + ai_tool_version(ans))
    vp = path("VERSION")
    first = (read(vp).splitlines() or [""])[0].strip() \
        if os.path.isfile(vp) else ""
    items.append(("kit version", "PASS" if first else "WARN",
                  first or "no VERSION file"))
    keys = sorted(set(k for k, _ in env_entries()))
    if keys:
        files["env-keys.txt"] = ("Key names in the workspace's .env files "
                                 "(values are never copied):\n"
                                 + "\n".join(keys) + "\n")
    return items, files


def summary_text(items, files):
    zone = machine_zone() or "UNKNOWN"
    out = ["# Fieldbook OS diagnostic report", "",
           "Generated %s (machine time zone %s) on %s." % (
               datetime.now().strftime("%Y-%m-%d %H:%M"), zone,
               platform.platform()), "",
           "| Item | Status | Detail |", "|---|---|---|"]
    for name, status, detail, _ in items:
        out.append("| %s | %s | %s |" % (name, status, str(detail).replace(
            "|", "/").replace("\n", " ")[:300]))
    out += ["", "## Not passing", ""]
    bad = [i for i in items if i[1] != "PASS"]
    for name, status, detail, fix in bad:
        out += ["### %s (%s)" % (name, status), "", str(detail)]
        if fix:
            out.append("fix: " + fix)
        out.append("")
    if not bad:
        out += ["Nothing: every item passed.", ""]
    out += ["## In this bundle", ""] + ["- " + f for f in sorted(files)]
    return "\n".join(out) + "\n"


def write_report(doctor_text, smoke_out):
    """Write the bundle; return its workspace-relative folder."""
    items, files = report_items(smoke_out)
    rows = [(n, s, d, f) for n, s, d, f in RESULTS] + \
        [(n, s, d, None) for n, s, d in items]
    files["doctor.txt"] = doctor_text
    files["summary.md"] = summary_text(rows, files)
    secrets = [v for _, v in env_entries() if len(v) >= 4]
    stamp = datetime.now()
    rel = "Temp/managed/doctor-report-" + stamp.strftime("%Y%m%d-%H%M")
    base, n = rel, 1
    while os.path.exists(path(rel)):
        n += 1
        rel = "%s-%d" % (base, n)
    os.makedirs(path(rel))
    for name, text in files.items():
        with open(os.path.join(path(rel), name), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(scrub(text, secrets))
    man = path("Temp/managed/manifest.md")
    with open(man, "a", encoding="utf-8") as f:
        f.write("%s | %s | %s | doctor.py --report bundle\n" % (
            stamp.date(), stamp.date() + timedelta(days=REPORT_DAYS), rel))
    return rel


def anonymize(text):
    """Workspace and home paths, login and machine names out of text."""
    pairs = [(ROOT, "<workspace>"), (os.path.expanduser("~"), "<home>")]
    for p, tag in list(pairs):
        pairs += [(p.replace("\\", "/"), tag), (p.replace("/", "\\"), tag)]
    for p, tag in sorted(pairs, key=lambda x: -len(x[0])):
        if len(p) > 3:
            text = re.sub(re.escape(p), tag, text, flags=re.I)
    for name, tag in ((getpass.getuser(), "<user>"),
                      (platform.node(), "<machine>")):
        if name and len(name) > 1:
            text = re.sub(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])"
                          % re.escape(name), tag, text, flags=re.I)
    return text


def issue_body(bundle, problem=""):
    """The public issue text: the problem in the user's words, the summary
    table, then not-passing details trimmed from the end to fit ISSUE_CAP.
    The same text serves gh issue create and the prefilled link."""
    summary = read(os.path.join(bundle, "summary.md"))
    secrets = [v for _, v in env_entries() if len(v) >= 4]
    summary = anonymize(scrub(summary, secrets))
    problem = anonymize(scrub(problem.strip(), secrets))
    head, _, rest = summary.partition("\n## Not passing\n")
    details = re.split(r"(?m)^(?=### )", rest.split("\n## In this bundle",
                                                    1)[0])
    details = [d for d in details if d.startswith("### ")]
    top = ("## What happened\n\n%s\n\n" % problem if problem else "")
    note = ("\n(Trimmed to fit: %d more not-passing detail(s) stay in the "
            "reporter's local bundle.)\n")
    keep = len(details)
    while True:
        body = top + head.rstrip() + "\n"
        if details:
            body += "\n## Not passing\n\n" + "".join(details[:keep]).rstrip() \
                + "\n" + (note % (len(details) - keep)
                          if keep < len(details) else "")
        if len(body) <= ISSUE_CAP or keep == 0:
            break
        keep -= 1
    if len(body) > ISSUE_CAP and top:
        over = len(body) - ISSUE_CAP + 20
        top = "## What happened\n\n%s ...(trimmed)\n\n" % problem[:max(
            0, len(problem) - over)]
        body = top + head.rstrip() + "\n" + (
            note % len(details) if details else "")
    return body


# ------------------------------------------------------------------ main

def log_run(code, summary):
    """The doctor's own line, through the run log's one writer."""
    sys.path.insert(0, os.path.join(ROOT, "Scheduled"))
    import runlog
    runlog.record("doctor", code, summary, path=board.RUNS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-smoke", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--issue", metavar="BUNDLE")
    ap.add_argument("--problem", metavar="FILE")
    ap.add_argument("--out", metavar="FILE")
    args = ap.parse_args()
    if args.issue:
        bundle = os.path.join(ROOT, args.issue)
        if not os.path.isfile(os.path.join(bundle, "summary.md")):
            print("BROKEN: no summary.md in " + bundle)
            return 2
        body = issue_body(bundle, read(args.problem) if args.problem
                          else "")
        out = args.out or os.path.join(bundle, "issue.md")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        print("ISSUE BODY: %s (%d characters)" % (out, len(body)))
        return 0
    checks = [("tree", check_tree), ("workspace rules", check_workspace_rules),
              ("account tier", check_account_tier),
              ("answers", check_answers), ("version", check_version),
              ("scheduled", check_scheduled), ("backup", check_backup),
              ("rule keys", check_rule_keys), ("git", check_git)]
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
    shown = []

    def say(line):
        print(line)
        shown.append(line)
    for name, status, detail, fix in RESULTS:
        say("%-4s  %-15s  %s" % (status, name, detail))
        if fix:
            say("%23s%s" % ("fix: ", fix))
    if CONFIRM:
        say("\nConfirm with your AI (no script can read its settings):")
        for c in CONFIRM:
            say("- " + c)
    bad = {s: [n for n, st, _, _ in RESULTS if st == s]
           for s in ("FAIL", "WARN")}
    code = 2 if bad["FAIL"] else 3 if bad["WARN"] else 0
    summary = "; ".join("%s: %s" % (s, ", ".join(n)) for s, n in bad.items()
                        if n) or "PASS"
    if args.no_smoke:
        summary += " (smoke and dashboard skipped)"
    log_run(code, summary)
    say("\nDOCTOR: %s" % (summary if code else
                          "PASS - every check passed" + summary[4:]))
    if args.report:
        rel = write_report("\n".join(shown) + "\n", smoke_out[0])
        print("REPORT: %s/summary.md" % rel)
    return code


if __name__ == "__main__":
    sys.exit(main())
