# Installing Fieldbook OS: instructions for the AI

You are the installing AI. The user pasted the README's prompt and pointed
you here. You hold the conversation; `install.py` does every mechanical
step, so every install builds the same tree. Read this whole file before
you say anything to the user, then work through it in order.

How to talk to the user throughout:
- One question at a time. Offer lettered choices where the question allows
  it, and always add that an answer in their own words is welcome. Where a
  choice restates a default you just explained, label it "(default)"
  instead of explaining it again.
- Answer what you can check yourself (a slot's size, the machine's time
  zone, a launch route, files already on disk) and ask only what you cannot.
- These instructions' section numbers and file names are yours alone;
  never show them to the user.
- Plain language. No jargon without a one-line explanation.
- When you use tools, do the work and then reply once; don't narrate each
  command.
- Never ask for, display or write a secret's value. Key names only.

**Keep the journal from your first step.** Every attempt you make (a
check, an install, a command, a question that changes the plan) gets one
line in the install journal, written with a plain file write as soon as
you can write files. Its location and line format are in
`workspace/Maintenance/README.md`, section "The install journal"; read it
where you are reading this file.

## 1. Reach the user's disk

You need to read and write files on the user's machine and run commands
there. Some AI tools run commands in a sandbox of their own: a separate
computer where writing and reading back works but none of it is the
user's disk. Browser and phone chats usually work this way. Prove it is
their machine: list their home folder (on Windows, `C:\Users\<name>`) or
their Desktop and ask them to confirm a file or two they recognise. A
Linux-style path such as `/home/...` or `/mnt/...` when they are on
Windows means a sandbox. Then write a small file in their home folder,
read it back with a command (`dir` or `ls`), and delete it.

If you cannot reach their disk, say so plainly in your first line: from
where you are running, you cannot reach their files, and that comes before
anything else. Then get them set up, one step per message, waiting for
their "done" (or a screenshot) before the next:

1. Ask whether they already have a desktop AI app or a coding agent
   installed (Claude Desktop, Claude Code, the ChatGPT or Codex app, Codex
   CLI, Cursor, VS Code agent mode, or similar). If one can reach files,
   use it.
2. Otherwise recommend one route, matched to the service they already pay
   for. Claude: Claude Desktop, then the Desktop Commander extension from
   the app's own Extensions directory (one click; no terminal or Node.js
   needed). ChatGPT: the Codex app or Codex CLI, which works on files
   directly. Anything else: that service's desktop app or coding agent.
3. Look up the chosen tool's current install steps on its own site or
   documentation before giving them. They change often; never give them
   from memory.
4. Walk them through it: download and install, sign in (they do this
   themselves), add the file connector if the tool needs one, restart if
   the steps say to. Give exact links.
5. If this same conversation now has file tools (some apps carry a chat
   over and add the connector mid-conversation), carry on here: repeat the
   disk proof above and continue. Otherwise hand them the README's prompt
   in a code block to paste into the new tool, and stop.

If they would rather not install anything, a chat-only tool can still take
the account rules: offer to fill in `tiers/account.md` with their time
zone for them to paste into their tool's custom instructions, and stop.

## 2. The plan, the mode and one yes

Tell the user in a few plain lines what an install does:
- Installs Python and Git if they are missing, and a command-line version
  of their AI if scheduled jobs need one (section 5).
- Builds one workspace folder that holds everything Fieldbook OS keeps.
- Registers a few small scheduled jobs (backups, a memory check, cleanup,
  the work-item launcher, the inbox reader) in Windows Task Scheduler.
- Touches nothing else on the machine except where a step below says so
  and they have seen it in this list: adding a command-line tool's folder
  to their own PATH, and, where their AI tool keeps its account rules in
  a file rather than a settings box, that file (section 6).

Then the quick defaults, briefly, with what each means:
- **Workspace:** `Documents\Fieldbook` in their home folder.
- **Working style:** the kit's defaults, kept as they are (they can read
  and change them any time).
- **Time zone:** the computer's own, which you show them to confirm.
- **About them:** skipped for now; they can tell the AI later.
- **Keys and paid services:** none.
- **Scheduler:** Windows Task Scheduler if their AI can be started from a
  command line (proven with one live run), otherwise jobs run by hand.
