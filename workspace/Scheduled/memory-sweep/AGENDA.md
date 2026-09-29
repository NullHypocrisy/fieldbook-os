# Memory sweep agenda

The precheck has already refreshed the search index and found drift: each
item it printed after "WORK drift:" is one tenant whose memory is out of
shape. Your job is to make each one plain enough for the user to settle at
their next session. The sweep never writes memory itself. Memory belongs to
the sessions that do the work, which write it at their close under the
admission test in AGENTS.md; an overnight rewrite would judge a day it did
not see.

## For each item

- **Over cap** (working memory or core profile): read the file and the
  admission test. For each line that fails the test, name the file that
  should own it instead (its spec, a rules file, a project document) or
  say it belongs to a day log alone. A file over cap has lines in the wrong
  home; the fix is moving them, never raising the cap.
- **Working-memory file missing**: check `Memory/tenants.json` names the
  right path and whether the file moved. Say which.

File one attention item per tenant, standing on its own: which memory, how
far over, and the moves you propose, line by line.

    python Maintenance/attention.py --file "TEXT" --source memory-sweep --key "memory:<tenant>"

The key repeats night after night, so a tenant already filed is not filed
twice.

## Never

- Edit, trim or reorder any memory file, even a line you are sure of.
- Raise a cap.

## Close the run

1. Append one line per tenant to today's global day log,
   `Memory/global/logs/YYYY-MM-DD.md` (date read from the clock): the
   drift and what you filed.
2. Log the run as held, since it needs the user:

       python Scheduled/runlog.py memory-sweep 3 "drift filed for 1 tenant"

3. Commit: `python Maintenance/close_commit.py -m "memory sweep: <summary>"`.
4. Reply in one line: the sweep ran, and anything that looks off. The attention queue holds the rest.
