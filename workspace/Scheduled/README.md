# Scheduled pieces

The tasks that keep the four systems working while nobody is at the
keyboard. Each folder here is one task, and every task has the same shape:

- `INSTRUCTIONS.md` - the only text the scheduler hands an AI session. It
  says three things: confirm file access, run the precheck, and on WORK
  follow the task's agenda (or run its wrapper). Everything else lives on
  disk, so changing a task never means re-registering it.
- `precheck.py` - answers "anything to do?" in one call, before the
  session reads anything else, so an empty run costs next to nothing. It
  prints `EMPTY` only when there is provably nothing to do, `WORK ...` when
  there is, and `BROKEN ...` (exit 2) when it cannot tell. EMPTY and BROKEN
  write the run's log line themselves.
- `AGENDA.md` (tasks needing judgment) or `run.py` (mechanical tasks) -
  what a WORK run does.
- `schedule.json` - when it runs: `{"schedule": "DAILY" | "WEEKLY", "day":
  "SUN", "time": "HH:MM"}`. The installer reads it to register the task
  (its docstring owns that contract); the board and the doctor read it to
  tell an overdue task.

Where no scheduler is wired, each task is a prompt you run by hand: start
an AI session that can read files and give it the task's `INSTRUCTIONS.md`.

## The run log

Every run leaves one line in `runs.log` here, appended, never rewritten:

    YYYY-MM-DD HH:MM | task | exit N | result

The time is the local clock read when the line is written; the task is the
folder name; the exit code is 0 fine, 1 crashed, 2 broken, 3 held (ran,
and left something for you); a result starting "empty" or "nothing" means
there was nothing to do. `runlog.py` is the one writer (`python
Scheduled/runlog.py TASK CODE "RESULT"` from a session); the board
(`Maintenance/dashboard_build.py`) renders it as scheduled-piece health and
the doctor checks it. The doctor logs itself here as task `doctor`.

## The tasks

**work-item-launcher** (daily 01:00). Builds one work item end to end while
you are away. It only ever takes an item you have marked with a
`| Run | launcher |` row in the spec's table, which is your statement that
every decision the work needs is already written down. The precheck picks
the item deterministically: a run that stopped partway first, then the
order in `Work Items/scores.md` if you keep one, then the Priority row,
then the lowest id; items waiting on an open dependency are skipped. The
session checks the spec for decisions it leaves open and hands the item
back to you (Run row changed, attention item filed) rather than deciding
anything itself.

**bridge-reader** (daily 03:00). Reads `Agent Bridge/to-global/`: answers
questions from the files, does small work that changes no outcome, and
turns anything larger into a work item. Anything only you can decide stays
open and is filed to your attention queue. Its precheck also files any
message, in any inbox, left unread past the board's threshold, so mail in
an inbox with no reader still reaches you.

**memory-sweep** (daily 04:00). Refreshes the search index and audits
memory against `Memory/tenants.json`: a working-memory file missing, or a
working memory or core profile over its cap. Drift gets a session that
proposes where each misplaced line belongs and files that for you; it
never edits memory itself.

**backup-daily** (daily 05:00) and **backup-weekly** (Sunday 05:30). Run
`Maintenance/backup.py` for their tier when a snapshot is due. No
destination set is an empty run; a destination that cannot be reached is a
broken one, red on the board. When a weekly snapshot lands, the weekly task
then runs `Maintenance/restore_drill.py`, logged as `restore-drill`.

**cleanup** (Sunday 06:30, after the weekly backup). Runs
`Maintenance/cleanup.py` when anything in `Quarantine/` or `Temp/managed/`
is past expiry. With no backup landed that week it deletes nothing and
logs the run as held.
