# Running base and head

Read this before running anything for evidence. Each section ends on what must hold before you trust the result.

## Recipe

`.showcase/recipe.md` at the repo root is what earlier runs learned about running this repo. Read it first and follow it; it is a cache of discovery, so the repo wins when they disagree.

After a run, write or update it with what the next run needs whatever the change is: which of several commands works, how to start each surface and know it is ready, where fake data and fake sign-ins live, how to prove provenance, every trap that cost you time, and how long slow steps take. Point at files instead of copying their contents, credentials included. A trick that served only this change stays in this report. Fix any line that turned out wrong, and end with `Last verified: <short SHA> <date>`.

```markdown
# Running this repo for a showcase

## Web UI
- Start: `<command>` (from `<dir>`), ready when `<log line or URL responds>`.
- Data: `<fixture/seed/fake server>`, scenario `<name>` for `<state>`.
- Sign-in: fake account defined in `<file>`.
- Provenance: `<how to confirm the running code is this checkout>`.
- Gotchas: `<trap and fix>`.

Last verified: a1b2c3d 2026-01-31
```

The recipe lives in the repo so every developer and agent shares it. Tell the user it is new or changed; committing it is their call.

## Discovery

Without a recipe, look where the repo already records how it runs, roughly cheapest first: agent instructions and project skills, README and CONTRIBUTING and development docs, CI workflows (CI proves those commands work), package scripts and task runners, e2e and Storybook configs, container files, fixtures, seeds, mocks and fake servers. Repos with e2e tests usually ship a fake backend or seed data; the e2e config shows how to start it and the specs show how to reach each state.

## Run directory

Make one fresh directory per run, outside the repo: inside your session's scratch or temp area when you have one, else from `mktemp -d`. Everything temporary for this run goes in it: worktrees, helper scripts, logs, raw captures. Parallel runs then never collide, and cleanup is one place.

On Windows under a POSIX shell, programs that are not the shell (node, python, browsers) need native paths: convert with `cygpath -m`.

## Checkouts

Run every side that is not exactly the current working tree from its own checkout: `git worktree add --detach <run-dir>/<side> <rev>`. The developer's working tree, branch and stash stay untouched.

A new worktree has no installed dependencies or build output. Install them with the repo's own command (a lockfile install is usually quick). If you link a dependency directory instead, remove the link before removing the worktree, so removal never follows it into the original.

## Provenance

Before trusting any output, prove each side runs its own checkout's code. Editable installs, global builds, a shared virtualenv, a cached bundle or a server already holding the port all make a "base" run silently execute head's code, or the reverse. Check something that differs between the two: the module path the process imported, the build directory a server serves, a version string, or a string the change itself edits.

Done when each side shows a marker that could only come from its own checkout.

## Processes

Start each long-lived process (server, watcher, emulator) so it outlives a single tool call: your tool's background mode, or a detached start. Record the PID of the process that actually serves, not a wrapper: package-runner shims and shell wrappers hide it, so start the program directly or resolve the PID from the port it listens on. Stop processes by those PIDs. Stopping by program name kills the user's unrelated processes.

## Same conditions

Base and head get the same input data, viewport, locale, theme and clock, with animations settled and network idle. Then every difference in the evidence comes from the change.

## Reaching a state

Drive the app to each state the change affects. The repo's e2e helpers already know how to sign in, seed and click through, so borrow them before scripting your own steps. A state that takes minutes to reach (a scheduler tick, a long job) is worth one run; plan the captures so you pass through it once.

Fake credentials committed for development or tests may be typed into the local app. They stay out of the report and the recipe, like any secret.

## Capturing

- **Screenshots** frame the changed region: an element screenshot, or a clip rectangle with enough surroundings to find it on the page. Add a full-page shot only when position on the page is the point. A reader must see the difference at the report's display width.
- Capture both sides with the same clip rectangle, so the pair lines up in the slider even when the change alters the element's height.
- JPEG or WebP keeps the HTML small.
- **Text output** keeps the lines that show the result: the summary line, the assertion, the changed value. Cut logging noise, marking each cut with `…`.
- **Tests as evidence**: a new or changed test run on both sides is before-after evidence. Copy head's test files into the base checkout; failing there (or not compiling) and passing on head shows what the change adds. For a refactor, the base's own suite passing on base and head's passing on head shows behaviour kept.
- **A reproduction you write** for a change that brought no test: keep it in the run directory, run it on both sides, and add its source to the report as an `output` item without a `command`, captioned as written for this showcase and not part of the change.

## Cleanup

Stop every PID you recorded, then remove every worktree you added (`git worktree remove`, then `git worktree prune`). Installs and codegen often dirty your own temporary worktree; `--force` is fine there and only there. Then remove the run directory.

Done when `git worktree list` and `git status` match what you found, and no PID you recorded is alive.
