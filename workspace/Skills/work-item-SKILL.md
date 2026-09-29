---
name: work-item
description: Create a work item for work that will not finish this session, or complete one; the system itself is described in Work Items/README.md.
triggers:
  - "add a work item"
  - "new work item"
  - "spec this up"
  - "complete WI-NN"
  - "close out this work item"
---

# Work Item Skill

## Branch: CREATE

1. **Situate.** Read `Work Items/00_index.md` end to end and open every
   spec whose scope touches the new work. If an existing item already owns
   this ground, extend that spec and its index line instead, and stop.
   Done when: you know the next free WI number and can justify, in a
   sentence, that this ground is nobody else's.

2. **Ask the hard questions first.** Pull the answers out of the files and
   the current session now — a future session cannot: the problem and its
   evidence; dependencies both directions; the deadline (a specific date,
   the event that sets it, or explicitly none); and acceptance
   criteria that are checkable and exhaustive, so meeting them IS
   completion. Anything genuinely unknowable gets an honest UNKNOWN plus
   the question that resolves it.

3. **Write the spec** from `Work Items/templates/WI-template.md`, named for
   what the work does. The bar is execute-cold: reread it as a stranger and
   answer every "which file?", "why?", "per whose decision?" it raises,
   inside the document. State what only this spec knows; point at the files
   that own the rest, and never restate them.

4. **Index it.** Append one line to `Work Items/00_index.md` — ID, link,
   status, one sentence. Single-line edits only.

5. **Surface the decisions.** Any decision the work needs that only the
   user can make goes in the spec's Open decisions section, with options,
   trade-offs, and a recommendation — never decided silently on their
   behalf. Tell the user the item exists and what it waits on, if anything.

## Branch: COMPLETE

1. **Verify against the spec's own acceptance list**, criterion by
   criterion, each backed by something concrete — a test run, a query
   result, the path of the artifact produced. Where a criterion depends on
   the user acting, do not leave the item open waiting: write down what
   they must do next to the criterion and close anyway. Reopening is never
   the remedy for a later-discovered flaw; whichever session discovers it
   fixes it.

2. **Append a completion record**: what shipped, evidence per criterion,
   deviations from spec, and the date read from a live clock at the moment
   of writing. Add `outcome:` beside `project:` at the top — one sentence,
   under 200 characters, written now because no later session will know it
   first-hand.

3. **Move and regenerate.** Move the spec to `Work Items/completed/`,
   delete its line from `00_index.md` (single-line edit), then run
   `python "Work Items/tools/build_completed_index.py"` and confirm exit 0.

4. **Hand the outcome to the session close.** The spec and archive hold the
   item's truth; the close adds only the day-log entry and any
   working-memory line that survives the admission test in AGENTS.md —
   which a completed item rarely does.