- **Dashboard:** follows the computer's light or dark mode, plain colours.
Asked either way, because no default is safe: the names of any projects
they want to start with, and where backups go.

Ask: **(a) Use the defaults (quick)** or **(b) Walk me through every
choice (customize)**.

Then the consent, once. One yes from them means you take control and do
everything in the plan you can reach, start to finish, without asking
again. On customize, also offer: "or I can ask before each change". That
yes covers this installation (or a later upgrade of it) only. It does not
carry into any other rule, task or later session.

These stay manual whatever they answered; you stop, say exactly what is
needed and where, and wait:
- Signing in to anything.
- System settings (the machine's time zone, Task Scheduler's "run whether
  logged on or not").
- Pasting rules into their AI tool's account settings.
- Anything that costs money.
- Anything that touches something that already exists: an existing file,
  folder, rules file or setup. Show what is there and what would change.

## 3. Prerequisites and the kit

Before running any install command, show the whole command with every
flag, in a code block, as part of the plan they agreed to. Never add a
flag they have not seen.

1. **Python and Git.** Run `python --version` and `git --version` (on
   Windows also try `py --version`). A clean Windows machine has a
   `python.exe` that only prints "Python was not found" or opens the
   Microsoft Store: that is a stub, not Python. Read the output, don't just
   check the exit. On Windows, install what is missing from winget's own
   source (the store source can fail with a certificate error):

       winget install -e --id Python.Python.3.12 --source winget
       winget install -e --id Git.Git --source winget

   On other systems use the platform's package manager.
2. **Check the disk before retrying.** winget can report "cancelled" or a
   failure for an install that landed. Look for the program before running
   anything again.
3. **Refresh PATH.** A program installed after your shell started is not
   on its PATH. Reload it from the machine and user values (PowerShell:
   `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')`)
   instead of asking them to restart.
4. **Get the kit.** Clone it into their home folder, or use the copy the
   prompt names, and work from there:

       git clone https://github.com/NullHypocrisy/fieldbook-os

5. **Prove you can write there.** Write a small file in the kit folder,
   read it back with a command, delete it.
6. `python install.py --check` from the kit folder. Read its JSON out in
   one line per item and fix anything it reports before going on.

Windows is the supported platform. On macOS or Linux, say the install runs
best-effort there: the steps are the same, and anything that fails is done
by hand with the user.

**Writing files on Windows.** Write UTF-8 without a byte-order mark.
Windows PowerShell 5.1's `Set-Content -Encoding utf8` and `Out-File` add
one, and a rules file that starts with one can break the tool's import.
Use your file tool's write, or
`[IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))`.

## 4. Already have a setup?

Look before asking: obvious note, task or memory folders an AI already
uses (an Obsidian vault, a notes tree, exported chats), and an existing
rules file for their tool. If you find something, name it and ask: (a)
start fresh beside it, or (b) bring it in after the install. On (b),
finish the install first; section 9 offers the migration. Nothing that
exists is changed during the install.

## 5. The answers

Both modes write the same answers file. Its fields and what each means are
documented in the installer itself; print them with:

    python -c "import install, json; print(json.dumps(install.ANSWERS_ABOUT, indent=1))"

### Settled by looking, in both modes

- **Account slot size** (`account_slot_chars`): how much text their AI
  tool's account-level rules hold. Use the tested value below for their
  tool and say which you used; look it up only for a tool not listed, and
  record 0 if the tool has no such place. The installer decides what fits
  there and puts the rest in the workspace rules file.

  | Tool | Where account rules go | Size to record |
  |---|---|---|
  | Claude (desktop app, browser) | Settings, personal preferences box | 6000 (no published limit; 6,000+ in use as of 2026-09-30) |
  | ChatGPT, paid plans | Settings, Personalization, custom instructions | 5000 (OpenAI, 2026-07-15) |
  | ChatGPT, Free and Go | same | 1500 |
  | Codex (app or CLI) | the file `~/.codex/AGENTS.md`, no settings box | 100000 (a file; no practical limit) |
  | Claude Code alone | the file `~/.claude/CLAUDE.md` | 100000 |
  | Microsoft Copilot agent | agent instructions | 8000 (Microsoft docs, 2026-09-30) |

- **Time zone.** The installer reads the computer's zone itself; show it
  to them as a named zone and ask them to confirm. If it is wrong, they
  change the computer's time zone in Windows settings themselves (you never
  change system settings), then run `python install.py --check` again to
  read the new one. There is no separate time-zone answer.
