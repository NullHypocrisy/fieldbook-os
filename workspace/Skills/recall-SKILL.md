---
name: recall
description: Search memory for past decisions, facts or history, when the user asks about the past or a session needs history the files it read at start do not hold.
triggers:
  - "what did we decide about"
  - "when did we"
  - "do you remember"
  - "search memory"
---

# Recall Skill

1. **Search the index:**
   `python Memory/engine/search.py "query terms" [--tenant NAME]`.
   Try the user's wording first, then synonyms — the index is keyword
   search, so vocabulary matters.

2. **Open the cited source** for any hit you rely on. The snippet locates
   the fact; the file is the fact. Quote the file, with its date.

3. **Answer with citations** — file, heading, date — so the answer can be
   traced. A dated log entry claims truth as of its date; say so when the
   fact may have moved since.

4. **No hits means "not found in memory," said plainly.** Never fill the
   gap with a guess dressed as a memory.
