"""workspace_common.py - helpers every workspace script shares.

Lives at the workspace root, beside workspace.json. Each script puts this
folder on sys.path from its own location and imports from here, so the
scripts work from any current directory. Keep the scripts where the kit
places them; the import depends on that layout.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime

# Where the installer puts the rule tiers inside AGENTS.md (no-slot fallback).
MARK_BEGIN = "<!-- fieldbook:placed-rules begin -->"
MARK_END = "<!-- fieldbook:placed-rules end -->"

# Install manifest: every machinery file the installer placed, workspace-
# relative with "/" separators, as {"_about": ..., "files": [...]}. The
# doctor checks the tree against it. Work-item specs are the adopter's to
# move and delete, and Setup/ is the installer's own, so neither is listed.
MANIFEST = "Setup/manifest.json"

# Set in the environment of the smoke test the doctor starts, so that run
# skips its own doctor checks instead of recursing.
SMOKE_NESTED = "FIELDBOOK_SMOKE_NESTED"


def manifest_tracked(rel):
    """False for what the adopter owns after install: Setup/, work-item
    specs, and each project's folder under Projects/."""
    rel = rel.replace("\\", "/")
    name = rel.rsplit("/", 1)[-1]
    return not (rel.startswith("Setup/") or (
        rel.startswith("Work Items/") and rel.count("/") == 1
        and name.startswith("WI-")) or (
        rel.startswith("Projects/") and rel.count("/") >= 2))


# Projects: one short name (project_slug of the name as typed) shared by a
# memory tenant, a Projects/<name>/ folder and an Agent Bridge/to-<name>/
# inbox; the typed name is the dashboard tab's title. Projects/README.md
# owns the folder shape and the dashboard.json format. The rules template
# is the kit's tiers/project.md, which install.py copies to
# PROJECT_TEMPLATE.
PROJECT_NAME = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
PROJECT_TEMPLATE = "Setup/project-template.md"


def project_slug(name):
    """The folder-safe short name for a project typed as free text: each
    run of characters PROJECT_NAME rejects becomes '-', ends trimmed, so a
    name already valid is its own slug. "" when nothing usable is left."""
    name = str(name).strip()
    if re.match(PROJECT_NAME, name):
        return name
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-_")


def project_slugs(names):
    """[(typed name, slug)] for names, or raise ValueError naming every
    name that cannot be a project: empty slug, 'global', or a slug two
    names share."""
    pairs = [(str(n), project_slug(n)) for n in names]
    bad = ["%r (nothing usable in it)" % n for n, s in pairs if not s]
    bad += ["%r (the name 'global' is the workspace's own)" % n
            for n, s in pairs if s.lower() == "global"]
    seen = {}
    for n, s in pairs:
        seen.setdefault(s.lower(), []).append(n)
    bad += ["%s (all become %r)" % (" and ".join(repr(n) for n in ns),
                                    project_slug(ns[0]))
            for k, ns in seen.items() if k and len(ns) > 1]
    if bad:
        raise ValueError("project names that cannot be used: "
                         + "; ".join(bad))
    return pairs


STARTER_PANELS = ("work", "memory", "inbox", "attention")

# Board looks, chosen at install (workspace.json "board" -> "theme"); the
# first is the default. Maintenance/dashboard_build.py owns what each is.
BOARD_THEMES = ("auto", "dark", "light", "colorful-auto",
                "colorful-dark", "colorful-light")


def project_tenant(name):
    """The tenants.json entry for a project's memory tenant."""
    return {"working_memory": "Memory/%s/working-memory.md" % name,
            "cap_chars": 4000,
            "scopes": [{"root": "Memory/" + name,
                        "include": ["working-memory.md", "logs/*.md"]}]}


