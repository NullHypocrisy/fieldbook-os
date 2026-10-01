# Stability promise

From 1.0.0, every 1.x release keeps these four things working the way they
work in 1.0.0, so you can build on them:

1. **The workspace layout.** The folders the installer creates and what each
   one is for (`Memory/`, `Work Items/`, `Projects/`, `Agent Bridge/`,
   `Scheduled/`, `Maintenance/`, `Skills/`, `Quarantine/`, `Temp/`, `Setup/`)
   and the files your sessions read at start (`AGENTS.md`, each project's
   `PROJECT.md`, the working-memory files).
2. **The upgrade path.** `python upgrade.py --workspace YOUR-FOLDER`, run
   from a newer kit, brings any 1.x workspace up to that kit. It never
   overwrites a file you changed; the kit's version lands beside yours to
   merge.
3. **The answers file.** `Setup/answers.json` keeps its format. A new
   question may be added; upgrade.py then asks it. An existing one keeps its
   meaning.
4. **The rule keys.** The labels the rule files are built from (`Truth:`,
   `Decisions:`, `## Rules for this project` and the rest, listed in
   `tiers/keys.json`) keep working. If one is renamed, the old name is
   recorded in that file and `doctor.py` warns you, naming the new one,
   until you change it.

Anything else can improve in a 1.x release: scripts, the dashboard,
procedures, wording.

**A breaking change** to any of the four means a new major version (2.0.0)
and a CHANGELOG entry that says what changed and exactly what to do about
it. Nothing in the four changes silently.

Before 1.0.0 (versions 0.x) none of this is promised yet, though upgrade.py
already works the same way.
