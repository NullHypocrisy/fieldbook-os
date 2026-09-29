---
name: tour
description: A guided, hands-on tour of a Fieldbook OS workspace for a new user, ending with their first real project and work item.
triggers:
  - "give me the tour"
  - "guided tour"
  - "show me around"
  - "how does this work"
---

# Tour

A tour is a tutorial the user does, not a lecture. At each stop: say in two
or three plain sentences what the system is for, do one real thing with it
together, show where it appears on the dashboard, then ask whether to go
on. The user can skip any stop or end the tour early, except the last one:
closing a session always runs, because it is what makes every other
system work. Say both at the start. Keep what is real (their project, their work item); clean up only
what was made as a sample, and say which is which as you go.

Rebuild the board (`python Maintenance/dashboard_build.py`) after each stop
that changes something, and ask the user to refresh the page.

## Stops

1. **The dashboard.** Open `dashboard.html`. Walk the Global tab: each tile,
   what gray, amber and red mean (amber is drifting, red needs them and is
   always also on the waiting-on-you list), and that clicking a card opens
   its detail page. Point out that each project gets its own tab.

2. **Their first project.** Ask what they want to work on first; if they
   named projects during install, offer those. Follow
   `Skills/new-project-SKILL.md`, which includes designing the project's
   tab with them. End on their new tab.

3. **A work item.** Ask for one real thing in that project that will not be
   finished today. Create it with `Skills/work-item-SKILL.md`, tagged with
   the project. Show it on the project tab and in `Work Items/00_index.md`.

4. **Memory.** Explain working memory (a small always-read note per
   project) versus day logs (the searchable archive). Ask for one fact worth
   keeping and store it with `Skills/remember-SKILL.md`. Then search for it:
   `python Memory/engine/search.py "<a word from it>"`.

5. **Waiting on you.** Explain that anything needing their decision, from a
   session or an overnight job, lands in one queue. File a sample:
   `python Maintenance/attention.py --file "Tour sample: nothing to do" --key tour-sample`.
   Show it on the board, then clear it with `--clear` and the id it printed.

6. **Messages between projects.** Explain the bridge: projects never write
   into each other's folders; they leave a message in an inbox. Show the
   project's inbox folder and `Agent Bridge/README.md`'s one-paragraph
   format. Only if they have two projects, offer to send a real note.

7. **Scheduled jobs.** Show the scheduled-jobs tile and what each job does
   (`Scheduled/README.md`). Run one check by hand so a line appears:
   `python Scheduled/memory-sweep/precheck.py`. If they chose no scheduler,
   show `Setup/hand-run-tasks.md`.

8. **Backups.** If destinations are set, offer to run the first daily
   backup now (`python Maintenance/backup.py --tier daily`) and show it on
   the board. Explain the restore drill: the weekly backup restores a copy
   to prove it works; until the first one runs the board says "not run yet".
   Remind them their backups are only as private as the destination.

9. **Health check.** Run `python Maintenance/doctor.py` and read the result.
   Tell them to run it, or ask you to, whenever something seems off.

10. **Closing a session (never skipped).** Explain that a session only
    counts once it is closed: the close writes the day-log entry, updates
    memory and commits the workspace, and a session left open is work the
    system never learns about. Show the words that close one ("we're done")
    and what happens, then do it now for real, as the end of the tour.

Just before stop 10, list the jobs they can ask for by name from
`Skills/00_triggers.md`, in one short line each, and mention "file a bug"
for problems with Fieldbook OS itself.
