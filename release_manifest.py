"""release_manifest.py - the kit's per-version file hash manifest.

Writes manifests/<version>.json (version = line 1 of VERSION): the sha256
of every workspace/ file install.py copies, keyed by workspace-relative
path with "/" separators. upgrade.py reads the manifest of the version an
installation reports to tell files the adopter never touched from files
they changed. Every manifest ever released stays in manifests/, so a newer
kit can upgrade from any older version.

Release path: change kit files, bump VERSION, add the version's entry to
CHANGELOG.md (a "## <version> (<date>)" heading and at least one line
under it), run this, commit all three. Until a
version is published its manifest may be regenerated; once published it is
never rewritten (bump VERSION instead). The kit's smoke test runs --check,
so a changed file with a stale manifest, or a version with no changelog
entry, fails the kit's own test.

Usage:  python release_manifest.py [--check]
Exit codes (tools/EXIT-CODES.md): 0 written, or current; 1 crashed;
2 broken (VERSION unreadable); 3 --check found it missing or stale, or
CHANGELOG.md has no entry for the version (either mode).
"""

import argparse
import json
import os
import re
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import install  # noqa: E402

MANIFESTS = os.path.join(KIT, "manifests")
CHANGELOG = os.path.join(KIT, "CHANGELOG.md")


def changelog_has(version):
    """True when CHANGELOG.md has a "## <version>" heading with at least
    one non-blank line before the next heading."""
    try:
        text = open(CHANGELOG, encoding="utf-8").read()
    except OSError:
        return False
    m = re.search(r"^## %s\b.*\n((?:(?!^## ).*\n?)*)" % re.escape(version),
                  text, re.M)
    return bool(m and m.group(1).strip())


def kit_version(kit=KIT):
    with open(os.path.join(kit, "VERSION"), encoding="utf-8") as f:
        v = f.readline().strip()
    if not re.match(r"^\d+\.\d+\.\d+$", v):
        raise ValueError("VERSION line 1 is not major.minor.patch: %r" % v)
    return v


def manifest_text(version):
    files = {}
    for rel in install.kit_files():
        with open(os.path.join(install.KIT_WS, rel), "rb") as f:
            files[rel.replace("\\", "/")] = install.sha(f.read())
    return json.dumps({"_about": "sha256 of each workspace file kit version "
                       "%s ships, keyed by workspace-relative path. Written "
                       "by release_manifest.py; read by upgrade.py." % version,
                       "version": version, "files": files}, indent=2) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    try:
        v = kit_version()
    except (OSError, ValueError) as e:
        print("BROKEN: %s" % e)
        return 2
    if not changelog_has(v):
        print("MISSING: CHANGELOG.md has no entry for %s; add a \"## %s (date)\" heading with a line or two on what changed" % (v, v))
        return 3
    p = os.path.join(MANIFESTS, v + ".json")
    want = manifest_text(v)
    cur = open(p, encoding="utf-8").read() if os.path.exists(p) else None
    if cur == want:
        print("CURRENT: manifests/%s.json matches the kit" % v)
        return 0
    if a.check:
        print("STALE: manifests/%s.json %s; run release_manifest.py (bump "
              "VERSION first if %s is published)"
              % (v, "is missing" if cur is None else "differs from the kit",
                 v))
        return 3
    os.makedirs(MANIFESTS, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(want)
    print("WRITTEN: manifests/%s.json" % v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
