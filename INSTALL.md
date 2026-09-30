# Installing Fieldbook OS: instructions for the AI

You are the installing AI. The user pasted the README's prompt and pointed
you here. You hold a conversation; `install.py` does every mechanical step,
so every install builds the same tree. Read this whole file before you say
anything to the user, then work through it in order.

How to talk to the user throughout:
- One question at a time. Offer lettered choices where the question allows
  it, and always add that an answer in their own words is welcome. Where a
  choice restates a default you just explained, label it "(default)"
  instead of explaining it again.
- Answer what you can check yourself — a slot's character limit, the
  machine's time zone, an existing launch route, files already on disk —
  and ask only what you cannot.
- These instructions' section numbers and file names are yours alone;
  never show them to the user.
- Plain language. No jargon without a one-line explanation.
- Before anything is installed or changed on their machine, say exactly what
  will be done and get a yes. Never assume consent carries to the next step.
- Never ask for, display or write a secret's value. Key names only.

## 1. The tool, and can it reach the disk

Establish first, mostly by looking rather than asking:

- **Which AI tool they will use day to day.** Usually you are it; confirm
  in one line rather than ask cold.
- **Its account-level instructions slot** (the custom-instructions box that
  applies to every chat) and its character limit. Look this up yourself —
  the tool's settings or documentation, or browse — and tell them what you
  found; ask only what you cannot verify. No such box means 0. The
  installer decides what fits there and puts the rest in the workspace
  rules file.
- **File access.** You need to read and write files on the user's machine
  and run commands. Some AI tools run commands in a sandbox of their own:
  a separate computer where writing and reading back works but none of it
  is the user's disk. Browser and phone chats usually work this way. So
  prove it is their machine, not just a machine: list their home folder
  (on Windows, `C:\Users\<name>`) or their Desktop and ask them to confirm
  a file or two they recognise. A Linux-style path such as `/home/...` or
  `/mnt/...` when they are on Windows means a sandbox. If it is theirs,
  also write a small file into the folder where this kit sits, read it
  back with a command (`dir` or `ls`), and delete it.

If you cannot reach the disk, fixing that comes before any interview. Say
so plainly: from where you are running, you cannot reach their files. Then
set them up with a tool that can, one step per message, waiting for their
"done" (or a screenshot) before the next:
  1. Recommend one. If they are in a Claude chat (browser or phone), that
     is Claude Desktop with the Desktop Commander connector. Otherwise it
     is their AI's desktop app with a file-access connector, or a coding
     agent that already has access (Claude Code, Codex CLI, Cursor, VS Code
     agent mode, and similar). Ask only if they have a preference.
  2. Look up that tool's current install and connector steps yourself, on
     its own site or documentation. They change often, so never give them
     from memory.
  3. Walk them through it: download and install, sign in, add the
     connector, restart if the steps say to. When a step needs something
     else on their machine (some connectors need Node.js), say in one
     sentence what it is for and give the exact link or command.
  4. Hand them the prompt to paste into the new tool, in a code block: the
     one from README.md, which starts this file over from the top there.
  5. Stop. Everything else happens in the new tool.
If they would rather not install anything, a chat-only tool can still take
the account rules: offer to fill in `tiers/account.md` with their time zone
for them to paste into their tool's custom instructions.

## 2. Prerequisites

Run `python --version` and `git --version` (on Windows, try `py --version`
if `python` is missing). If both work, run `python install.py --check` from
this folder and read its JSON out in one line per item.

For anything missing, explain what it is for in one sentence and offer a
scripted fix, stating the exact command first. On Windows:
`winget install Python.Python.3.12` and `winget install Git.Git`. On other
systems use the platform's package manager. Run it only on a yes; after, the
user may need to open a new terminal. Re-run the check until it passes.

Windows is the supported platform. On macOS or Linux, say that the install
runs best-effort there: the steps are the same, and anything that fails is
done by hand with the user.

## 3. Already have a setup?

With file access, look before asking: obvious note, task or memory folders
an AI already uses (an Obsidian vault, a notes tree, exported chats). Then
confirm, naming anything you found: (a) this is a fresh start, or (b) I
already keep notes, memory or task lists my AI uses. On (b), finish the
install first; section 7 offers the migration.

## 4. The interview

The answers become one JSON file. Its fields and what each means are
documented in the installer itself; print them with:

    python -c "import install, json; print(json.dumps(install.ANSWERS_ABOUT, indent=1))"

Order runs from the biggest questions down: what this is for, how the AI
should work with them, then the machinery, then fine preferences. The tool
and its slot are already settled from your first step. Ask, in this order:

1. **Purpose.** "Is there something you already know you want to work on
   with this?" Names only, short. None is fine; the tour can create one.
2. **About them.** "What should I know about you? Your name, what you
   do, and anything I should always keep in mind." A few lines is plenty;
   skipping is fine. Record it, in their words, as `about_user`.
