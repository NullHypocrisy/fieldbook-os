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
the sanitizer and the user has read the final text and said yes. The
diagnostic bundle itself never leaves; only the issue text built from its
summary does. A chat export never goes into an issue.

## 1. Gather

From the workspace root:

    python Maintenance/doctor.py --report

It takes about a minute and ends with `REPORT: <bundle>/summary.md`; that
folder under `Temp/managed/` is the evidence (`Maintenance/README.md`
says what is in it). Then ask the user for **the problem** in their own
words: what they did, what happened, what they expected, and whether it
happens every time. Write it to `Temp/managed/feedback-problem.md`, with a
one-week line in `Temp/managed/manifest.md`.

## 2. Draft

    python Maintenance/doctor.py --issue <bundle> --problem Temp/managed/feedback-problem.md --out Temp/managed/feedback/report.md

Add a one-week manifest line for the report. The draft holds the problem,
the bundle's summary table and its not-passing details, trimmed from the
end to 6,000 characters so both filing routes take the same text. The
workspace and home paths, login name and machine name are already
replaced with `<workspace>`, `<home>`, `<user>` and `<machine>`. Read it
and replace anything else that identifies the user (their real name, a
project name they would rather keep private) the same way. Add nothing
from the bundle's other files unless the bug is in that exact text, and
then only the lines needed.

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

Give the user the link: opening it and pressing Submit (signed in to
GitHub) files the report. It carries the same sanitized text, so nothing
new is exposed.

## 5. Record

Note the issue link, or that the user submitted by hand, in today's day
log. The draft, problem, terms file and bundle expire from
`Temp/managed/` on their own.
