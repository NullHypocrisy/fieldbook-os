---
name: remember
description: Store, update or delete a fact in working memory, or clean memory up, when the user asks for it.
triggers:
  - "remember this"
  - "note that"
  - "forget about"
  - "clean up memory"
---

# Remember Skill

1. **Route.** Decide which tenant owns the fact (Memory/tenants.json is the
   registry): a project fact to that project's working memory, everything
   else to global. Facts about the user's stable identity or working style
   go to the core profile instead.

2. **Apply the admission test** from AGENTS.md before writing anything.
   Most of what a session produces belongs in the day log, not working
   memory; a fact whose truth already has a home updates the home.

3. **Read the whole target file first.** If the fact is already there in
   any wording, update that line rather than adding a near-duplicate.
   Treat the file as configuration under maintenance, not a journal that
   accumulates.

4. **Write surgically.** Add or replace single lines. Replacing or removing
   a line an earlier session wrote goes through
   `python Memory/engine/evict.py <file> "exact line"`, which records it in
   the day log first and refuses anything it cannot read back.

5. **Respect the cap** (tenants.json). At or near cap, do not trim
   arbitrarily: re-home the lines that have homes elsewhere, consolidate
   real duplicates, and only then judge what remains. Tell the user what
   moved where.
