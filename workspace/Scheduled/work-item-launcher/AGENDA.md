# Work-item launcher agenda

The precheck printed `WORK <file>`: that spec in `Work Items/` is this
run's one item. The user marked it `| Run | launcher |`, which says every
decision the work needs is already in the spec, so it can be built with
nobody watching. Nobody is here to catch a bad start, so the checks below
are the whole safety net. Do not pick a different item.

Read `Work Items/README.md` and the spec in full, then everything the spec
points at.

## 1. Check before touching anything

- **No open decision.** List the spec's open decisions, then walk the
  build step by step and add every choice it would force that the spec
  does not settle: a design choice, a missing parameter, a trade-off. A
  choice that ends in the same result either way is yours; one that leaves
  the user with a different result is theirs. If the list is not empty,
  hand the item back (below) with the list.
- **The spec matches the files.** Check what the spec says about the
  current state against the files themselves. A contradiction is a hand-
  back with the contradiction named.

## 2. Build

Deliver what the spec's What and Acceptance describe, at the scope they
set: nothing added, nothing polished beyond it, nothing left out. Follow
AGENTS.md throughout. If a decision surfaces mid-build that the check missed, stop
there: hand the item back with the decision and a line on the partial
state. Deciding it yourself and reporting it afterwards is the one thing
this run must never do.

If you cannot finish well in this session, stop at a clean seam instead of
rushing: add a `## Progress` section to the spec (done, what remains, what
the next run needs to know), leave the Run row as it is, and log the run
as held. The next run resumes this item before any other.

## 3. Finish

Close the item with the COMPLETE branch of `Skills/work-item-SKILL.md`.
Acceptance criteria that need the user do not hold the item open: the
branch records them beside the criterion, and you also file each one to
the attention queue (below). Then:

    python Scheduled/runlog.py work-item-launcher 0 "WI-NN completed"

## Handing an item back

1. Change the spec's Run row to
   `| Run | attended - handed back YYYY-MM-DD: <one-line reason> |`
   (date read from the clock). The precheck stops picking it; the user
   restores the mark once they have settled it.
2. File one attention item naming the work item and, for each decision,
   the options you can see:

       python Maintenance/attention.py --file "TEXT" --source work-item-launcher --key "launcher:WI-NN"

3. Log the run as held:

       python Scheduled/runlog.py work-item-launcher 3 "WI-NN handed back: 2 open decisions"

## Before the turn ends

Write the day-log entry AGENTS.md asks for, commit with
`python Maintenance/close_commit.py -m "WI-NN: <what happened>"`, then
reply in one line: which item, and whether it completed, stopped partway
or was handed back. The spec, the day log and the attention queue hold everything else.
