---
name: feedback
description: Report a bug in the Fieldbook OS kit to its public repository, sanitized, with the user's yes before anything is sent.
triggers:
  - "file a bug"
  - "report a bug"
  - "report a kit problem"
  - "send feedback on the kit"
---

# Feedback Procedure

The kit's repository is `https://github.com/NullHypocrisy/fieldbook-os`.
A report there is public. Nothing leaves this machine until it has passed
the sanitizer and the user has read the final text and said yes.

## 1. Gather

From the workspace root, collect:

- **Kit version:** line 1 of `VERSION`.
- **OS and Python:** `python -c "import platform; print(platform.platform(), platform.python_version())"`.
- **Health:** `python Maintenance/doctor.py`. Keep its full output; if the
  problem is in the smoke test, `python Maintenance/smoke_test.py` too.
- **The problem**, in the user's words: what they did, what happened, what
  they expected, and whether it happens every time.

## 2. Draft

Write the report to `Temp/managed/feedback/report.md`, and add one line to
`Temp/managed/manifest.md` giving it a one-week expiry. Shape:

    ## What happened
    ## What was expected
    ## Steps to reproduce
    ## Environment
    Kit version, OS, Python.
    ## Doctor output
    (fenced block)

Then make it anonymous. Replace, everywhere in the report:

- the workspace's full path with `<workspace>`;
- the home folder's full path with `<home>`;
- the user's login name, real name and any machine name with `<user>` or
  `<machine>`.

Leave out file contents from the workspace (memory, specs, logs) unless the
bug is in that exact text, and then only the lines needed.

## 3. Sanitize

`sanitize.py` sits in the kit folder the workspace was installed from,
beside `install.py`. If that folder is gone, clone the repository again.

Write the terms that must not leave to `Temp/managed/feedback-terms.txt`,
one per line, with its own one-week manifest line: the original workspace
path, the home folder path, the login name, the user's name and email, the
machine name, and anything else the user names. The terms file stays
outside the folder being scanned, or it would match itself. Then:

    python <kit>/sanitize.py Temp/managed/feedback --terms Temp/managed/feedback-terms.txt

Exit 0 is clean. On exit 1, fix every finding in the report and run it
again. Never file a report the sanitizer has not passed with exit 0.

## 4. Show, then file

Show the user the title and the full final body, and ask whether to file
it publicly. File only on a clear yes; on a no, stop and keep the draft.

**Route A, GitHub CLI.** If `gh auth status` exits 0:

    gh issue create --repo NullHypocrisy/fieldbook-os --title "TITLE" --body-file Temp/managed/feedback/report.md

Give the user the issue link `gh` prints.

**Route B, by hand.** Otherwise compose a prefilled new-issue link:

    python -c "import sys, urllib.parse as u; b = open(sys.argv[2], encoding='utf-8').read(); print('https://github.com/NullHypocrisy/fieldbook-os/issues/new?' + u.urlencode({'title': sys.argv[1], 'body': b}))" "TITLE" Temp/managed/feedback/report.md

If the link runs past about 6,000 characters, cut the doctor output in the
body to its WARN and FAIL lines and rebuild it; the sanitizer passes again
before the link is shown. Give the user the link: opening it and pressing
Submit (signed in to GitHub) files the report. The link carries the same
sanitized text, so nothing new is exposed.

## 5. Record

Note the issue link, or that the user submitted by hand, in today's day
log. The draft and terms file expire from `Temp/managed/` on their own.
