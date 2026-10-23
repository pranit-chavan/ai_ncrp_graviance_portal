# Repository workflow

- Keep changes focused and review the diff before committing.
- After completing a requested code or documentation change, commit it and push it to the current branch on the configured GitHub repository. The project owner has requested this as the default workflow.
- Use descriptive commits. Never force-push, rewrite published history, or reset away prior work. Use a follow-up commit or `git revert` to undo a published change.
- Do not commit API keys, `.env` files, databases, uploaded evidence, generated case records, investigator inbox contents, local logs, or personal information. Check `git status` and staged file names before every commit.
- Do not include real victim or complainant information in examples, tests, screenshots, or documentation. Use fictional data.
