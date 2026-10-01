# Fieldbook OS

**An agentic OS you set up with one prompt.**

Fieldbook OS turns an AI assistant into one that remembers, keeps track of
work, and looks after itself between conversations. It is a folder of plain
files and small Python scripts that any file-capable AI can run: memory that
lasts across sessions, work tracked from idea to done, messages between
projects, backups and cleanup, scheduled jobs, and a dashboard that shows
all of it at a glance. Nothing here calls a model or needs a subscription;
your AI is the operator and the scripts are the machinery.

## Install

Open your AI, even a chat in your browser, and paste this:

> Install Fieldbook OS for me. Get it from
> https://github.com/NullHypocrisy/fieldbook-os (clone it, or use the copy
> I have at: _path, if you have one_), then read INSTALL.md in it and follow
> it from the top. Ask me what you need to know as you go.

The AI checks what your computer needs, walks you through a short
interview (where things go, how you like to work, backups, which projects
to start with), runs the installer, proves the result, and offers a guided
tour. Nothing is installed without telling you exactly what first.

**Supported:** Windows, Python 3.10 or newer, git. The AI helps you get
Python and git if you don't have them. macOS and Linux work best-effort:
same steps, with the AI doing by hand whatever the scripts don't cover yet.

**Your AI can't reach your files?** A browser or phone chat usually
can't. It will notice, walk you through setting up one that can (for
Claude, the desktop app with a file connector), and hand you the prompt
to paste there. If you'd rather install nothing, it can still fill in
`tiers/account.md` for you to paste into its custom instructions.

## What you get

- **Rules in three layers.** Account-level rules that hold in every chat
  (`tiers/`), workspace rules for any session that can read the folder
  (`workspace/AGENTS.md`), and a rules file per project. Each rule lives in
  exactly one layer.
- **Memory.** A small always-read note per project, day logs as the
  archive, and full-text search over everything ever written.
- **Work items.** One spec per piece of work, an index, a generated
  archive, and a launcher that can run marked items unattended.
- **Projects.** Each with its own rules, memory, inbox and dashboard tab,
  designed with you when you create it.
- **Agent Bridge.** File-based messages between projects or agents.
- **Backups, quarantine and cleanup.** Nothing is hard-deleted; backups
  are tested by a restore drill.
- **Scheduled jobs.** Each checks first whether there is anything to do,
  so an empty night costs nothing. See `workspace/Scheduled/README.md`.
- **Dashboard and waiting-on-you queue.** One static page; anything that
  needs you is marked and also queued.
- **Doctor and upgrades.** `doctor.py` checks the installation any time;
  `upgrade.py` brings a newer kit in without overwriting your changes.

## Security: read this

Everything is stored as plain, unencrypted files: memory, the search index,
backups, and any `.env` file holding keys. Fieldbook OS does not encrypt.
We strongly advise putting backups on an encrypted destination (an
encrypted drive or an encrypted cloud folder) and keeping the workspace on
an encrypted disk. Doing that is up to you: setup records whether your
backups are encrypted, and the health check keeps flagging unencrypted
ones. [SECURITY.md](SECURITY.md) has the details and how to report a
security problem.

## Stability and license

From 1.0.0, 1.x releases keep the workspace layout, the upgrade path, the
answers file and the rule keys working; [STABILITY.md](STABILITY.md) says
exactly what is promised. MIT licensed: see [LICENSE](LICENSE).

## Layout

    INSTALL.md       the installing AI's instructions
    install.py       builds a workspace from the interview's answers
    upgrade.py       upgrades an existing workspace to this kit version
    tiers/           account rules, default working style, project template,
                     and keys.json, the rule keys the doctor checks
    workspace/       everything the installer places, each system with its README
    sanitize.py      checks a folder for secrets before anything is shared

## Problems and feedback

Ask your AI to "file a bug". It gathers the details, strips anything
personal or secret, shows you the report, and files it on GitHub (or gives
you a link to submit it yourself).

## Sharing your own copy

Before pushing a copy anywhere, run `python sanitize.py <folder>
[--terms your-terms.txt]`. Exit 0 means nothing found; exit 1 lists each
finding with file and line.