def project_files(name, template, title=None):
    """{workspace-relative path: text} a new project needs besides its
    tenants.json entry. name: the slug; template: the rules template text;
    title: the name as typed, shown on its dashboard tab (default name)."""
    board = {"title": title or name,
             "panels": [{"type": t} for t in STARTER_PANELS]}
    return {
        "Memory/%s/working-memory.md" % name:
            "# %s working memory (cap in tenants.json)\nThe standing present "
            "for this project only. Same admission test as global.\n\n"
            "## Standing present\n\n(Empty - new project.)\n" % name,
        "Projects/%s/PROJECT.md" % name: template.replace("{PROJECT}", name),
        "Projects/%s/dashboard.json" % name:
            json.dumps(board, indent=2) + "\n",
        "Agent Bridge/to-%s/closed/.gitkeep" % name: "",
    }


def manifest_text(rels):
    """The manifest file's content for the given workspace-relative paths."""
    files = sorted(set(r.replace("\\", "/") for r in rels
                       if manifest_tracked(r)))
    return json.dumps({"_about": "Machinery files the installer placed; "
                       "Maintenance/doctor.py checks each still exists. "
                       "Written by install.py.", "files": files},
                      indent=2) + "\n"


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


def machine_zone():
    """The machine's time zone name as its OS shows it, or None when it
    cannot be read. Read only: nothing here ever changes it."""
    import platform
    if platform.system() == "Windows":
        try:
            r = subprocess.run(["tzutil", "/g"], capture_output=True,
                               text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        zone = r.stdout.strip()
        return zone if r.returncode == 0 and zone else None
    m = re.search(r"zoneinfo/(.+)$", os.path.realpath("/etc/localtime"))
    return m.group(1) if m else None


# Install journal: Maintenance/README.md owns the name, place and line
# format. FIELDBOOK_HOME stands in for the home folder (self-tests only).
JOURNAL = "Setup/install-journal.txt"
HOME_JOURNAL = "fieldbook-install-journal.txt"
JOURNAL_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} \| [^|]+ \| ")


def home_journal():
    home = os.environ.get("FIELDBOOK_HOME") or os.path.expanduser("~")
    return os.path.join(home, HOME_JOURNAL)


def journal_path(ws):
    """The workspace's journal once the workspace folder exists, else the
    home-folder one."""
    if ws and os.path.isdir(ws):
        return os.path.join(ws, *JOURNAL.split("/"))
    return home_journal()


def journal(ws, who, step, command, result):
    """Append one journal line; never raises (a journal is evidence, not a
    reason to fail a run)."""
    def flat(s):
        return " ".join(str(s).split()) or "-"
    line = "%s | %s | %s | %s | %s\n" % (
        datetime.now().strftime("%Y-%m-%d %H:%M"), flat(who), flat(step),
        flat(command), flat(result).replace(" | ", " / "))
    try:
        p = journal_path(ws)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def adopt_home_journal(ws):
    """Move the home-folder journal into the workspace's, appending; the
    home copy is deleted only after the append is written. Returns the
    number of lines moved."""
    src = home_journal()
    if not (ws and os.path.isdir(ws) and os.path.isfile(src)):
        return 0
    with open(src, "rb") as f:
        data = f.read()
    if data and not data.endswith(b"\n"):
        data += b"\n"
    dest = os.path.join(ws, *JOURNAL.split("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "ab") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.remove(src)
    return data.count(b"\n")


def log_line(log_path, msg):
    """Append a timestamped line to log_path and echo it."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("%s | %s\n" % (stamp, msg))
    print(msg)


def git(root, *args):
    """Run git in root; return (returncode, combined output)."""
    r = subprocess.run(["git", "-C", root] + list(args),
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def git_identity(root):
    """Extra args so a commit works where no git identity is configured.

    The user's own identity always wins; the fallback only fills a gap.
    """
    rc, out = git(root, "config", "user.email")
    if rc == 0 and out:
        return []
    return ["-c", "user.name=Fieldbook OS", "-c",
            "user.email=fieldbook@localhost"]
