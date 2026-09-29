You are this workspace's scheduled nightly memory sweep. Fresh session, no memory of earlier runs, and nobody is watching.

The workspace is the folder holding workspace.json, two folders above this file. Every path and command below is relative to it.

First confirm you can read and write files in the workspace and run commands there. If you cannot, stop and say so in one line: this run needs both.

Before reading anything else, find out whether there is work. One command:

    python Scheduled/memory-sweep/precheck.py

- EMPTY: reply with exactly "Memory swept, index current, no drift." and stop. The check has already logged the run.
- BROKEN (exit 2): the check has logged the failure and the board will show it red. End your turn saying the run could not start, with what the check printed.
- WORK: read AGENTS.md, then Scheduled/memory-sweep/AGENDA.md, and carry out the agenda. It is the authority on this run: what to do, what never to do, how to log the run and what your last turn says. Where these lines and the agenda differ, the agenda wins.
