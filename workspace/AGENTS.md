# Workspace rules: read at the start of every session

You are an AI assistant operating in this workspace. The account-level rules
(principles and working style) bind first. They live in your tool's
account instructions; where the tool had no room for them, the installer
placed them in a marked block at the end of this file, and that block is
their home. This file adds only what binds a session that can read the
workspace. Each system's README carries its full design.

## Session start

Read, in order:
1. This file.
2. `Memory/global/core-profile.md` and `Memory/global/working-memory.md`.
3. If the session belongs to a project: its rules, `Projects/<project>/PROJECT.md`,
   then its working memory, `Memory/<project>/working-memory.md`.
4. `Work Items/00_index.md`, the open-work view.
5. `attention.json`: raise anything marked urgent with the user now.

Day logs are archive: never read them at session start; reach them through
search (`Memory/engine/search.py`) when history is needed.

## Session close

When the user ends the session, write the close artifacts in this order:
1. One day-log entry per project the session touched:
   `Memory/<project>/logs/YYYY-MM-DD.md` (or `Memory/global/logs/` for work
   belonging to no project). Fold your own corrections in before writing
   rather than appending contradictions after.
2. Working-memory updates, per the admission test below.
3. Commit the workspace, so every session is a point you can roll back to:
   `python Maintenance/close_commit.py -m "what changed and why"`. It exits
   clean when there is nothing to commit; call it anyway.

A session survives only as its files: whatever was not written down before
the end is gone.

## Working memory: the admission test

A working-memory file holds the standing present: only what is true NOW and
has no other home. Before adding a line, ask in order:

1. Does this outcome change what is true now? Usually not: then it goes
   in the day log and nowhere else.
2. If so, does a file already own that truth? Finished work is owned by its
   spec, rules by rules files, project facts by the project's own documents.
   Update the owner, not memory.
3. Only what survives both questions enters working memory.

Writes are surgical: add lines, or replace a line your own work superseded.
Replacing or removing a line an earlier session wrote goes through
`Memory/engine/evict.py`, which records it in today's day log first. Never
rewrite a memory file wholesale. Caps live in `Memory/tenants.json`;
sustained cap pressure means lines are homed wrong, not that the cap is too
small.

## Work

Work that will not finish in the current session becomes a work item:
follow `Skills/work-item-SKILL.md`. The system is described in
`Work Items/README.md`. Never edit a generated file (the completed archive,
the trigger index, the dashboard page); edit the source and rerun its
builder.

Anything that would cost the user money — a subscription, a hosted
service, a paid tier — is priced and flagged before it becomes part of any
plan; signing up and paying are always the user's.

When the user asks for a named job ("file a bug", "give me the tour"),
look it up in `Skills/00_triggers.md` and follow the procedure it points to.

Anything that needs the user's decision or hand, found by a session or an
unattended run, is filed to the waiting-on-you queue
(`Maintenance/attention.py --file`); the dashboard shows it.

## Retiring files

Nothing is hard-deleted. A file that has served its purpose moves to
`Quarantine/` (mirroring its original relative path) with one line appended
to `Quarantine/manifest.md` in the same session. Throwaway scratch goes in
`Temp/managed/` with a manifest line carrying its expiry. The weekly
cleanup deletes only what is past expiry, unreferenced, and already backed up.

## Messages between projects

Projects do not write into each other's folders. Anything one project needs
to tell another goes through `Agent Bridge/`; its README owns the format.

## Files and secrets on this disk

File timestamps can be in UTC while the clock is local: convert before
writing a file's timestamp as a date. Some AI tools write through a sandbox
rather than the real disk; after any write, confirm the file exists where
you said it does. Secrets live only in `.env` files: git ignores them, the
search index skips them, and no other file ever carries their values.
Backups do copy them, which is one more reason the backup destination
should be encrypted.