3. **Working style.** Open `tiers/working-style.md`. For each item, read
   the placed text in plain words, then ask its "Ask:" question. Record
   keep, drop, or their replacement text. On the Decisions item, also ask
   which decisions they want the system to simply make for them; the usual
   good answer is "anything that ends up with the same result either way".
4. **Where the workspace goes.** Suggest a folder in their home directory,
   for example `Documents/Fieldbook`. It must be empty or new.
5. **Time zone.** Read it from the machine (`tzutil /g` on Windows, `date`
   elsewhere) and confirm it with them as a named zone; ask only if the
   machine gave no answer.
6. **Backups.** Two destinations, both outside the workspace: daily and
   weekly (another drive, a synced cloud folder, a network share). Pin
   each to a concrete path. If one is removable (a thumb drive), say
   plainly that a backup is skipped when it is absent and the doctor
   reports the gap. Then say this plainly: everything the workspace holds,
   memory, the search index, backups and any `.env` file, is stored as
   plain, unencrypted files. Fieldbook OS does not encrypt. We strongly
   advise an encrypted destination (an encrypted drive such as BitLocker,
   or an encrypted cloud folder); setting that up is theirs to do. Record
   what they choose, or no backups.
7. **Keys and cost.** "Do you use any services this setup will need keys
   for?" For each: the key's name only, the name it will carry in `.env`,
   and whether the service costs money and how much. Also ask about any
   paid service with no key. Never ask for a value.
8. **Scheduler.** The workspace has small scheduled jobs (backups, a memory
   check, cleanup, the work-item launcher, the inbox reader); `Scheduled/README.md`
   describes each. Before asking, look yourself for a way to start a
   file-capable AI session from a command line with a prompt file (an
   installed CLI agent such as Claude Code); that becomes `launch_command`.
   Then ask, stating your recommendation: (a) Windows Task Scheduler —
   recommend this when you found a launch route, naming it; or (b) no
   scheduler, they run the jobs by hand — recommend this when you found
   none. Either can be switched later.
9. **Dashboard look.** "The dashboard is one page that shows how everything
   is running. Should it be light or dark?" (a) Match my computer: light,
   or dark whenever the computer is set to dark mode (default) (b) Always
   dark (c) Always light. Then: "Plain, or colorful?" (a) Plain: calm,
   neutral colours (default) (b) Colorful: a tinted background and a
   colour for each section. Add that they will see it at the end of the
   install and can switch any time by asking. Record it as `board_theme`:
   `auto`, `dark` or `light`, with `colorful-` in front for colorful.
10. **Last question:** "Would you like a guided tour of your new Fieldbook OS
   once it's installed?" (a) Yes (b) Not now, I can ask for it later.

Read the answers back as a short list and get a yes before writing them.

## 5. Install

1. Write the answers to a file outside the kit (for example
   `answers.json` beside the workspace folder).
2. `python install.py --answers FILE --dry-run`. Summarise the plan in a few
   lines and get a yes.
3. `python install.py --answers FILE`. Exit codes: 0 done; 2 broken (read
   the message, fix, rerun; finished phases are skipped); 3 held (the
   report at `Setup/install-report.md` in the workspace says what to act on:
   a `.fieldbook-new` file beside an existing one means you and the user
   merge the two, never overwrite).
4. **Account rules.** If `Setup/account-slot.txt` exists, show its text and
   tell the user exactly where in their tool to paste it, replacing
   anything that was there only if they agree. If it does not exist, the
   rules were placed at the end of the workspace's `AGENTS.md`; say so.
5. **Your tool's rules file.** Point the tool at the workspace's `AGENTS.md`
   as its read-first file (Claude tools read `CLAUDE.md`: copy or link it
   under that name; other tools use their own rules-file setting).
6. **Prove it.** From the workspace: `python Maintenance/doctor.py`, then
   `python Maintenance/dashboard_build.py`, and open `dashboard.html` in their
   browser. Read out any WARN or FAIL with its fix. Confirm, by listing the
   folder, that the workspace really is on disk.
7. **Native procedures.** The procedures in `Skills/` work in any tool
   through `Skills/00_triggers.md`. If their tool has its own skill format,
   offer to install them there too, and explain that the files in `Skills/`
   stay the source.

## 6. Tour, and the one lesson nobody skips

If they said yes to the tour, follow `Skills/tour-SKILL.md` now; it ends
with closing a session.

If they said no, still do its last stop, "Closing a session", hands-on,
before you finish. Say why in one sentence: closing a session is what
writes the logs, memory and commit that everything else runs on, so an
unclosed session is work the system never learns about. Then tell them the
full tour is there any time with "give me the tour".

## 7. Existing setup

If they answered (b) in section 3, offer `Skills/migrate-SKILL.md`: an audit
first, then a migration they approve part by part.

## 8. Finish

Tell the user in a few lines: where the workspace is, what the doctor
said, where backups go (and whether they are encrypted, by their choice),
what runs on a schedule, and the one sentence that starts each session:
"read AGENTS.md". If anything is unfinished, say what and why.
