# Changelog

What changed in each version, newest first. One entry per version, short
on purpose; the commit history has the detail.

## 0.9.7 (2026-09-30)

- The install starts with the whole plan and one choice: quick (defaults,
  asking only project names and backups) or customize (every question).
  One yes covers the install and nothing beyond it; sign-ins, system
  settings, pasting account rules, paid services and anything already on
  the machine still stop for you.
- Works from any AI service: the installing AI finds its own file and
  command-line tools (Codex for ChatGPT, Claude Desktop or Claude Code for
  Claude), with tested sizes for each tool's account rules.
- After the account rules are placed, the install continues in a fresh
  session whose first line proves it read AGENTS.md; it ends by running
  every scheduled job through the scheduler and writing the diagnostic
  report.
- Account rules rewritten (look for a file tool before deciding there is
  none; write down how to get an answer, not a frozen one; the session's
  start date goes stale). Working style: Decisions and Answers reworded,
  and a new optional Voice item (rule key added to tiers/keys.json).
- README states the paid-plan assumption and what a free plan can't do;
  the install prompt has no placeholder to fill in.
- Install fixes from test 1: Python store stub, winget source and false
  "cancelled", PATH refresh, files without a byte-order mark, CLAUDE.md as
  the one line @AGENTS.md, launch routes proven by a live run, jobs run
  only while logged on.

## 0.9.6 (2026-09-30)

- MIT license (LICENSE), a written promise of what 1.x keeps stable
  (STABILITY.md), and SECURITY.md: what is stored in plain text, who can
  read it, and how to report a security problem.
- Unencrypted backups are now a recorded choice. The answers file takes
  backup.encrypted (true or false), required when a backup destination is
  set; false, or no answer on an older workspace, is a health-check warning
  and an amber backups card. To act: on an existing workspace, add
  "encrypted": true or false under "backup" in Setup/answers.json.
- The health check warns about unknown or renamed rule keys in the placed
  rules and each project's rules file, naming the fix. The known keys ship
  in tiers/keys.json.

## 0.9.5 (2026-09-30)

- Installs keep a journal: one line per step, started by the installing AI
  in your home folder and moved into Setup/install-journal.txt by the
  installer, which (like upgrade.py) adds its own steps.
- doctor.py --report writes a diagnostic bundle with a one-page summary
  marking every item PASS, WARN, FAIL or UNKNOWN. The feedback procedure
  files its summary as the bug report; the bundle stays on your computer.

## 0.9.4 (2026-09-30)

- Fixes from the first clean-machine install test. A fresh install no
  longer holds its own files back as .fieldbook-new copies, and the health
  check no longer turns red once the workspace is in use.
- The time zone is now always the computer's own: setup shows it to
  confirm, and if it is wrong you change it in the computer's settings.
- Project names can be typed freely ("Raised Bed Garden"); folders use a
  safe short form and the dashboard shows the name as typed.
- Scheduled jobs no longer pause waiting for input. Choosing no backups is
  a warning shown once, and a backup folder on the same disk is allowed,
  with its tradeoff named. upgrade.py takes --dry-run like install.py, and
  the health check warns about a byte-order mark in the rule files.

## 0.9.3 (2026-09-30)

- Added this changelog. Every new version now needs an entry here before
  it can be released; the release check refuses a version without one.

## 0.9.2 (2026-09-30)

- Start from any AI, even a chat in your browser. The AI now proves it can
  reach your own disk (a browser chat runs commands on a computer of its
  own), and if it can't, it walks you step by step into a tool that can,
  then hands you the prompt to paste there.

## 0.9.1 (2026-09-29)

- Dashboard redesigned: five tiles across the top, work items by state
  (Ready for launcher, Blocked, Needs decisions, Attended session, On hold),
  stacked bars and a grid of scheduled tasks.
- Six dashboard looks, picked during setup: light, dark or match the
  computer, each plain or colorful.
- Setup asks who you are, so the first session already knows.
- Closing a session settles the waiting-on-you list first.
- The tour explains how the rules are layered and how to stay current, and
  asks for questions after every stop.

## 0.9.0 (2026-09-29)

- The install is an interview the AI runs, top-down: purpose, working
  style, then the machinery.
- Rules in three layers (account, workspace, project).
- A dashboard tab per project, a restore drill for backups, a health check
  (doctor), a bridge reader, a close commit and an upgrade path.

## 0.1.0 (2026-09-03)

- First release: memory, work items, the agent bridge, quarantine and
  backups as an installable starter set.
- 2026-09-26: one shared helper module for all scripts; fixes so a fresh
  clone keeps its empty folders and passes its own test.
