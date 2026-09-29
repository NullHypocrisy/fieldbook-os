---
name: migrate
description: Audit the setup the user had before this workspace and, part by part and only on their yes, bring it into the workspace's formats.
triggers:
  - "adopt my existing setup"
  - "migrate my notes"
  - "import my old memory"
  - "bring my old task list in"
---

# Migrate Procedure

For a user who already kept notes, memory or task lists before this
workspace existed. The job has two halves: an audit that changes nothing,
then a migration the user approves one part at a time. Source formats vary
too much to script, so you do the reading and transforming; git is the
safety net.

Three rules hold throughout:

- **The source is read-only.** Never edit, move or delete anything in the
  user's old setup. The migration writes only inside this workspace; the
  user retires the old files themselves, when they choose.
- **Nothing is migrated without a yes for that part.** A yes for one part
  covers only that part.
- **Every part is bracketed by commits**, so any transform rolls back whole.

## 1. Before starting

From the workspace root, `python Maintenance/doctor.py --no-smoke` shows
no FAIL, and `git status --short` is empty (commit or settle anything
pending first). Migration on a broken or dirty tree makes rollback unsafe.

## 2. Audit (read-only)

Ask the user where the old setup lives: folders, files, a notes app
export, a tool's saved memory or custom instructions pasted in. Read all
of it. Then write the audit to `Temp/managed/migration-audit.md`, with a
manifest line giving it a 30-day expiry, and show it to the user:

- **What exists:** each source, its path, format, size, and date range.
- **Where it maps:** each part's destination here, from the table in
  section 3, or "does not map" with why.
- **What the workspace adds** that the old setup lacks (search with
  citations, capped working memory, work-item specs, backups, and so on).
- **What would be lost or reshaped:** anything that does not survive the
  transform as it stands, said plainly.

The audit writes nothing but that file. Stop here if the user only wanted
the audit.

## 3. Where things go

Each destination system's README owns its format; read it before
transforming into it.

| Old material | Destination |
|---|---|
| Who the user is, how they like to work | `Memory/global/core-profile.md`, within its cap |
| Standing facts still true now | the owning tenant's working memory, through the admission test in `AGENTS.md`, within its cap |
| Dated notes, journals, history | day logs, `Memory/<tenant>/logs/YYYY-MM-DD.md`, each under its original date |
| A project with its own notes | a new tenant in `Memory/tenants.json` (see `Memory/README.md`), then as above |
| To-dos, plans, unfinished work | work items, via `Skills/work-item-SKILL.md` CREATE, one spec per real piece of work |
| Finished work worth keeping | a work item written already complete, filed in `Work Items/completed/` |
| Standing instructions to an assistant | shown to the user beside `AGENTS.md`; rules are theirs to place, never merged silently |

Most old notes belong in day logs, not working memory: the admission test
decides, and it admits little. A note with no date goes under today's date,
headed as imported, naming its source file.

## 4. Migrate, one part at a time

Offer the parts from the audit one by one. For each part the user says yes
to:

1. **Commit before:** `git add -A` then
   `git commit -m "before migrating <part>"`.
2. **Preview:** list every file to be created or changed, and show the
   transformed content (all of it when short, a representative sample when
   long, with counts). Ask for a yes on the preview. Change nothing until
   it comes; on a no, adjust and preview again, or skip the part.
3. **Transform:** write exactly what the preview showed.
4. **Verify:** `python Memory/engine/indexer.py`, then a search for two or
   three facts from the part to prove they are found with citations; for
   work items, `python "Work Items/tools/build_completed_index.py"` when
   any went to `completed/`. Then `python Maintenance/doctor.py --no-smoke`
   shows no new FAIL.
5. **Commit after:** `git add -A` then
   `git commit -m "migrated <part> from <source>"`.

If the user dislikes a result, roll that part back with
`git revert --no-edit <after-commit>`; the before-commit is the state to
return to, and earlier parts stay as they were.

## 5. Close

Tell the user, per part: what moved where, what was left behind and why,
and that the old setup is untouched. Record the migration in today's
global day log: sources, parts migrated, parts declined, and the commit
pairs.
