"""Ticket landing pipeline for ticket-coordinator (Python stdlib only).

Subcommands and standard usage:
  1. preflight — Verify main repo branch, clean tracked tree, and remote sync state:
       python3 scripts/land_ticket.py preflight --repo <repo> [--base main] [--json]
     Output:
       HEAD <branch> <sha> <subject>
       WARN <reason>            (any WARN exits 1)
       INFO <note>              (informational, exits 0 when no WARN)
       READY

  2. merge — Validate ticket commits, optional local ticket file, required files,
     dry-run conflict check (`git merge --no-commit --no-ff` with automatic
     `git merge --abort` on conflict), and commit `--no-ff` merge:
       python3 scripts/land_ticket.py merge --repo <repo> (--worktree <wt> | --branch <br>)
         [--base main] [--ticket <rel_path>] [--require <rel_path> ...]
         [--message "merge: ticket NN slug"] [--json]
     Validation rules:
       - Commit subjects in <base>..<branch>: exempts `Merge ` and `Revert "` prefixes;
         all other commits must match Conventional Commits (`<= 72` chars, lowercase
         start after `: `, no trailing period `.`).
       - Local ticket file (when `--ticket` is provided; omit for GitHub Issue mode):
         requires `Status: done` and zero unchecked `- [ ]` items outside fenced code
         blocks (``` / ~~~) and before `## Comments`.
       - Main repo must be on `--base` with clean tracked files; `--worktree` (if given)
         must have a clean working tree.
     Output & exit codes:
       - Exit 0: `MERGED <sha> <message>`
       - Exit 1: `NOT READY: <reason>` (one line per unmet requirement; repo untouched)
       - Exit 3: `CONFLICT: <files>` (merge automatically aborted; main repo stays clean)

  3. push-ci — Single-lock push (`.git/push-ci.lock` with stale-PID recovery) and bounded
     GitHub Actions check:
       python3 scripts/land_ticket.py push-ci --repo <repo> [--branch main]
         [--workflow <ci.yml|none>] [--poll 15] [--max-retries 3]
         [--no-run-checks 3] [--json]
     Behavior:
       - No `origin` remote: degrades cleanly (`remote=none ci=skipped reason=no_origin`, exit 0).
       - Acquires `<git-common-dir>/push-ci.lock` atomically; reclaims lock immediately
         when recorded PID is no longer alive, and always releases lock on exit.
       - Every `gh` query retries transient failures up to `--max-retries` consecutive
         attempts before releasing the lock and exiting 1.
       - After `git push`, if `--no-run-checks` polls find no workflow run for HEAD SHA
         and commit `check-runs` are empty or all skipped/neutral/success (e.g. workflow
         `paths-ignore`), exits 0 with `ci=skipped reason=no_workflow_run sha=<sha7>`.
     Output & exit codes:
       - Exit 0: `ci=success run=<id> sha=<sha7>`, `ci=skipped ...`, `ci=none ...`, or `remote=none ...`
       - Exit 1: `ci=<failure_conclusion> ...` or `ERROR: <reason>`

  4. cleanup — Release settled Orca worker, remove Orca worktree, prune, and delete
     merged ticket & `backup/*` branches:
       python3 scripts/land_ticket.py cleanup --repo <repo> [--worktree <wt>]
         [--dispatch <dispatch_id>] [--branch <br>] [--base main] [--orca <bin>]
         [--poll 1.0] [--poll-attempts 12] [--json]
     Output & exit codes:
       - Exit 0: `CLEANED ...` (verifies exit code 0 and JSON `ok == true` on every
         Orca CLI call)
       - Exit 1: `ERROR: <reason>`

  5. land — Run `preflight` -> `merge` -> `push-ci` -> `cleanup` sequentially, stopping
     immediately on the first non-zero stage:
       python3 scripts/land_ticket.py land --repo <repo> --worktree <wt>
         --message "merge: ticket NN slug" [--base main] [--ticket <rel_path>]
         [--require <rel_path> ...] [--workflow <ci.yml|none>] [--dispatch <id>]
         [--orca <bin>] [--skip-push] [--poll 15] [--max-retries 3] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)\r\n]+\))?!?: [^A-Z\s].*$"
)
STATUS_DONE_RE = re.compile(r"^\s*\*{0,2}Status:?\*{0,2}:?\s*done(?:\s|$)", re.IGNORECASE)
UNCHECKED_BOX_RE = re.compile(r"^\s*[-*+]\s+\[\s\]")
COMMENTS_HEADING_RE = re.compile(r"^\s*##\s+Comments(?:\s|$)", re.IGNORECASE)
BACKTICK_FENCE_OPEN_RE = re.compile(r"^\s*(`{3,})([^`]*)$")
TILDE_FENCE_OPEN_RE = re.compile(r"^\s*(~{3,})(.*)$")


class LandError(Exception):
    """Raised when an external CLI (`gh`, `git`, `orca`) fails fatally."""


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def resolve_orca_bin(explicit: str | None = None) -> str:
    """Resolve the Orca CLI executable following the official orchestration contract."""
    if explicit:
        return explicit
    env_cmd = os.environ.get("ORCA_CLI_COMMAND", "").strip()
    if env_cmd:
        return env_cmd
    if os.environ.get("ORCA_DEV_REPO_ROOT", "").strip():
        return "orca-dev"
    if sys.platform.startswith("linux") and not os.environ.get("ORCA_TERMINAL_ID"):
        if shutil.which("orca-ide"):
            return "orca-ide"
    return "orca"


def has_remote(repo: Path, remote: str = "origin") -> bool:
    return _git(repo, ["remote", "get-url", remote]).returncode == 0


def is_merging(repo: Path) -> bool:
    return _git(repo, ["rev-parse", "-q", "--verify", "MERGE_HEAD"]).returncode == 0


def git_common_dir(repo: Path) -> Path:
    proc = _git(repo, ["rev-parse", "--git-common-dir"])
    if proc.returncode != 0:
        raise LandError(f"無法解析 git common dir：{proc.stderr.strip()}")
    raw = Path(proc.stdout.strip())
    return (repo / raw).resolve() if not raw.is_absolute() else raw.resolve()


def current_branch(repo: Path) -> str:
    proc = _git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    if proc.returncode != 0:
        raise LandError(f"無法讀取目前分支：{proc.stderr.strip()}")
    return proc.stdout.strip()


def validate_commit_subjects(commits: list[tuple[str, str]]) -> list[str]:
    """Validate (sha, subject) pairs against Conventional Commits rules."""
    errors: list[str] = []
    for sha, subject in commits:
        if subject.startswith("Merge ") or subject.startswith('Revert "'):
            continue
        if len(subject) > 72:
            errors.append(f"{sha} 標題 {len(subject)} 字元 > 72：{subject}")
        if subject.endswith("."):
            errors.append(f"{sha} 標題不可有結尾句號：{subject}")
        if not CONVENTIONAL_RE.match(subject):
            errors.append(f"{sha} 不符合 Conventional Commits 小寫格式：{subject}")
    return errors


def validate_ticket_markdown(text: str) -> list[str]:
    """Check `Status: done` and unchecked `- [ ]` outside fences and before `## Comments`."""
    errors: list[str] = []
    has_done_status = False
    unchecked = 0
    fence_char: str | None = None
    fence_len = 0
    in_comments = False

    for raw_line in text.splitlines():
        if fence_char is not None:
            close_re = re.compile(rf"^\s*{re.escape(fence_char)}{{{fence_len},}}\s*$")
            if close_re.match(raw_line):
                fence_char = None
                fence_len = 0
            continue

        m_bt = BACKTICK_FENCE_OPEN_RE.match(raw_line)
        if m_bt:
            fence_char = "`"
            fence_len = len(m_bt.group(1))
            continue
        m_tl = TILDE_FENCE_OPEN_RE.match(raw_line)
        if m_tl:
            fence_char = "~"
            fence_len = len(m_tl.group(1))
            continue

        if COMMENTS_HEADING_RE.match(raw_line):
            in_comments = True
            continue

        if not in_comments:
            if STATUS_DONE_RE.match(raw_line):
                has_done_status = True
            if UNCHECKED_BOX_RE.match(raw_line):
                unchecked += 1

    if not has_done_status:
        errors.append("票的 Status 不是 done")
    if unchecked > 0:
        errors.append(f"票上還有 {unchecked} 個未勾的驗收條件")
    return errors


def _parse_requires(cli_requires: list[str] | None) -> list[str]:
    items: list[str] = []
    for raw in cli_requires or []:
        for part in re.split(r"[\s,]+", raw.strip()):
            if part:
                items.append(part)
    env_req = os.environ.get("REQUIRE", "").strip()
    if env_req and not items:
        items.extend(p for p in env_req.split() if p)
    return list(dict.fromkeys(items))


def run_preflight(repo: Path, base: str = "main") -> dict[str, Any]:
    """Inspect main repo state without failing on missing `origin` remote."""
    warns: list[str] = []
    infos: list[str] = []

    branch = current_branch(repo)
    head_proc = _git(repo, ["log", "--oneline", "-1"])
    head_line = head_proc.stdout.strip() if head_proc.returncode == 0 else "(no commits)"

    if branch != base:
        warns.append(f"主目錄目前在 {branch}，不在預期的 {base}")
    if is_merging(repo):
        warns.append("主目錄處於未完成的 MERGE 狀態")

    if has_remote(repo, "origin"):
        fetch_proc = _git(repo, ["fetch", "-q", "origin"])
        if fetch_proc.returncode != 0:
            warns.append(f"git fetch origin 失敗：{fetch_proc.stderr.strip()}")
        elif _git(repo, ["rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{base}"]).returncode == 0:
            ahead = _git(repo, ["log", "--oneline", f"origin/{base}..{base}"]).stdout.strip()
            if ahead:
                warns.append(f"本機 {base} 有尚未 push 的 commit：\n{ahead}")
            behind = _git(repo, ["log", "--oneline", f"{base}..origin/{base}"]).stdout.strip()
            if behind:
                warns.append(f"origin/{base} 有本機尚未同步的 commit：\n{behind}")
        else:
            infos.append(f"origin 尚無 {base} 分支")
    else:
        infos.append("本地無 origin remote，略過遠端同步檢查")

    dirty = _git(repo, ["status", "--short", "--untracked-files=no"]).stdout.strip()
    if dirty:
        warns.append(f"主目錄有未提交的追蹤檔改動：\n{dirty}")

    all_status = _git(repo, ["status", "--short"]).stdout.splitlines()
    untracked = [ln for ln in all_status if ln.startswith("??")]
    if untracked:
        infos.append("未追蹤檔案：\n" + "\n".join(untracked))

    wt_list = _git(repo, ["worktree", "list"]).stdout.strip()
    return {
        "ok": len(warns) == 0,
        "branch": branch,
        "head": head_line,
        "warns": warns,
        "infos": infos,
        "worktrees": wt_list.splitlines() if wt_list else [],
    }


def run_merge(
    repo: Path,
    *,
    worktree: Path | None = None,
    branch: str | None = None,
    base: str = "main",
    ticket: str | None = None,
    requires: list[str] | None = None,
    message: str = "",
) -> tuple[int, dict[str, Any]]:
    """Validate ticket readiness, dry-run conflict check (auto-aborting on conflict), and merge."""
    bad: list[str] = []

    if worktree is not None:
        if not worktree.is_dir():
            return 1, {"ok": False, "status": "not_ready", "errors": [f"找不到 worktree 目錄：{worktree}"]}
        wt_status = _git(worktree, ["status", "--short"]).stdout.strip()
        if wt_status:
            preview = " ".join(wt_status.splitlines()[:5])
            bad.append(f"worktree 不乾淨：{preview}")
        if not branch:
            branch = current_branch(worktree)

    if not branch or branch == "HEAD":
        bad.append("無法解析票的分支名稱（請確認 worktree 在具名分支或傳入 --branch）")
        return 1, {"ok": False, "status": "not_ready", "errors": bad}

    log_proc = _git(repo, ["log", "--format=%h\t%s", f"{base}..{branch}"])
    if log_proc.returncode != 0:
        bad.append(f"無法讀取 {base}..{branch} 的 commit：{log_proc.stderr.strip()}")
        commits: list[tuple[str, str]] = []
    else:
        commits = []
        for ln in log_proc.stdout.splitlines():
            if not ln.strip():
                continue
            sha, _, subj = ln.partition("\t")
            commits.append((sha.strip(), subj))

    if not commits:
        bad.append(f"{branch} 相對 {base} 沒有新 commit")
    else:
        bad.extend(validate_commit_subjects(commits))

    if ticket:
        ticket_text: str | None = None
        if worktree is not None:
            tf = worktree / ticket
            if tf.is_file():
                ticket_text = tf.read_text(encoding="utf-8")
            else:
                bad.append(f"找不到票檔 {tf}")
        else:
            show_proc = _git(repo, ["show", f"{branch}:{ticket}"])
            if show_proc.returncode == 0:
                ticket_text = show_proc.stdout
            else:
                bad.append(f"分支 {branch} 找不到票檔 {ticket}")
        if ticket_text is not None:
            bad.extend(validate_ticket_markdown(ticket_text))

    for req_file in _parse_requires(requires):
        diff_proc = _git(repo, ["diff", "--name-only", f"{base}...{branch}", "--", req_file])
        if diff_proc.returncode != 0 or not diff_proc.stdout.strip():
            bad.append(f"{branch} 沒有改到 {req_file}（專案完成標準要求）")

    if current_branch(repo) != base:
        bad.append(f"主目錄不在 {base} 上")
    if is_merging(repo):
        bad.append("主目錄處於未完成的 MERGE 狀態")
    dirty_main = _git(repo, ["status", "--short", "--untracked-files=no"]).stdout.strip()
    if dirty_main:
        bad.append("主目錄有未提交的追蹤檔改動，請先跑 preflight 查清")

    if bad:
        return 1, {"ok": False, "status": "not_ready", "errors": bad}

    merge_msg = message.strip() or f"merge: branch {branch}"
    dry = _git(repo, ["merge", "--no-commit", "--no-ff", branch])
    if dry.returncode != 0:
        unmerged_proc = _git(repo, ["diff", "--name-only", "--diff-filter=U"])
        conflicts = [ln.strip() for ln in unmerged_proc.stdout.splitlines() if ln.strip()]
        if is_merging(repo):
            _git(repo, ["merge", "--abort"])
        detail = conflicts if conflicts else [ln.strip() for ln in (dry.stderr or dry.stdout).splitlines() if ln.strip()]
        return 3, {
            "ok": False,
            "status": "conflict",
            "branch": branch,
            "conflicts": conflicts,
            "detail": detail,
        }

    try:
        commit_proc = _git(repo, ["commit", "-m", merge_msg])
        if commit_proc.returncode != 0:
            if is_merging(repo):
                _git(repo, ["merge", "--abort"])
            return 1, {
                "ok": False,
                "status": "commit_failed",
                "errors": [commit_proc.stderr.strip() or commit_proc.stdout.strip() or "git commit failed"],
            }
    except Exception:
        if is_merging(repo):
            _git(repo, ["merge", "--abort"])
        raise

    sha = _git(repo, ["rev-parse", "--short", "HEAD"]).stdout.strip()
    return 0, {
        "ok": True,
        "status": "merged",
        "branch": branch,
        "commit_count": len(commits),
        "sha": sha,
        "message": merge_msg,
    }


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _acquire_push_lock(lock_dir: Path, poll: float) -> None:
    pid_file = lock_dir / "pid"
    incomplete_grace = min(2.0, max(0.05, poll * 2))
    while True:
        try:
            os.mkdir(lock_dir)
            pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
            return
        except FileExistsError:
            holder_pid: int | None = None
            try:
                raw = pid_file.read_text(encoding="utf-8").strip()
                if raw:
                    holder_pid = int(raw)
            except (OSError, ValueError):
                holder_pid = None

            if holder_pid is not None:
                if not _is_pid_alive(holder_pid):
                    shutil.rmtree(lock_dir, ignore_errors=True)
                    continue
            else:
                try:
                    age = time.time() - lock_dir.stat().st_mtime
                except OSError:
                    continue
                if age > incomplete_grace:
                    shutil.rmtree(lock_dir, ignore_errors=True)
                    continue

            time.sleep(poll)


def _release_push_lock(lock_dir: Path) -> None:
    pid_file = lock_dir / "pid"
    try:
        if pid_file.is_file():
            raw = pid_file.read_text(encoding="utf-8").strip()
            if raw and int(raw) != os.getpid():
                return
    except (OSError, ValueError):
        pass
    shutil.rmtree(lock_dir, ignore_errors=True)


def _gh_json(
    repo: Path,
    args: list[str],
    *,
    max_retries: int,
    retry_delay: float,
    default_empty: Any,
) -> Any:
    """Call `gh` with bounded retries; raises LandError after `max_retries` consecutive failures."""
    attempts = max(1, max_retries)
    last_err = ""
    for attempt in range(1, attempts + 1):
        try:
            proc = _run(["gh", *args], cwd=repo)
        except FileNotFoundError as exc:
            raise LandError(f"找不到 gh 執行檔：{exc}") from exc

        if proc.returncode == 0:
            raw = proc.stdout.strip()
            if not raw:
                return default_empty
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                last_err = f"gh 回傳非合法 JSON（{exc}）：{raw[:200]}"
        else:
            last_err = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"

        if attempt < attempts:
            time.sleep(retry_delay)

    raise LandError(f"gh {' '.join(args[:3])} 連續失敗 {attempts} 次：{last_err}")


def run_push_ci(
    repo: Path,
    *,
    branch: str = "main",
    workflow: str | None = None,
    poll: float = 15.0,
    max_retries: int = 3,
    no_run_checks: int = 3,
) -> tuple[int, dict[str, Any]]:
    """Serialize push via `.git/push-ci.lock` and wait for GitHub Actions with bounded retries."""
    if not has_remote(repo, "origin"):
        return 0, {"ok": True, "remote": "none", "ci": "skipped", "reason": "no_origin"}

    lock_dir = git_common_dir(repo) / "push-ci.lock"
    retry_delay = min(poll, 2.0) if poll > 0 else 0.0
    _acquire_push_lock(lock_dir, max(0.01, poll))
    try:
        skip_ci = workflow is not None and workflow.lower() == "none"

        if not skip_ci:
            while True:
                runs = _gh_json(
                    repo,
                    ["run", "list", "--branch", branch, "--limit", "20", "--json", "status,workflowName,headSha,databaseId"],
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    default_empty=[],
                )
                in_progress = [
                    r for r in (runs if isinstance(runs, list) else [])
                    if isinstance(r, dict) and r.get("status") != "completed"
                ]
                if not in_progress:
                    break
                time.sleep(poll)

        push_proc = _git(repo, ["push", "origin", branch])
        if push_proc.returncode != 0:
            err = push_proc.stderr.strip() or push_proc.stdout.strip() or "git push failed"
            return 1, {"ok": False, "ci": "push_failed", "error": err}

        sha = _git(repo, ["rev-parse", "HEAD"]).stdout.strip()
        sha7 = sha[:7]

        if skip_ci:
            return 0, {"ok": True, "remote": "origin", "ci": "none", "sha": sha7}

        wf_args = ["--workflow", workflow] if workflow else []
        run_id: Any = None
        checks_limit = max(1, no_run_checks)

        for check_idx in range(1, checks_limit + 1):
            commit_runs = _gh_json(
                repo,
                ["run", "list", *wf_args, "--commit", sha, "--limit", "5", "--json", "databaseId,status,conclusion"],
                max_retries=max_retries,
                retry_delay=retry_delay,
                default_empty=[],
            )
            if isinstance(commit_runs, list) and commit_runs:
                first = commit_runs[0]
                if isinstance(first, dict) and first.get("databaseId") is not None:
                    run_id = first["databaseId"]
                    break

            if check_idx < checks_limit:
                time.sleep(poll)
                continue

            # Final discovery pass: inspect commit check-runs to distinguish `paths-ignore` from pending/failing checks.
            while True:
                cr_payload = _gh_json(
                    repo,
                    ["api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs"],
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    default_empty={},
                )
                check_runs = cr_payload.get("check_runs", []) if isinstance(cr_payload, dict) else []
                if not check_runs:
                    return 0, {
                        "ok": True,
                        "remote": "origin",
                        "ci": "skipped",
                        "reason": "no_workflow_run",
                        "sha": sha7,
                    }
                active_crs = [c for c in check_runs if isinstance(c, dict) and c.get("status") != "completed"]
                if active_crs:
                    time.sleep(poll)
                    # Re-check if workflow run also registered in the meantime
                    recheck = _gh_json(
                        repo,
                        ["run", "list", *wf_args, "--commit", sha, "--limit", "5", "--json", "databaseId,status,conclusion"],
                        max_retries=max_retries,
                        retry_delay=retry_delay,
                        default_empty=[],
                    )
                    if isinstance(recheck, list) and recheck and isinstance(recheck[0], dict) and recheck[0].get("databaseId") is not None:
                        run_id = recheck[0]["databaseId"]
                        break
                    continue

                bad_crs = [
                    c for c in check_runs
                    if isinstance(c, dict) and c.get("conclusion") not in ("success", "skipped", "neutral")
                ]
                if bad_crs:
                    failed_jobs = [f"{c.get('name', '?')}: {c.get('conclusion', '?')}" for c in bad_crs]
                    return 1, {
                        "ok": False,
                        "remote": "origin",
                        "ci": "failure",
                        "sha": sha7,
                        "failed_jobs": failed_jobs,
                    }
                return 0, {
                    "ok": True,
                    "remote": "origin",
                    "ci": "skipped",
                    "reason": "checks_skipped_or_passed_without_workflow",
                    "sha": sha7,
                }

        while True:
            view = _gh_json(
                repo,
                ["run", "view", str(run_id), "--json", "status,conclusion,jobs"],
                max_retries=max_retries,
                retry_delay=retry_delay,
                default_empty={},
            )
            if not isinstance(view, dict):
                raise LandError(f"gh run view {run_id} 回傳格式異常：{view!r}")
            if view.get("status") == "completed":
                conclusion = str(view.get("conclusion") or "unknown")
                jobs = view.get("jobs") if isinstance(view.get("jobs"), list) else []
                failed_jobs = [
                    f"{j.get('name', '?')}: {j.get('conclusion', '?')}"
                    for j in jobs
                    if isinstance(j, dict) and j.get("conclusion") not in ("success", "skipped", None)
                ]
                ok = conclusion in ("success", "skipped")
                return (0 if ok else 1), {
                    "ok": ok,
                    "remote": "origin",
                    "ci": conclusion,
                    "run_id": run_id,
                    "sha": sha7,
                    "failed_jobs": failed_jobs,
                }
            time.sleep(poll)

    except LandError as exc:
        return 1, {"ok": False, "ci": "error", "error": str(exc)}
    finally:
        _release_push_lock(lock_dir)


def _call_orca_json(orca_bin: str, args: list[str], *, cwd: Path) -> dict[str, Any]:
    try:
        proc = _run([orca_bin, *args, "--json"], cwd=cwd)
    except FileNotFoundError as exc:
        raise LandError(f"找不到 Orca 執行檔 {orca_bin!r}：{exc}") from exc

    raw = proc.stdout.strip()
    parsed: dict[str, Any] | None = None
    if raw:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                parsed = obj
        except json.JSONDecodeError:
            parsed = None

    if proc.returncode != 0:
        detail = proc.stderr.strip() or raw or f"exit {proc.returncode}"
        raise LandError(f"{orca_bin} {' '.join(args)} 失敗（exit {proc.returncode}）：{detail}")
    if parsed is None or parsed.get("ok") is not True:
        raise LandError(f"{orca_bin} {' '.join(args)} 未回傳 ok=true：{raw or proc.stderr.strip()}")
    return parsed


def _worktree_still_registered(repo: Path, target_wt: Path) -> bool:
    target_resolved = target_wt.resolve()
    proc = _git(repo, ["worktree", "list", "--porcelain"])
    for ln in proc.stdout.splitlines():
        if ln.startswith("worktree "):
            listed = Path(ln[len("worktree "):].strip()).resolve()
            if listed == target_resolved:
                return True
    return False


def run_cleanup(
    repo: Path,
    *,
    worktree: Path | None = None,
    dispatch_id: str | None = None,
    branch: str | None = None,
    base: str = "main",
    orca_bin: str | None = None,
    poll: float = 1.0,
    poll_attempts: int = 12,
) -> tuple[int, dict[str, Any]]:
    """Release settled Orca worker, remove Orca worktree, prune, and delete merged branches."""
    resolved_orca = resolve_orca_bin(orca_bin)
    wt_resolved = worktree.resolve() if worktree is not None else None

    if branch is None and worktree is not None and worktree.is_dir():
        proc = _git(worktree, ["rev-parse", "--abbrev-ref", "HEAD"])
        if proc.returncode == 0:
            candidate = proc.stdout.strip()
            if candidate and candidate != "HEAD":
                branch = candidate

    try:
        if dispatch_id:
            _call_orca_json(
                resolved_orca,
                ["orchestration", "worker-release", "--dispatch", dispatch_id],
                cwd=repo,
            )

        if worktree is not None and wt_resolved is not None:
            _call_orca_json(
                resolved_orca,
                ["worktree", "rm", "--worktree", f"path:{worktree}", "--force", "--delete-branch"],
                cwd=repo,
            )
            attempts = max(1, poll_attempts)
            for idx in range(1, attempts + 1):
                _git(repo, ["worktree", "prune"])
                if not wt_resolved.exists() and not _worktree_still_registered(repo, wt_resolved):
                    break
                if idx == attempts:
                    return 1, {
                        "ok": False,
                        "error": f"worktree 仍未移除：{worktree}",
                    }
                time.sleep(poll)
        else:
            _git(repo, ["worktree", "prune"])
    except LandError as exc:
        return 1, {"ok": False, "error": str(exc)}

    deleted_branches: list[str] = []
    head_branch = current_branch(repo)

    if branch and branch not in (base, head_branch):
        if _git(repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"]).returncode == 0:
            del_proc = _git(repo, ["branch", "-d", branch])
            if del_proc.returncode == 0:
                deleted_branches.append(branch)

    refs_proc = _git(repo, ["for-each-ref", "--format=%(refname:short)", "refs/heads/backup/"])
    if refs_proc.returncode == 0:
        for b_ref in refs_proc.stdout.splitlines():
            b_name = b_ref.strip()
            if not b_name or b_name == head_branch:
                continue
            if _git(repo, ["merge-base", "--is-ancestor", f"refs/heads/{b_name}", "HEAD"]).returncode == 0:
                if _git(repo, ["branch", "-d", b_name]).returncode == 0:
                    deleted_branches.append(b_name)

    return 0, {
        "ok": True,
        "released_dispatch": dispatch_id,
        "removed_worktree": str(worktree) if worktree is not None else None,
        "deleted_branches": deleted_branches,
    }


def _emit(payload: dict[str, Any], *, as_json: bool, lines: list[str]) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for ln in lines:
            print(ln)


def _cmd_preflight(args: argparse.Namespace) -> int:
    res = run_preflight(Path(args.repo).resolve(), base=args.base)
    lines = [f"HEAD {res['branch']} {res['head']}"]
    lines.extend(f"WARN {w}" for w in res["warns"])
    lines.extend(f"INFO {i}" for i in res["infos"])
    if res["ok"]:
        lines.append("READY")
    _emit(res, as_json=args.json, lines=lines)
    return 0 if res["ok"] else 1


def _cmd_merge(args: argparse.Namespace) -> int:
    wt = Path(args.worktree).resolve() if args.worktree else None
    rc, res = run_merge(
        Path(args.repo).resolve(),
        worktree=wt,
        branch=args.branch,
        base=args.base,
        ticket=args.ticket,
        requires=args.require,
        message=args.message or "",
    )
    if rc == 0:
        lines = [f"MERGED {res['sha']} {res['message']}"]
    elif res.get("status") == "conflict":
        shown = ", ".join(res.get("conflicts") or res.get("detail") or ["unknown"])
        lines = [f"CONFLICT: {shown}"]
    else:
        lines = [f"NOT READY: {e}" for e in res.get("errors", [])]
    _emit(res, as_json=args.json, lines=lines)
    return rc


def _format_push_lines(res: dict[str, Any]) -> list[str]:
    if res.get("remote") == "none":
        return [f"remote=none ci=skipped reason={res.get('reason', 'no_origin')}"]
    if res.get("ci") == "none":
        return [f"ci=none sha={res.get('sha', '')}"]
    if res.get("ci") == "skipped":
        return [f"ci=skipped reason={res.get('reason', '')} sha={res.get('sha', '')}".strip()]
    if "error" in res:
        return [f"ERROR: {res['error']}"]
    lines = [f"ci={res.get('ci')} run={res.get('run_id', '')} sha={res.get('sha', '')}".strip()]
    for job in res.get("failed_jobs", []):
        lines.append(f"  {job}")
    return lines


def _cmd_push_ci(args: argparse.Namespace) -> int:
    rc, res = run_push_ci(
        Path(args.repo).resolve(),
        branch=args.branch,
        workflow=args.workflow,
        poll=args.poll,
        max_retries=args.max_retries,
        no_run_checks=args.no_run_checks,
    )
    _emit(res, as_json=args.json, lines=_format_push_lines(res))
    return rc


def _cmd_cleanup(args: argparse.Namespace) -> int:
    wt = Path(args.worktree).resolve() if args.worktree else None
    rc, res = run_cleanup(
        Path(args.repo).resolve(),
        worktree=wt,
        dispatch_id=args.dispatch,
        branch=args.branch,
        base=args.base,
        orca_bin=args.orca,
        poll=args.poll,
        poll_attempts=args.poll_attempts,
    )
    if rc == 0:
        deleted = ",".join(res.get("deleted_branches", [])) or "none"
        lines = [f"CLEANED dispatch={res.get('released_dispatch') or 'none'} deleted_branches={deleted}"]
    else:
        lines = [f"ERROR: {res.get('error', 'cleanup failed')}"]
    _emit(res, as_json=args.json, lines=lines)
    return rc


def _cmd_land(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    wt = Path(args.worktree).resolve() if args.worktree else None

    pre = run_preflight(repo, base=args.base)
    if not pre["ok"]:
        lines = [f"WARN {w}" for w in pre["warns"]]
        _emit({"ok": False, "stage": "preflight", "preflight": pre}, as_json=args.json, lines=lines)
        return 1

    m_rc, m_res = run_merge(
        repo,
        worktree=wt,
        branch=args.branch,
        base=args.base,
        ticket=args.ticket,
        requires=args.require,
        message=args.message or "",
    )
    if m_rc != 0:
        if m_res.get("status") == "conflict":
            shown = ", ".join(m_res.get("conflicts") or m_res.get("detail") or ["unknown"])
            lines = [f"CONFLICT: {shown}"]
        else:
            lines = [f"NOT READY: {e}" for e in m_res.get("errors", [])]
        _emit({"ok": False, "stage": "merge", "merge": m_res}, as_json=args.json, lines=lines)
        return m_rc

    merged_branch = m_res.get("branch") or args.branch

    if args.skip_push:
        p_res: dict[str, Any] = {"ok": True, "ci": "skipped", "reason": "skip_push"}
    else:
        p_rc, p_res = run_push_ci(
            repo,
            branch=args.base,
            workflow=args.workflow,
            poll=args.poll,
            max_retries=args.max_retries,
            no_run_checks=args.no_run_checks,
        )
        if p_rc != 0:
            _emit(
                {"ok": False, "stage": "push-ci", "merge": m_res, "push_ci": p_res},
                as_json=args.json,
                lines=_format_push_lines(p_res),
            )
            return p_rc

    c_rc, c_res = run_cleanup(
        repo,
        worktree=wt,
        dispatch_id=args.dispatch,
        branch=merged_branch,
        base=args.base,
        orca_bin=args.orca,
        poll=min(args.poll, 1.0),
        poll_attempts=args.poll_attempts,
    )
    if c_rc != 0:
        _emit(
            {"ok": False, "stage": "cleanup", "merge": m_res, "push_ci": p_res, "cleanup": c_res},
            as_json=args.json,
            lines=[f"ERROR: {c_res.get('error', 'cleanup failed')}"],
        )
        return c_rc

    summary = {
        "ok": True,
        "merge": m_res,
        "push_ci": p_res,
        "cleanup": c_res,
    }
    lines = [
        f"MERGED {m_res['sha']} {m_res['message']}",
        *_format_push_lines(p_res),
        f"CLEANED dispatch={c_res.get('released_dispatch') or 'none'} deleted_branches={','.join(c_res.get('deleted_branches', [])) or 'none'}",
    ]
    _emit(summary, as_json=args.json, lines=lines)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="land_ticket.py", description="Ticket landing tool for ticket-coordinator.")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_pre = sub.add_parser("preflight", help="Check main repo cleanliness and remote sync status.")
    p_pre.add_argument("--repo", required=True, help="Path to the main git checkout.")
    p_pre.add_argument("--base", default="main", help="Expected base branch (default: main).")
    p_pre.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_pre.set_defaults(func=_cmd_preflight)

    p_merge = sub.add_parser("merge", help="Validate ticket branch/file, preflight conflicts, and merge --no-ff.")
    p_merge.add_argument("--repo", required=True, help="Path to target checkout (main or train worktree).")
    p_merge.add_argument("--worktree", help="Path to ticket worktree.")
    p_merge.add_argument("--branch", help="Ticket branch name (inferred from --worktree when omitted).")
    p_merge.add_argument("--base", default="main", help="Target base branch (default: main).")
    p_merge.add_argument("--ticket", help="Ticket file path relative to repo root (omit for GitHub Issue mode).")
    p_merge.add_argument("--require", action="append", default=[], help="File path required to change on branch.")
    p_merge.add_argument("--message", default="", help="Merge commit message.")
    p_merge.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_merge.set_defaults(func=_cmd_merge)

    p_push = sub.add_parser("push-ci", help="Push under single-repo lock and wait for GitHub Actions.")
    p_push.add_argument("--repo", required=True, help="Path to the main git checkout.")
    p_push.add_argument("--branch", default="main", help="Branch to push (default: main).")
    p_push.add_argument("--workflow", default=None, help="Workflow filename or 'none' to skip CI.")
    p_push.add_argument("--poll", type=float, default=float(os.environ.get("PUSH_CI_POLL", "15")), help="Poll interval seconds.")
    p_push.add_argument("--max-retries", type=int, default=3, help="Max consecutive `gh` failures before aborting.")
    p_push.add_argument("--no-run-checks", type=int, default=3, help="Discovery polls before treating missing run as paths-ignore.")
    p_push.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_push.set_defaults(func=_cmd_push_ci)

    p_clean = sub.add_parser("cleanup", help="Release Orca worker, remove Orca worktree, and delete merged branches.")
    p_clean.add_argument("--repo", required=True, help="Path to the main git checkout.")
    p_clean.add_argument("--worktree", help="Path to ticket worktree to remove.")
    p_clean.add_argument("--dispatch", help="Orca Dispatch ID to release.")
    p_clean.add_argument("--branch", help="Ticket branch name (inferred from --worktree when omitted).")
    p_clean.add_argument("--base", default="main", help="Base branch to never delete (default: main).")
    p_clean.add_argument("--orca", help="Resolved Orca CLI executable.")
    p_clean.add_argument("--poll", type=float, default=1.0, help="Worktree removal poll interval seconds.")
    p_clean.add_argument("--poll-attempts", type=int, default=12, help="Max poll iterations for worktree directory removal.")
    p_clean.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_clean.set_defaults(func=_cmd_cleanup)

    p_land = sub.add_parser("land", help="Run preflight -> merge -> push-ci -> cleanup.")
    p_land.add_argument("--repo", required=True, help="Path to the main git checkout.")
    p_land.add_argument("--worktree", help="Path to ticket worktree.")
    p_land.add_argument("--branch", help="Ticket branch name (inferred from --worktree when omitted).")
    p_land.add_argument("--base", default="main", help="Target base branch (default: main).")
    p_land.add_argument("--ticket", help="Ticket file path relative to repo root (omit for GitHub Issue mode).")
    p_land.add_argument("--require", action="append", default=[], help="File path required to change on branch.")
    p_land.add_argument("--message", required=True, help="Merge commit message.")
    p_land.add_argument("--workflow", default=None, help="Workflow filename or 'none' to skip CI.")
    p_land.add_argument("--dispatch", help="Orca Dispatch ID to release.")
    p_land.add_argument("--orca", help="Resolved Orca CLI executable.")
    p_land.add_argument("--skip-push", action="store_true", help="Skip push-ci step.")
    p_land.add_argument("--poll", type=float, default=float(os.environ.get("PUSH_CI_POLL", "15")), help="Poll interval seconds.")
    p_land.add_argument("--max-retries", type=int, default=3, help="Max consecutive `gh` failures before aborting.")
    p_land.add_argument("--no-run-checks", type=int, default=3, help="Discovery polls before treating missing run as paths-ignore.")
    p_land.add_argument("--poll-attempts", type=int, default=12, help="Max poll iterations for worktree directory removal.")
    p_land.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_land.set_defaults(func=_cmd_land)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