- **Launch route for scheduled jobs** (`scheduler`). Look for their AI's
  command-line tool on PATH: Claude Code (`claude`), Codex (`codex`), or
  their tool's equivalent. Rules:
  - Use a command on PATH, never a version-numbered path inside an app's
    own folder; that breaks on the app's next update.
  - If none is installed and their plan includes one, offer it as part of
    the plan (current install steps from its own site). If its installer
    leaves its folder off PATH, add that folder to the user's own PATH (not
    the machine's) and refresh PATH as in section 3.
  - Look up the tool's current flags for a non-interactive run that can
    read and write files in the workspace without stopping for approval
    (for example `claude -p ...`, `codex exec ...`).
  - Prove it with one live run that has to answer, for example a prompt
    asking for the word OK. A config file that says they are signed in is
    not proof; only an answer is.
  - Record it as `launch_command`, with `{instructions}` where the task's
    instructions file goes and `{workspace}` where the workspace goes. The
    installer wraps it in a small batch file and adds the input redirect
    itself.
  - No route proven: `kind: none`. Say plainly what that means: each job
    becomes a prompt they run by hand at its time, listed in
    `Setup/hand-run-tasks.md`. On Claude's free plan this is always the
    case, because Claude Code needs a paid plan.

### Quick

Fill every other answer with the defaults from section 2, then ask only:

1. **Projects.** "Is there something you already know you want to work on
   with this? Just the names; none is fine." Any wording works; the
   installer makes the folder name and keeps theirs as the title.
2. **Backups.** Daily and weekly destinations outside the workspace:
   another drive, a synced cloud folder or a network share, pinned to a
   real path. If they have none, a folder on the same disk is allowed;
   say it does not survive that disk failing. If one is removable, say a
   backup is skipped while it is absent and the health check reports the
   gap. Then say plainly: everything the workspace holds (memory, the
   search index, backups, any `.env` file of keys) is stored as plain,
   unencrypted files, and Fieldbook OS does not encrypt. We strongly
   advise an encrypted destination (an encrypted drive such as BitLocker,
   or an encrypted cloud folder); setting that up is theirs. Ask whether
   the destination is encrypted and record `encrypted` true or false.
   "No backups" is also a valid answer.
3. **Tour.** Last: "Would you like a guided tour once it's installed?"
   (a) Yes (b) Not now, I can ask for it later.

### Customize

Ask, in this order, one at a time:

1. **Projects**, as in Quick.
2. **About them.** "What should I know about you? Your name, what you do,
   and anything I should always keep in mind." A few lines; skipping is
   fine. Record it in their words as `about_user`.
3. **Working style.** Open `tiers/working-style.md`. Give one short
   plain-language summary of all the items with an option to keep them
   all; then walk only the ones they want to change, reading the placed
   text and asking its "Ask:" question. Record keep, drop, or their
   replacement text. On Decisions, also ask which decisions they want the
   system to simply make for them; the usual good answer is "anything that
   ends up with the same result either way".
4. **Where the workspace goes.** Suggest `Documents\Fieldbook` in their
   home folder. It must be empty or new.
5. **Backups**, as in Quick.
6. **Keys and cost.** "Do you use any services this setup will need keys
   for?" For each: the key's name only, the name it will carry in `.env`,
   and whether the service costs money and how much. Also ask about any
   paid service with no key. Never ask for a value.
7. **Scheduler.** Give your finding from the launch-route check and
   recommend: (a) Windows Task Scheduler with the route you proved, or (b)
   jobs run by hand. Either can be switched later. Mention any job time
   they may want to move (`times`).
8. **Dashboard look.** "The dashboard is one page that shows how
   everything is running. Light or dark?" (a) Match my computer (default)
   (b) Always dark (c) Always light. Then "Plain or colorful?" (a) Plain
   (default) (b) Colorful: a tinted background and a colour per section.
   Record `board_theme`: `auto`, `dark` or `light`, with `colorful-` in
   front for colorful.
9. **Tour**, as in Quick.

Read the answers back as a short list. On "ask me before each change",
get a yes here; otherwise go straight on.

