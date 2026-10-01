"""install_selftest.py - prove install.py end to end in throwaway folders.

Runs full installs from canned answers and asserts: dry-run writes
nothing; the tree and one git commit per phase; the installed workspace,
in use, passes its own smoke test; the install manifest the doctor checks;
a rerun changes nothing; a planted file gets a sidecar, never an
overwrite, while the installer's own files are replaced (a kit with
Windows line endings into an empty folder); resume after a stop redoes no
phase; the close-commit helper commits then exits clean; the machine's
time zone, never an answer's; project names typed as free text; tier
placement per slot size; scheduler wiring (hand-run and Windows, never
registered here).

Usage:  python install_selftest.py [--tmp DIR]
Exit codes: 0 all passed; 1 crashed; 3 a check failed.
"""

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import install  # noqa: E402

FAIL = []


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        (" - " + str(detail)[:300]) if detail and not ok
                        else ""))
    if not ok:
        FAIL.append(name)


def py(script, *args, cwd=None):
    r = subprocess.run([sys.executable, script] + list(args), cwd=cwd,
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def commits(ws):
    r = subprocess.run(["git", "-C", ws, "log", "--format=%s"],
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l]


def answers(tmp, name, ws, **over):
    a = {"workspace": ws, "account_slot_chars": 1500, "projects": ["alpha"],
         "working_style": {"Suggestions": "drop"},
         "backup": {"weekly_dest": os.path.join(tmp, name + "-bk")},
         "scheduler": {"kind": "none"}}
    a.update(over)
    p = os.path.join(tmp, name + ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(a, f)
    return p


def rmtree(p):
    """Remove a tree, clearing the read-only bit git sets on objects."""
    import stat

    def fix(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if sys.version_info >= (3, 12):
        shutil.rmtree(p, onexc=fix)
    else:
        shutil.rmtree(p, onerror=fix)


def read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp")
    tmp = tempfile.mkdtemp(prefix="fieldbook-install-test-",
                           dir=ap.parse_args().tmp)
    inst = os.path.join(KIT, "install.py")
    n = len(install.PHASES)
    zone = install.machine_zone()

    # prerequisites
    rc, out = py(inst, "--check")
    try:
        pre = json.loads(out)
    except ValueError:
        pre = {}
    check("check: machine-readable, python and git reported",
          rc in (0, 2) and "python" in pre and "git" in pre and
          (rc == 0) == pre.get("ok"), out)

    # dry run writes nothing
    ws = os.path.join(tmp, "dry")
    rc, out = py(inst, "--answers", answers(tmp, "dry", ws), "--dry-run")
    check("dry-run: exits 0, plans every phase, writes nothing",
          rc == 0 and all("phase %d/%d %s" % (i, n, p) in out
                          for i, p in enumerate(install.PHASES, 1))
          and not os.path.exists(ws), out)

    # bad answers
    rc, out = py(inst, "--answers", answers(tmp, "bad", "relative/path"))
    check("answers: invalid set is refused as broken (exit 2)",
          rc == 2 and "BROKEN" in out, out)

    # full install
    ws = os.path.join(tmp, "full")
    ans_full = answers(tmp, "full", ws)
    rc, out = py(inst, "--answers", ans_full)
    check("install: exits 0 and completes", rc == 0 and "DONE" in out, out)
    log = commits(ws)
    check("install: one commit per phase", len(log) == n and all(
        any(m.endswith("phase %d/%d %s" % (i, n, p)) for m in log)
        for i, p in enumerate(install.PHASES, 1)), log)
    ver = read(os.path.join(KIT, "VERSION"))
    check("install: VERSION stamped and documented",
          read(os.path.join(ws, "VERSION")) == ver and "#" in ver)
    try:
        man = json.loads(read(os.path.join(ws, *install.MANIFEST.split("/"))))
    except ValueError:
        man = {}
    files = man.get("files", [])
    check("install: manifest lists the placed tree, not work-item specs",
          "AGENTS.md" in files and "Maintenance/doctor.py" in files and
          all(os.path.exists(os.path.join(ws, f)) for f in files) and
          not any(f.startswith("Work Items/WI-") for f in files), files[:5])
    saved = json.loads(read(os.path.join(ws, "Setup", "answers.json")))
    check("install: answers saved and documented in-file",
          saved.get("projects") == ["alpha"] and
          set(install.ANSWERS_ABOUT) <= set(saved.get("_about", {})))
    check("install: project tenant replaces the example",
          os.path.exists(os.path.join(ws, "Memory", "alpha",
                                      "working-memory.md")) and
          not os.path.exists(os.path.join(ws, "Memory", "example-project"))
          and "alpha" in json.loads(read(os.path.join(
              ws, "Memory", "tenants.json")))["tenants"])
    rules = read(os.path.join(ws, "Projects", "alpha", "PROJECT.md"))
    check("install: project folder, tab, inbox and rules template placed",
          rules.startswith("# alpha") and "{PROJECT}" not in rules and
          os.path.exists(os.path.join(ws, "Projects", "alpha",
                                      "dashboard.json")) and
          os.path.isdir(os.path.join(ws, "Agent Bridge", "to-alpha")) and
          os.path.exists(os.path.join(ws, *install.PROJECT_TEMPLATE.split(
              "/"))) and "Projects/alpha/PROJECT.md" not in files and
          "Projects/README.md" in files)
    cfg = json.loads(read(os.path.join(ws, "workspace.json")))
    check("install: backup destination configured",
          cfg["backup"]["weekly_dest"] == os.path.join(tmp, "full-bk"))
    slot = os.path.join(ws, "Setup", "account-slot.txt")
    agents = read(os.path.join(ws, "AGENTS.md"))
    check("install: 1500 slot takes principles, AGENTS.md the style",
          os.path.exists(slot) and len(read(slot).strip()) <= 1500 and
          "Times are %s." % zone in read(slot) and "{" not in read(slot) and
          install.MARK_BEGIN in agents and "- Decisions:" in agents and
          "Suggestions" not in agents and "Ask:" not in agents)
    check("install: close-commit helper and workspace .gitignore installed",
          os.path.exists(os.path.join(ws, "Maintenance", "close_commit.py"))
          and os.path.exists(os.path.join(ws, ".gitignore")))
    st = subprocess.run(["git", "-C", ws, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    check("install: working tree clean after install", st == "", st)
    # In use: an open bridge message and a launcher-marked work item.
    planted = [os.path.join(ws, "Agent Bridge", "to-global",
                            "FROM-alpha_2026-01-01_ask.md"),
               os.path.join(ws, "Work Items", "WI-02_planted.md")]
    with open(planted[0], "w", encoding="utf-8") as f:
        f.write("---\nfrom: alpha\nkind: question\nstatus: open\n---\nask\n")
    with open(planted[1], "w", encoding="utf-8") as f:
        f.write("project: global\nname: planted\n\n# WI-02 - planted\n\n"
                "| Field | Value |\n|---|---|\n| Run | launcher |\n"
                "| Priority | P1 |\n")
    rc, out = py(os.path.join(ws, "Maintenance", "smoke_test.py"))
    check("install: workspace in use (open message, launcher item) passes "
          "smoke_test.py", rc == 0 and "ALL CHECKS PASSED" in out,
          "\n".join(l for l in out.splitlines()
                    if l.startswith("FAIL"))[-600:] or out[-400:])
    for p in planted:
        os.remove(p)

    # rerun changes nothing
    rc, out = py(inst, "--answers", ans_full)
    st = subprocess.run(["git", "-C", ws, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    check("rerun: says nothing to do, no commit, no change",
          rc == 0 and "NOTHING TO DO" in out and len(commits(ws)) == n
          and st == "", out + st)
    rc, out = py(inst, "--answers", answers(tmp, "full2", ws,
                                            board_theme="dark"))
    check("rerun: differing answers held, saved ones kept",
          rc == 3 and "HELD" in out and '"dark"' not in read(
              os.path.join(ws, "Setup", "answers.json")), out)

    # close-commit helper
    cc = os.path.join(ws, "Maintenance", "close_commit.py")
    with open(os.path.join(ws, "Memory", "alpha", "working-memory.md"), "a",
              encoding="utf-8") as f:
        f.write("a session wrote this\n")
    rc, out = py(cc, "-m", "session close test")
    check("close-commit: commits a dirtied workspace",
          rc == 0 and "COMMITTED" in out and len(commits(ws)) == n + 1, out)
    rc, out = py(cc, "-m", "second close")
    check("close-commit: second unchanged run exits clean",
          rc == 0 and "NOTHING TO COMMIT" in out and
          len(commits(ws)) == n + 1, out)

    # planted collision
    ws = os.path.join(tmp, "collide")
    os.makedirs(ws)
    mine = "# my own rules\n"
    with open(os.path.join(ws, "AGENTS.md"), "w", encoding="utf-8") as f:
        f.write(mine)
    rc, out = py(inst, "--answers", answers(tmp, "collide", ws))
    side = os.path.join(ws, "AGENTS.md" + install.SIDECAR)
    rep = read(os.path.join(ws, "Setup", "install-report.md"))
    check("collision: existing file kept, kit version as sidecar, held",
          rc == 3 and read(os.path.join(ws, "AGENTS.md")) == mine and
          os.path.exists(side) and install.MARK_BEGIN in read(side) and
          "AGENTS.md" + install.SIDECAR in rep, out)

    # resume after a stop
    ws = os.path.join(tmp, "resume")
    rc, out = py(inst, "--answers", answers(tmp, "resume", ws),
                 "--stop-after", "systems")
    check("resume: stop after phase 2 leaves two commits",
          rc == 0 and "STOPPED" in out and len(commits(ws)) == 2, out)
    rc, out = py(inst, "--workspace", ws)
    log = commits(ws)
    check("resume: rerun finishes without redoing phases 1-2",
          rc == 0 and "skip phase 1 workspace" in out and
          "skip phase 2 systems" in out and len(log) == n and
          len(set(log)) == n, out)

    # A kit cloned with Windows line endings, into an empty folder: the
    # installer replaces its own phase-2 files, never sidecars them. The
    # same install proves the zone comes from the machine.
    kit3 = os.path.join(tmp, "kit-crlf")
    shutil.copytree(KIT, kit3, ignore=shutil.ignore_patterns(
        "__pycache__", ".git"))
    for d, _, fs in os.walk(kit3):
        for fn in fs:
            p = os.path.join(d, fn)
            with open(p, "rb") as f:
                data = f.read()
            if b"\0" not in data:
                with open(p, "wb") as f:
                    f.write(data.replace(b"\r\n", b"\n")
                            .replace(b"\n", b"\r\n"))
    ws = os.path.join(tmp, "crlf")
    rc, out = py(os.path.join(kit3, "install.py"), "--answers", answers(
        tmp, "crlf", ws, timezone="Asia/Tokyo"))
    sides = [os.path.join(d, f) for d, _, fs in os.walk(ws) for f in fs
             if f.endswith(install.SIDECAR)]
    check("crlf kit, empty folder: exits 0, no sidecar anywhere, the "
          "configured files in place", rc == 0 and not sides and "alpha" in
          read(os.path.join(ws, "Memory", "tenants.json")) and
          install.MARK_BEGIN in read(os.path.join(ws, "AGENTS.md")),
          out + str(sides))
    slot = read(os.path.join(ws, "Setup", "account-slot.txt"))
    check("zone: placed rules carry the machine's zone; an answers file "
          "naming another is ignored, said once",
          "Times are %s." % zone in slot and "Tokyo" not in slot and
          out.count("IGNORED answer timezone") == 1 and "timezone" not in
          read(os.path.join(ws, "Setup", "answers.json")), out)
    ws = os.path.join(tmp, "typed")
    rc, out = py(inst, "--answers", answers(
        tmp, "typed", ws, projects=["Raised Bed Garden"]))
    tab = os.path.join(ws, "Projects", "Raised-Bed-Garden", "dashboard.json")
    check("project typed with spaces: folder uses the short name, the tab "
          "the typed name", rc == 0 and os.path.exists(tab) and json.loads(
              read(tab)).get("title") == "Raised Bed Garden" and os.path.isdir(
              os.path.join(ws, "Agent Bridge", "to-Raised-Bed-Garden")),
          out)
    rc, out = py(inst, "--answers", answers(
        tmp, "dup", os.path.join(tmp, "dup"),
        projects=["My Garden", "my-garden", "global"]))
    check("project names: shared short name and 'global' refused, named",
          rc == 2 and "'My Garden' and 'my-garden'" in out and
          "'global'" in out and not os.path.exists(os.path.join(tmp, "dup")),
          out)

    # zone unreadable: --check says UNKNOWN, install stops naming it
    real_zone = install.machine_zone
    install.machine_zone = lambda: None
    buf = io.StringIO()
    try:
        pre = install.check_prereqs()
        with contextlib.redirect_stdout(buf):
            rc = install.main(["--answers", answers(
                tmp, "nozone", os.path.join(tmp, "nozone"))])
    finally:
        install.machine_zone = real_zone
    check("zone unreadable: --check UNKNOWN, install exit 2 naming it",
          pre["timezone"]["zone"] == "UNKNOWN" and not pre["ok"] and
          rc == 2 and "timezone" in buf.getvalue() and
          not os.path.exists(os.path.join(tmp, "nozone")), buf.getvalue())

    # placement by slot size
    base = {"workspace": "C:/ws"}
    s, b, _ = install.placed_texts(dict(base, account_slot_chars=0), "UTC")
    check("placement: no slot puts everything in AGENTS.md",
          s is None and "Where rules live" in b and "- Decisions:" in b)
    s, b, _ = install.placed_texts(dict(base, account_slot_chars=8000),
                                   "UTC")
    check("placement: large slot takes both, AGENTS.md gets nothing",
          b is None and "Where rules live" in s and "- Decisions:" in s)
    s, b, _ = install.placed_texts(dict(base, account_slot_chars=500), "UTC")
    check("placement: slot smaller than principles falls back",
          s is None and "Where rules live" in b)
    s, b, _ = install.placed_texts(dict(
        base, account_slot_chars=8000,
        working_style={"Answers": "short and blunt"}), "UTC")
    check("placement: a changed item replaces the default",
          "- Answers: short and blunt" in s and "finished answer" not in s)

    # scheduler wiring against a kit copy with a planted task
    kit2 = os.path.join(tmp, "kit2")
    shutil.copytree(KIT, kit2, ignore=shutil.ignore_patterns(
        "__pycache__", ".git"))
    tdir = os.path.join(kit2, "workspace", "Scheduled", "demo-task")
    os.makedirs(tdir)
    with open(os.path.join(tdir, "INSTRUCTIONS.md"), "w") as f:
        f.write("Confirm file access, then run the demo agenda.\n")
    with open(os.path.join(tdir, "schedule.json"), "w") as f:
        json.dump({"schedule": "WEEKLY", "day": "SUN", "time": "07:00"}, f)
    inst2 = os.path.join(kit2, "install.py")
    ws = os.path.join(tmp, "hand")
    rc, out = py(inst2, "--answers", answers(tmp, "hand", ws))
    hand = os.path.join(ws, "Setup", "hand-run-tasks.md")
    check("scheduler none: hand-run prompt printed and written",
          rc == 0 and "HAND-RUN" in out and os.path.exists(hand) and
          "demo-task" in read(hand) and "WEEKLY 07:00 SUN" in read(hand), out)
    ws = os.path.join(tmp, "win")
    rc, out = py(inst2, "--answers", answers(
        tmp, "win", ws, scheduler={
            "kind": "windows", "launch_command": 'ai-cli run "{instructions}"',
            "times": {"demo-task": "05:30"}}), "--no-register")
    launch = os.path.join(ws, "Scheduled", "demo-task", "launch.cmd")
    check("scheduler windows: launch file written, entry planned only",
          rc == 0 and os.path.exists(launch) and "INSTRUCTIONS.md" in
          read(launch) and 'INSTRUCTIONS.md" < NUL' in read(launch) and
          "schtasks /Create" in out and "/ST 05:30" in out
          and "/D SUN" in out, out)

    rmtree(tmp)
    print()
    if FAIL:
        print("FAILED: %d check(s): %s" % (len(FAIL), ", ".join(FAIL)))
        return 3
    print("ALL INSTALLER CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
