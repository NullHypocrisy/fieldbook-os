# The Work Item System

Durable task tracking in two layers:

**The specs.** One markdown document per piece of work —
`WI-NN_short-slug.md` in this folder — carrying everything a future session
needs to do the work cold: what, why, open decisions, how, acceptance
criteria, dependencies. The bar is *execute-cold*: a session with no access
to the conversation that created the item can do the work from the document
alone. `templates/WI-template.md` is the shape.

**The index.** `00_index.md`, one line per open item (ID, link, status, one
sentence), read whole at every session start. It is hand-maintained and
edited by single lines only — never rewritten wholesale.

## Lifecycle

- **Create:** write the spec from the template, then append one line to the
  index. Before creating, read the index end to end — if an existing item
  already owns the ground, extend it instead.
- **Update:** status changes edit the spec; the index line follows.
- **Complete:** verify every acceptance criterion with evidence, append a
  completion record (what shipped, evidence, deviations, the date read from
  a live clock), add a one-sentence `outcome:` line at the top, move the
  spec to `completed/`, delete its index line, and run
  `python tools/build_completed_index.py` to regenerate the archive view.

## Scope changes

When an item's scope changes mid-flight, the spec records it on the spot:
one dated line under the section it changes,
`Scope change YYYY-MM-DD: <what changed> - <why, and on whose decision>`,
and the section itself is updated to match. A change absorbed silently
leaves the spec describing work that no longer exists, and the next
session builds the wrong thing.

`completed/00_completed_index.md` is GENERATED from the specs — read it for
history, never hand-edit it; edits there are lost on the next build.

## Rules that keep it working

- Every spec carries a `project:` tag as its first line, naming the project
  (or `global`) it belongs to; a spec without one counts as global. The
  board shows a project's items on its tab.
- A spec states what only it knows and points at whatever file owns the
  rest. It never restates another document.
- Acceptance criteria are checkable by the build itself. Where one depends
  on the user acting, the item still closes — with what they must do
  recorded beside it. Problems surfacing after closure belong to whichever
  session surfaces them; nothing gets reopened.
- The full procedure for creating and completing items, at depth, is
  `Skills/work-item-SKILL.md` in the workspace root.
