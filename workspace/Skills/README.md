# Procedures

Each `<name>-SKILL.md` file here is a procedure: the steps the assistant
follows when the user asks for that job by name ("file a bug", "add a work
item"). Plain markdown, so any assistant that can read files can follow one.

## Frontmatter convention

Every procedure file opens with this block, and nothing else comes first:

    ---
    name: work-item
    description: One line saying what the procedure does and when to use it.
    triggers:
      - "add a work item"
      - "close out this work item"
    ---

- `name` matches the file name: `work-item` lives in `work-item-SKILL.md`.
- `description` is one line. Tools with a native skill format read it to
  decide when the procedure applies, so it names the job, not the steps.
- `triggers` lists the phrases a user is likely to say, one per line, each
  quoted. Close variations need not be listed; the assistant matches intent.

Other keys may follow (a tool's native format can add its own); the index
ignores them.

## The trigger index

`00_triggers.md` maps every trigger phrase to its procedure. It is
GENERATED from the frontmatter — never edit it by hand. After adding,
renaming or changing a procedure, rerun:

    python "Skills/tools/build_trigger_index.py"

It prints `unchanged` or `written`, exits 0, and exits 2 naming the file
when a procedure's frontmatter breaks the convention (the index is then
left as it was). `AGENTS.md` points sessions at the index, so a tool with no
native skill format still finds the right procedure.

## Native installation

Where a tool has its own skill format (Claude skills, for one), a procedure
can also be installed there. The file here stays the source; the installed
copy is the runtime, and the user moves each change across by reinstalling.
