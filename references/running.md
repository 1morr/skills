# Running base and head

Read this before running anything for evidence. Each section ends on what must hold before you trust the result.

## Recipe

`.showcase/recipe.md` at the repo root is what an earlier run learned about running this repo. Read it first and follow it; it is a cache of discovery, so the repo wins when they disagree.

After a run, write or update it: what you ran, where the fake data came from, how you checked provenance, and every gotcha that cost you time. The repo's own files already say what they say, so the recipe holds what they do not: which of several commands is the one that works, the trap you hit, how long a slow step takes. Fix any line that turned out wrong. End it with `Last verified: <short SHA> <date>`.

```markdown
# Running this repo for a showcase

## Web UI
- Start: `<command>` (from `<dir>`), ready when `<log line or URL responds>`.
- Data: `<fixture/seed/fake server>`, scenario `<name>` for `<state>`.
- Sign-in: fake account from `<file>`.
- Provenance: `<how to confirm the running code is this checkout>`.
- Gotchas: `<trap and fix>`.

Last verified: a1b2c3d 2026-01-31
```

The recipe lives in the repo so every developer and agent shares it. Tell the user it is new or changed; committing it is their call.

## Discovery

Without a recipe, look where the repo already records how it runs, roughly cheapest first: agent instructions and project skills, README and CONTRIBUTING and development docs, CI workflows (CI proves those commands work), package scripts and task runners, e2e and Storybook configs, container files, fixtures, seeds, mocks and fake servers. Repos with e2e tests usually ship a fake backend or seed data; the e2e config shows how to start it and the specs show how to reach each state.

## Checkouts

Run every side that is not exactly the current working tree from its own checkout: `git worktree add --detach <dir> <rev>`. `<dir>` is a fresh directory outside the repo, made inside your session's scratch or temp area when you have one, else by `mktemp -d`, so parallel runs never collide. The developer's working tree, branch and stash stay untouched.

A new worktree has no installed dependencies or build output. Install them with the repo's own command (a lockfile install is usually quick). If you link a dependency directory instead, remove the link before `git worktree remove`, so removal never follows it into the original.

## Provenance

Before trusting any output, prove each side runs its own checkout's code. Editable installs, global builds, a shared virtualenv, a cached bundle or a server already holding the port all make a "base" run silently execute head's code, or the reverse. Check something that differs between the two: the module path the process imported, the build directory a server serves, a version string, or a string the change itself edits.

Done when each side shows a marker that could only come from its own checkout.

## Same conditions

Base and head get the same input data, viewport, locale, theme and clock, with animations settled and network idle. Then every difference in the evidence comes from the change.

## Reaching a state

Drive the app to each state the change affects. The repo's e2e helpers already know how to sign in, seed and click through, so borrow them before scripting your own steps. A state that takes minutes to reach (a scheduler tick, a long job) is worth one run; plan the captures so you pass through it once.

Fake credentials committed for development or tests may be typed into the local app. They stay out of the report, like any secret.

## Capturing

- **Screenshots** frame the changed region: an element screenshot, or a crop with enough surroundings to find it on the page. Add a full-page shot only when position on the page is the point. A reader must see the difference at the report's display width.
- Same framing, size and scroll position on both sides, so the slider lines up.
- JPEG or WebP keeps the HTML small.
- **Text output** keeps the lines that show the result: the summary line, the assertion, the changed value. Cut logging noise.
- **Tests as evidence**: a new or changed test run on both sides is before-after evidence. Copy head's test files into the base checkout; failing there (or not compiling) and passing on head shows what the change adds. For a refactor, the base's own suite passing on base and head's passing on head shows behaviour kept.

## Cleanup

Stop exactly the processes you started: record each PID (or the port it bound) when you start it and stop by that. Stopping by program name kills the user's unrelated processes. Then remove every worktree you added (`git worktree remove`, then `git worktree prune`). Installs and codegen often dirty your own temporary worktree; `--force` is fine there and only there.

Done when `git worktree list` and `git status` match what you found, and nothing you started is still running.
