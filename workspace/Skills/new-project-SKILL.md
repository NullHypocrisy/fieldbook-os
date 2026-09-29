---
name: new-project
description: Set up a new project in the workspace with the user, including its rules, memory, inbox and its own dashboard tab designed with them.
triggers:
  - "new project"
  - "start a project"
  - "add a project"
  - "set up a project"
---

# New project

A project is one area of the user's life or work that gets its own rules,
memory, inbox and dashboard tab, all under one short name. No two projects
look alike, so the tab is designed with the user, never copied from a
template. `Projects/README.md` owns the folder layout and the tab format;
read it before step 4.

Ask one question at a time, with lettered choices where they fit, and say
an answer in their own words is welcome.

1. **What it is.** Ask what the project is for and what "going well" would
   look like. Propose a short lowercase name (letters, digits, hyphens) and
   confirm it.

2. **What it keeps.** Ask what information the project lives on: files they
   already have, data a script or tool produces, notes, deadlines. Note each
   file's path; nothing is moved yet.

3. **Create it.** `python Maintenance/new_project.py NAME --dry-run`, say
   what it will create, then run it without `--dry-run` on their yes. It
   makes the memory tenant, `Projects/NAME/` and the inbox, and never
   overwrites anything.

4. **Design the tab.** Explain that every project tab can show its open
   work, its memory, its inbox and anything waiting on them, and ask which
   of those they want, in what order: (a) all four (b) pick. Then, for each
   thing from step 2 worth watching, ask:
   - Would you like to see it on this tab? (a) yes (b) no
   - How: (a) as a table (b) as a short list of values (c) as text
   - Should it warn you when it goes stale? If yes, after how many days, and
     is stale (a) worth a glance (amber) or (b) something you must act on
     (red, also added to your waiting-on-you list)?
   Use your judgment to suggest what fits the project, and say why in one
   line. Write `Projects/NAME/dashboard.json` to the format in
   `Projects/README.md`.

5. **Its rules.** Fill the placeholders in `Projects/NAME/PROJECT.md` from
   steps 1 and 2. Ask whether anything must always or never happen in this
   project (files never to edit, what needs their approval). An empty rules
   section is fine; do not invent rules.

6. **Show them.** `python Maintenance/dashboard_build.py`, open the new tab
   and walk it panel by panel: what each shows and what would turn it amber
   or red. Change anything they want changed now.

7. **Finish.** Commit: `python Maintenance/close_commit.py -m "new project NAME"`.
   Tell them sessions for this project start by naming it, so the AI reads
   its rules and memory.
