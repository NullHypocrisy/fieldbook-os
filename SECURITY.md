# Security

Fieldbook OS is plain files on your own computer. This page says what that
means for your data, so you can decide how to protect it.

## What is stored in plain text

Everything. Nothing in the kit is encrypted:

- **Memory:** working-memory notes, day logs and your profile.
- **The search index** over everything ever written (`Memory/index/`).
- **Work items, project files, messages between projects.**
- **Keys** in `.env` files, if you add any.
- **Backups:** full copies of the workspace, `.env` files included.

## Who can read it

- Anyone, or any program, that can read your user account's files or the
  disk they sit on. That includes a lost or stolen computer whose disk is
  not encrypted.
- Anyone who can read your backup destination, and the company behind it
  if it is a cloud folder.
- Your AI service: whatever a session reads is sent to it as part of the
  conversation, under that service's own terms.

## What the kit does

- Keeps `.env` files out of git and out of the search index.
- Never shows a key's value: `doctor.py --report` writes key names only and
  replaces any value it finds with `<redacted>`.
- `sanitize.py` checks a folder for secrets and personal details before you
  share it, and the bug-report procedure runs it before anything is filed.
- Asks at setup whether your backup destination is encrypted and records
  the answer. If you choose unencrypted backups, `doctor.py` warns and the
  dashboard marks the backups card, as a standing reminder of that choice.

## What it does not do

- Encrypt anything, at rest or in backups.
- Control who can open the files. That is your operating system's job.
- Protect against malware, or against someone using your computer while
  you are signed in.

The strongest protection is yours to set up: an encrypted disk for the
workspace (BitLocker or Device Encryption on Windows, FileVault on macOS)
and an encrypted backup destination.

## Reporting a security problem

Open an issue at https://github.com/NullHypocrisy/fieldbook-os/issues
titled "security contact" and put no details in it. The maintainer will
reply with a private way to send them.