## 6. Install

1. Write the answers to a file outside the kit, for example `answers.json`
   beside the workspace folder.
2. `python install.py --answers FILE --dry-run`. On "ask me before each
   change", summarise the plan and get a yes; otherwise check it matches
   what they agreed to and go on.
3. `python install.py --answers FILE`. Exit codes: 0 done; 2 broken (read
   the message, fix, rerun; finished phases are skipped); 3 held
   (`Setup/install-report.md` in the workspace says what to act on: a
   `.fieldbook-new` file beside one of theirs means you and the user merge
   the two, never overwrite).
4. **Their tool's rules file.** The tool must read the workspace's
   `AGENTS.md` whenever it works there. Codex and most coding agents read
   `AGENTS.md` natively; nothing to do. Claude tools read `CLAUDE.md`:
   write a `CLAUDE.md` in the workspace containing the one line
   `@AGENTS.md`, nothing else (not a copy, not a link). Any other tool:
   its own rules-file setting, pointed at `AGENTS.md`.
5. **Account rules.** If `Setup/account-slot.txt` exists, its text goes
   where the table in section 5 says.
   - A settings box: show the text in a code block and tell them exactly
     where to paste it. They paste it themselves; if the box already holds
     something, it is replaced only if they say so.
   - A file (`~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`): if it does not
     exist, write it. If it does, show what is there and what would be
     added, and merge only on their yes.
   If `Setup/account-slot.txt` does not exist, the rules were placed at
   the end of the workspace's `AGENTS.md`; say so in one line.
6. **A fresh session.** Account rules only load when a conversation
   starts, so the next part runs in a new one, which also proves the rules
   took. Give them this prompt in a code block, with the paths filled in,
   and tell them where to open it (a new chat in their tool; for a
   command-line tool, started inside the workspace folder):

       Continue my Fieldbook OS install. The workspace is WORKSPACE and the
       kit is KIT. Read KIT/INSTALL.md and pick up at section 7, "Prove it".

   That session's first line must say it read the workspace's `AGENTS.md`.
   If it doesn't, the account rules or the rules file did not take: fix
   that with them before anything else.

## 7. Prove it

(Run in the fresh session. Keep writing journal lines.)

1. From the workspace: `python Maintenance/doctor.py`, then
   `python Maintenance/dashboard_build.py`, and open `dashboard.html` in
   their browser. Read out any WARN or FAIL with its fix. A WARN that
   follows from their own choice (no backups, unencrypted backups) is
   expected; say so.
2. **Run every scheduled job once through the scheduler,** not by calling
   its script: on Windows, `schtasks /Run /TN "<task name>"` for each task
   the installer registered (`Setup/install-report.md` names them). Then
   read `Scheduled/runs.log` and confirm each left a line. A job with
   nothing to do ends "empty"; that is a pass.
3. Say plainly: Windows runs these jobs only while they are logged on. If
   they want them to run when logged off, that is a setting they change in
   Task Scheduler themselves; give the steps if asked.
4. **Native procedures.** The procedures in `Skills/` work in any tool
   through `Skills/00_triggers.md`. If their tool has its own skill format,
   offer to install them there too; the files in `Skills/` stay the source.
5. Confirm, by listing the folder, that the workspace really is on disk.

## 8. Tour, and the one lesson nobody skips

If they said yes to the tour, follow `Skills/tour-SKILL.md` now; it ends
with closing a session.

If they said no, still do its last stop, "Closing a session", hands-on.
Say why in one sentence: closing a session is what writes the logs, memory
and commit that everything else runs on, so an unclosed session is work
the system never learns about. Then tell them the full tour is there any
time with "give me the tour".

## 9. Existing setup

If they chose (b) in section 4, offer `Skills/migrate-SKILL.md`: an audit
first, then a migration they approve part by part.

## 10. Finish

Last step: `python Maintenance/doctor.py --report`. It writes a diagnostic
bundle that stays on this computer; if anything went wrong, it is what the
"file a bug" procedure works from.

Then tell them in a few lines: where the workspace is, what the health
check said, where backups go (and whether they are encrypted, by their
choice), what runs on a schedule or by hand, and the one sentence that
starts a session if their tool doesn't do it on its own: "read AGENTS.md".
If anything is unfinished, say what and why.
