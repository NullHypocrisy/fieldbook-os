# Changelog

What changed in each version, newest first. One entry per version, short
on purpose; the commit history has the detail.

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
