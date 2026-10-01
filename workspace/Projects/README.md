# Projects

A project is one area of work with its own rules, memory, inbox and
dashboard tab, all under one short name (letters, digits, `-` and `_`),
made from the name as typed ("Raised Bed Garden" becomes
`Raised-Bed-Garden`); the tab shows the typed name:

- `Memory/NAME/` and its entry in `Memory/tenants.json`: working memory.
- `Projects/NAME/PROJECT.md`: the project's rules, read after `AGENTS.md`.
- `Projects/NAME/dashboard.json`: its tab on the board.
- `Agent Bridge/to-NAME/`: its inbox.

`python Maintenance/new_project.py NAME` creates all four and never
overwrites; the installer does the same for each project named at setup.
A work item belongs to a project when its first line is `project: NAME`;
without that line it is global. Everything under `Projects/NAME/` is yours:
upgrades never replace it.

## The tab: dashboard.json

    {"title": "Garden", "panels": [panel, ...]}

Panels render in list order. Standard panels are `{"type": T}` with T one of:

- `work`: this project's open work items.
- `memory`: its working memory against its cap.
- `inbox`: open messages in `Agent Bridge/to-NAME/`.
- `attention`: waiting-on-you entries whose source or text names the project.

A file panel shows a file the project keeps:

    {"type": "file", "title": "Harvest log", "path": "Projects/garden/harvest.csv",
     "render": "table", "stale_days": 7, "stale_state": "warn"}

- `path`: relative to the workspace root, and inside it.
- `render`: `table` (a JSON list of objects, or a CSV), `kv` (a JSON
  object) or `text` (the first 40 lines). A file that does not fit its
  render shows as text, with a note.
- `stale_days` (optional): the file is stale when last modified longer ago.
- `stale_state` (default `warn`): stale shows amber (`warn`), or red and
  added to the waiting-on-you queue (`bad`).

A missing file shows an amber note. A missing or unreadable dashboard.json
shows a banner on the tab; the rest of the board still builds.
