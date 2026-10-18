---
name: showcase
description: Showcase a code change for people who did not write it, as a self-contained HTML report plus PR-ready Markdown covering what changed, why, the decisions taken, annotated key diffs, and evidence (before/after screenshots, command output, test results). Use when asked to showcase, demo or walk through a change, branch, commit range or PR, or to show it before and after.
---

# Showcase

A showcase answers four questions for a **reader** who did not write the change: what does it do, why was it made, what was decided, and how can I see it myself. The reader is the developer who had an agent write the code, a reviewer, or anyone opening the PR. The PR's file view already holds the full diff; the showcase holds what the diff cannot say.

Output goes to `.showcase/reports/<id>/` at the repo root, where `<id>` is `pr-<number>`, else the head's short SHA, else `wip`. The directory ignores itself in git.

- `showcase.html`: one self-contained file with every image embedded. It reaches a PR as an attachment dragged into a comment on the web page (GitHub accepts `.html` up to 25 MB; `gh` cannot upload it).
- `pr.md`: the same content without images, for the PR body or a comment.

Language: the one the user asks for or their standing instructions set; otherwise the language of the repo's PR descriptions, then its docs. Set `lang`: `en` and `zh-Hant` have labels, anything else gets English labels.

## 1. Pin the range

- A commit or range the user names: take it as given (`<commit>^` to `<commit>` for a single commit; `^` is the first parent, also for a merge).
- A PR: its base branch and head commit, from `gh pr view <number> --json baseRefName,headRefOid`; `base` is the merge-base of the two.
- A branch or the current work: `base` is `git merge-base HEAD origin/<default-branch>`; `head` is `HEAD`, or `null` for uncommitted work in the working tree.

Done when `git diff --stat <base> [<head>]` lists exactly the change to showcase. When the range carries unrelated commits, ask which part to showcase.

## 2. Gather the why

Read every source that can state intent: the conversation that produced the change, the PR description, issues, tickets or specs referenced from commit messages, the branch name or the PR, the commit messages themselves, and ADRs or design docs the change touches or cites. Keep the list of sources you used. A ticket or doc that covers more than this range informs the why; the report still describes only the range.

A claim backed by a source is **stated**. Anything reconstructed from the code is **inferred** and carries that mark. When no source gives the motivation, `why.sources` stays empty and the report shows the why as awaiting the author: readers act on the why, so a visible gap serves them better than a plausible guess.

Done when every sentence in the why and in each decision is either stated with its source or marked inferred.

## 3. Collect evidence

Classify the change by what a reader could observe. A change can be several kinds; the main effect a reader would look for gets the strongest evidence, and secondary effects may stop lower or go to `unverified`.

| Kind | Evidence |
|---|---|
| Visible UI | screenshots of every affected screen and state, base and head |
| Behaviour (CLI, API, library output, data processing) | the same input through base and head, outputs side by side |
| Performance | the same benchmark on base and head |
| Fix or new logic with tests | the new or changed tests run on base (failing) and head (passing) |
| Refactor meant to keep behaviour | each side's own test suite green, public interface unchanged |
| Docs, config or dependencies only | the narrative and diff are the evidence |

Climb the **evidence ladder** as high as the change calls for:

1. `before-after`: base and head both exercised the same way (same screens, inputs, commands or test files). A test that fails or does not compile on base and passes on head counts.
2. `after`: head only.
3. `tests`: test or command output from one side.
4. `static`: nothing run.

Below `before-after`, `why_not_higher` names the concrete obstacle, such as "the screen needs a signed-in account". Readers weigh the whole report by that line.

Before running anything, read [references/running.md](references/running.md): the repo's recipe, discovery, separate checkouts, proving each side runs its own code, capturing, and cleanup. Inputs are fake data; real accounts and live services come in only when the change itself is about them.

Scrub everything you save: tokens, cookies, keys, personal names and emails, account data and home-directory paths. An attached report is public on a public repo.

Save evidence files in the report directory and reference them by relative path.

Done when each kind the change belongs to has evidence or a `why_not_higher` naming it, and running.md's provenance and cleanup checks hold.

## 4. Write the narrative

Write for a reader who has not opened the code.

- `summary`: in 1 to 3 sentences, what changes for someone using the software. Effects, not implementation.
- `how`: the approach in plain words, naming the main moving parts.
- `decisions`: each choice a reviewer could question, with why, the alternatives considered, and stated or inferred.
- `files`: a note for every changed file. A glob key gives one note to a group, such as generated code, lockfiles or a mechanical rename.
- `hunks`: the few hunks that carry the change, each with a note on what it does and why. Narrow each with `match` to the lines that matter.
- `try_it`: steps a reviewer follows from a fresh checkout, with fake data, to see the change.
- `unverified`: what you did not check, such as platforms, flows and edge cases.

Done when a reader can answer "what, why, and how do I see it" from the summary, the why and `try_it` alone.

## 5. Render

Write `report.json` in the report directory, in the format of [references/report-schema.md](references/report-schema.md), then run with Python 3.9 or later:

```
python <this skill's directory>/scripts/showcase.py .showcase/reports/<id>/report.json
```

The renderer reads every diff from git itself. It rejects a changed file without a note, a note matching no changed file, a hunk selector matching nothing, a missing evidence file, and a level below `before-after` without a reason. Fix the report until it exits 0, and act on each warning.

Then screenshot the rendered page in a browser and look at it as the reader would. Browsers often refuse `file://` under automation; serve the report directory with `python -m http.server` on a free local port and stop it afterwards.

Done when you have seen the page and each piece of evidence shows its difference at display size, and each diff shows the lines its note describes. With no way to view a page, say so in the hand-over.

## 6. Hand over

Give the user both file paths and three lines: the evidence level reached, what is unverified, and anything awaiting the author. Mention that `.showcase/` now sits untracked in the repo: the reports ignore themselves, and a new or changed `recipe.md` is the developer's to commit. Post to the PR (`gh pr edit --body-file pr.md` or `gh pr comment --body-file pr.md`) when the user asks for it; attaching `showcase.html` is the drag-and-drop on the PR page.
