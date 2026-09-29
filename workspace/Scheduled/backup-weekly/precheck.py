"""precheck.py - is a weekly backup due? One call, before any session reads
anything. Logic and output words: Scheduled/backup_task.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backup_task  # noqa: E402

sys.exit(backup_task.precheck("weekly"))
