# Commit credit: what changed and what to check

For Abby and Theo, from Daniel, 15 Nov 2026.

## What changed

CLAUDE.md now has a section called "Who commits are credited to". It was pushed to `main` as commit `b463fb4` (T55). It sets two rules:

1. **You are the author.** The author of every commit is the person whose computer made it. Your git name and email go on the commit, not Claude's.
2. **Claude is a co-author.** Every commit message ends with a line `Co-Authored-By: Claude <noreply@anthropic.com>`. Claude Code adds it by default. Do not remove it.

The rule applies from T55 onwards. Commits made before 15 Nov do not have the Claude line, and we are not rewriting history to add it.

## What you need to do

**Step 1: check your git identity** on your own computer, in any terminal:

```
git config user.name
git config user.email
```

- The name should be your GitHub name.
- The email must be one listed as verified at github.com → Settings → Emails.

**Step 2: if either is wrong or empty, fix it once** on your computer:

```
git config --global user.name "Your Name"
git config --global user.email "your-verified-email@example.com"
```

This applies to every repo on your computer. Use your own details, not Daniel's.

**Step 3: check your first commit.** After your next commit (before or just after pushing), run:

```
git log -1 --format='Author: %an <%ae>%n%n%B'
```

You should see:
- `Author:` with your name and your verified email.
- The commit message, ending with the line `Co-Authored-By: Claude <noreply@anthropic.com>`.

If the Co-Authored-By line is missing, do not push. Tell Daniel first.

## Things to avoid

- Do not set Claude as the author or committer, and do not change anyone else's git settings.
- Do not remove the Co-Authored-By line from a commit message.
- Do not use `git commit --amend` or force-push to change a commit that is already on `main`.

## Where the rule is

- CLAUDE.md, section "Who commits are credited to" (under Git rules).
- `docs/decisions.md`, the dated line for 14 Nov 2026 (Daniel).
