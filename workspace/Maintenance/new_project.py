"""new_project.py - add a project after install: its memory tenant (in
Memory/tenants.json and Memory/NAME/), its Projects/NAME/ folder (rules
file and a starter dashboard.json) and its Agent Bridge/to-NAME/ inbox.
Projects/README.md owns the folder shape and the tab format.

Never overwrites: a piece that already exists is kept and reported.

NAME is free text ("Raised Bed Garden"): the folders, tenant and inbox use
its short name (workspace_common.project_slug), the tab shows it as typed.

Usage:  python Maintenance/new_project.py NAME [--dry-run]
Exit codes (tools/EXIT-CODES.md): 0 created (or planned, with --dry-run);
1 crashed; 2 broken (bad name, no rules template, tenants.json unreadable
or unwritable); 3 held: some or all of it already existed, kept as is
(planned the same way with --dry-run).
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
from workspace_common import (PROJECT_TEMPLATE, project_files,  # noqa: E402
                              project_slugs, project_tenant, workspace_root)

ROOT = workspace_root(HERE)
TENANTS = os.path.join(ROOT, "Memory", "tenants.json")


def template_text():
    """The rules template: the installed copy, else the kit's own (when this
    runs inside the kit tree, before any install)."""
    for p in (os.path.join(ROOT, *PROJECT_TEMPLATE.split("/")),
              os.path.join(ROOT, "..", "tiers", "project.md")):
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return f.read()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dry = a.dry_run
    try:
        (title, name), = project_slugs([a.name])
    except ValueError as e:
        print("BROKEN %s" % e)
        return 2
    if name != title:
        print("project %r uses the short name %s for its folders; the tab "
              "shows %r" % (title, name, title))
    template = template_text()
    if template is None:
        print("BROKEN no rules template at %s; rerun install.py or copy the "
              "kit's tiers/project.md there" % PROJECT_TEMPLATE)
        return 2
    try:
        with open(TENANTS, encoding="utf-8") as f:
            ten = json.load(f)
        ten.setdefault("tenants", {})
    except (OSError, ValueError) as e:
        print("BROKEN cannot read Memory/tenants.json (%s)" % e)
        return 2
    say = "PLAN  " if dry else ""
    kept = []
    if name in ten["tenants"]:
        kept.append("tenant %s in Memory/tenants.json" % name)
    else:
        print("%sadd tenant %s to Memory/tenants.json" % (say, name))
        ten["tenants"][name] = project_tenant(name)
        if not dry:
            try:
                tmp = TENANTS + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(ten, f, indent=2)
                    f.write("\n")
                os.replace(tmp, TENANTS)
            except OSError as e:
                print("BROKEN cannot write Memory/tenants.json (%s)" % e)
                return 2
    for rel, text in sorted(project_files(name, template, title).items()):
        p = os.path.join(ROOT, *rel.split("/"))
        if os.path.exists(p):
            kept.append(rel)
            continue
        print("%swrite %s" % (say, rel))
        if not dry:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
    for k in kept:
        print("KEPT %s (already existed; not overwritten)" % k)
    if dry:
        print("DRY RUN: nothing was written")
        return 3 if kept else 0
    if kept:
        print("HELD project %s: %d piece(s) already existed and were kept"
              % (name, len(kept)))
        return 3
    print("CREATED project %s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
