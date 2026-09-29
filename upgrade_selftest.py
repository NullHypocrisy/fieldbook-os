"""upgrade_selftest.py - prove upgrade.py end to end in throwaway folders.

Copies the kit twice into a temp folder: version A as it stands, and a
synthesized version B (minor version bumped; one README changed per system
tested, the AGENTS.md template changed, a file added, a file retired, a new
installer question). Installs A, then asserts: preview writes nothing; an
unanswered new question is reported and blocks --apply; an unmodified tree
upgrades with zero sidecars (replace, add, retire, placed rules kept,
VERSION bumped, report, day-log line, commits before and after); a rerun
has nothing to do; a downgrade is refused; a file the adopter modified is
never overwritten and gets a sidecar. The real kit is never written.

Usage:  python upgrade_selftest.py [--tmp DIR]
Exit codes (tools/EXIT-CODES.md): 0 all passed; 1 crashed; 3 a check
failed.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import install  # noqa: E402
from install_selftest import answers, check, commits, rmtree, FAIL  # noqa

MOD = "Maintenance/README.md"       # changed in B; the adopter edits it
MOD2 = "Memory/README.md"           # changed in B; never edited
ADDED = "Maintenance/NOTES-B.md"
RETIRED = "Agent Bridge/templates/message-template.md"


def py(script, *args):
    r = subprocess.run([sys.executable, script] + list(args),
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def fp(root, rel):
    return os.path.join(root, *rel.split("/"))


def read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def append(p, text):
    with open(p, "a", encoding="utf-8") as f:
        f.write(text)


def tree(ws):
    """{rel: sha256} of every file outside .git."""
    out = {}
    for d, dirs, files in os.walk(ws):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in files:
            p = os.path.join(d, f)
            with open(p, "rb") as h:
                out[os.path.relpath(p, ws)] = hashlib.sha256(
                    h.read()).hexdigest()
    return out


def head(ws):
    return subprocess.run(["git", "-C", ws, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def sidecars(ws):
    return [r for r in tree(ws) if r.endswith(install.SIDECAR)]


def make_kits(tmp):
    ign = shutil.ignore_patterns("__pycache__", ".git", "manifests")
    ka, kb = os.path.join(tmp, "kitA"), os.path.join(tmp, "kitB")
    shutil.copytree(KIT, ka, ignore=ign)
    rc, out = py(os.path.join(ka, "release_manifest.py"))
    check("kit A: manifest written", rc == 0, out)
    shutil.copytree(ka, kb, ignore=shutil.ignore_patterns("__pycache__"))
    vp = os.path.join(kb, "VERSION")
    lines = read(vp).splitlines(True)
    a = lines[0].strip()
    ma, mi, _ = (int(x) for x in a.split("."))
    b = "%d.%d.0" % (ma, mi + 1)
    with open(vp, "w", encoding="utf-8") as f:
        f.write(b + "\n" + "".join(lines[1:]))
    kw = os.path.join(kb, "workspace")
    append(fp(kw, MOD), "\nChanged in B.\n")
    append(fp(kw, MOD2), "\nAlso changed in B.\n")
    append(fp(kw, "AGENTS.md"), "\nA rule line new in B.\n")
    with open(fp(kw, ADDED), "w", encoding="utf-8") as f:
        f.write("# Notes new in B\n")
    os.remove(fp(kw, RETIRED))
    ip = os.path.join(kb, "install.py")
    src = read(ip)
    with open(ip, "w", encoding="utf-8") as f:
        f.write(src.replace("ANSWERS_ABOUT = {\n", "ANSWERS_ABOUT = {\n"
                            '    "newq": "A question new in B.",\n', 1))
    rc, out = py(os.path.join(kb, "release_manifest.py"))
    check("kit B: manifest written beside A's", rc == 0 and os.path.exists(
        os.path.join(kb, "manifests", a + ".json")), out)
    return ka, kb, a, b


def answer(ws, key, value):
    p = os.path.join(ws, "Setup", "answers.json")
    ans = json.loads(read(p))
    ans[key] = value
    with open(p, "w", encoding="utf-8") as f:
        json.dump(ans, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp")
    tmp = tempfile.mkdtemp(prefix="fieldbook-upgrade-test-",
                           dir=ap.parse_args().tmp)
    ka, kb, va, vb = make_kits(tmp)
    up_a, up_b = os.path.join(ka, "upgrade.py"), os.path.join(kb, "upgrade.py")
    kbw = os.path.join(kb, "workspace")

    # --- unmodified tree ---------------------------------------------
    ws = os.path.join(tmp, "clean")
    rc, out = py(os.path.join(ka, "install.py"), "--answers",
                 answers(tmp, "clean", ws))
    check("install A: done", rc == 0 and read(os.path.join(ws, "VERSION"))
          .startswith(va), out)
    snap, h0 = tree(ws), head(ws)
    rc, out = py(up_b, "--workspace", ws)
    check("question: new question reported, preview held (exit 3)",
          rc == 3 and "QUESTION newq: A question new in B." in out, out)
    rc, out = py(up_b, "--workspace", ws, "--apply")
    check("question: --apply refuses, nothing written, never defaulted",
          rc == 3 and tree(ws) == snap and head(ws) == h0 and "newq" not in
          read(os.path.join(ws, "Setup", "answers.json")), out)
    answer(ws, "newq", "answered")
    snap = tree(ws)
    rc, out = py(up_b, "--workspace", ws)
    check("preview: exit 0, every planned action printed", rc == 0 and
          "PREVIEW" in out and all(s in out for s in (
              "replace %s" % MOD, "replace %s" % MOD2, "replace AGENTS.md",
              "add %s" % ADDED, "retire %s" % RETIRED, "VERSION %s -> %s"
              % (va, vb))) and "sidecar" not in out, out)
    check("preview: writes nothing", tree(ws) == snap and head(ws) == h0)

    rc, out = py(up_b, "--workspace", ws, "--apply")
    log = commits(ws)
    agents = read(os.path.join(ws, "AGENTS.md")) or ""
    check("apply clean: exit 0, zero sidecars", rc == 0 and "DONE" in out
          and not sidecars(ws), out + str(sidecars(ws)))
    check("apply clean: unmodified files replaced, new file added",
          read(fp(ws, MOD)) == read(fp(kbw, MOD)) and
          read(fp(ws, MOD2)) == read(fp(kbw, MOD2)) and
          read(fp(ws, ADDED)) == read(fp(kbw, ADDED)))
    check("apply clean: AGENTS.md rendered from B with the placed rules",
          "A rule line new in B." in agents and install.MARK_BEGIN in agents
          and "- Decisions:" in agents)
    check("apply clean: retired file quarantined with a manifest line",
          not os.path.exists(fp(ws, RETIRED)) and
          os.path.exists(fp(ws, "Quarantine/" + RETIRED)) and
          RETIRED in read(fp(ws, "Quarantine/manifest.md")))
    ans = json.loads(read(os.path.join(ws, "Setup", "answers.json")))
    check("apply clean: VERSION bumped, answers kept and documented",
          read(os.path.join(ws, "VERSION")) == read(os.path.join(kb,
                                                                 "VERSION"))
          and ans.get("newq") == "answered" and "newq" in ans["_about"]
          and ans["timezone"] == "Europe/Berlin")
    check("apply clean: git commits bracket the run, tree clean",
          log[0] == "Fieldbook OS upgrade %s -> %s" % (va, vb) and
          log[1] == "Fieldbook OS upgrade %s -> %s: before" % (va, vb) and
          subprocess.run(["git", "-C", ws, "status", "--porcelain"],
                         capture_output=True, text=True).stdout == "", log)
    logs = os.path.join(ws, "Memory", "global", "logs")
    day = "".join(read(os.path.join(logs, f)) for f in os.listdir(logs)) \
        if os.path.isdir(logs) else ""
    check("apply clean: report written, one day-log line",
          "## %s -> %s" % (va, vb) in (read(fp(ws, "Setup/upgrade-report."
                                                "md")) or "") and
          day.count("Fieldbook OS upgraded %s -> %s" % (va, vb)) == 1, day)
    rc, out = py(up_b, "--workspace", ws, "--apply")
    check("rerun: nothing to do", rc == 0 and "NOTHING TO DO" in out and
          len(commits(ws)) == len(log), out)
    rc, out = py(up_a, "--workspace", ws)
    check("downgrade: refused as broken (exit 2)", rc == 2 and "BROKEN" in
          out, out)

    # --- a file the adopter modified ---------------------------------
    ws = os.path.join(tmp, "modified")
    rc, out = py(os.path.join(ka, "install.py"), "--answers",
                 answers(tmp, "modified", ws))
    append(fp(ws, MOD), "\nMy own note.\n")
    mine = read(fp(ws, MOD))
    answer(ws, "newq", "answered")
    rc, out = py(up_b, "--workspace", ws)
    check("preview modified: sidecar planned", rc == 0 and "sidecar %s%s"
          % (MOD, install.SIDECAR) in out, out)
    rc, out = py(up_b, "--workspace", ws, "--apply")
    rep = read(fp(ws, "Setup/upgrade-report.md")) or ""
    check("apply modified: never overwritten, sidecar holds B, held",
          rc == 3 and read(fp(ws, MOD)) == mine and
          read(fp(ws, MOD + install.SIDECAR)) == read(fp(kbw, MOD)) and
          MOD + install.SIDECAR in rep and
          sidecars(ws) == [os.path.normpath(MOD + install.SIDECAR)], out)
    check("apply modified: the untouched file still replaced",
          read(fp(ws, MOD2)) == read(fp(kbw, MOD2)))

    rmtree(tmp)
    print()
    if FAIL:
        print("FAILED: %d check(s): %s" % (len(FAIL), ", ".join(FAIL)))
        return 3
    print("ALL UPGRADE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
