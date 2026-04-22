# Git Coupling Reference

How to embed the Linear issue ID in commits and PRs. Back to [SKILL.md](../SKILL.md).

**Non-rule:** Branch names are **not** touched. The issue ID goes in commit messages and the PR body only.

---

## Commit Message Template

```
<type>(<scope>): <subject>

<optional body — wrap at 72 chars>

Linear: ENG-###
```

### Examples

```
feat(auth): implement token-bucket rate limiter for /api/search

Adds per-user rate limiting using a Redis-backed token bucket.
Configurable via RATE_LIMIT_SEARCH_RPS env var (default: 10).

Linear: ENG-789
```

```
fix(sessions): correct race condition in refresh token handler

Linear: ENG-123
```

```
chore(deps): upgrade redis to v5

Linear: ENG-790
```

### Rules

- `Linear: ENG-###` goes at the **end** of the commit message, after the body, separated by a blank line.
- If the work spans multiple issues (rare), list them: `Linear: ENG-123, ENG-124`.
- Do not combine the Linear trailer with other trailers on the same line (`Co-authored-by:`, etc.) — keep each trailer on its own line.

---

## PR Body Template

```
## Summary
<1–3 sentence description of what this PR does>

## Changes
- <bullet 1>
- <bullet 2>

## Testing
- [ ] <manual test step>
- [ ] <automated test coverage>

---

Linear: ENG-###
```

The `Linear: ENG-###` line is the magic-word that triggers Linear's GitHub integration to attach the PR to the issue automatically.

---

## Appending to an Existing PR Template

Many repos have a `.github/pull_request_template.md`. **Do not rewrite or reorder it.** Instead, append or fill in the Linear field.

### If the template already has a field for it

Look for lines like:
```
Linear: 
Ticket: 
Issue: 
Tracker: 
Jira: 
```

Fill the existing field:
```
Linear: ENG-789
```

Do not add a second `Linear:` line at the bottom.

### If the template has no such field

Append at the very end, after all existing content, with a blank line separator:

```
[...existing template content...]

---

Linear: ENG-789
```

### Detection heuristic

```
# Before opening a PR, check for an existing template slot
grep -i "linear\|ticket\|issue\|tracker" .github/pull_request_template.md 2>/dev/null
# If a match is found → fill that line
# If no match → append
```

---

## Multi-Issue PRs

If a single PR closes multiple Linear issues (e.g., a parent + a sub-issue):

```
Linear: ENG-789, ENG-790
```

Or, if the template uses a list format, one per line:

```
Linear: ENG-789
Linear: ENG-790
```

---

## Backfilling Commits

If the user asks you to go back and add the issue ID to commits already on the branch (before the PR is open):

- Only do this if the user explicitly requests it.
- Use `git commit --amend` for the most recent commit, or `git rebase -i` for multiple commits.
- Never amend commits that have already been pushed and reviewed.

---

## What Linear's Auto-Linking Picks Up

Linear's GitHub integration parses PR bodies and commit messages for `ENG-###` patterns and for `Linear:` magic words. Either form works:

| Form | Recognized? |
| --- | --- |
| `Linear: ENG-123` | Yes — preferred form |
| `ENG-123` anywhere in body | Yes — looser match |
| Branch named `feat/ENG-123-foo` | Yes — but we don't enforce this |
| Only in a code comment | No |

Using `Linear: ENG-###` explicitly is more reliable than relying on the bare ID appearing somewhere in the body.
