"""Unit and integration tests for `skills/ticket-coordinator/scripts/land_ticket.py`."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/land_ticket.py"


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=True,
    )


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        env=merged_env,
        check=False,
        timeout=60,
    )


def write_executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class LandTicketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="land-ticket-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()

    def init_repo(self, *, with_remote: bool = True) -> tuple[Path, Path | None]:
        repo = self.tmp / "repo"
        git(self.tmp, "init", "-q", "-b", "main", str(repo))
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Tester")

        (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (repo / "docs").mkdir()
        (repo / "docs/progress.md").write_text("# Progress\n", encoding="utf-8")
        (repo / "issues").mkdir()
        (repo / "issues/01-demo.md").write_text(
            "# 01: Demo\n\nStatus: ready-for-agent\n\n- [ ] works\n",
            encoding="utf-8",
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "chore: initial commit")

        remote: Path | None = None
        if with_remote:
            remote = self.tmp / "remote.git"
            git(self.tmp, "init", "-q", "--bare", str(remote))
            git(repo, "remote", "add", "origin", str(remote))
            git(repo, "push", "-q", "-u", "origin", "main")
        return repo, remote

    def make_worktree(self, repo: Path, name: str = "t01") -> Path:
        wt = self.tmp / name
        git(repo, "worktree", "add", "-q", "-b", name, str(wt), "main")
        return wt

    def make_mock_orca(self, log_file: Path, *, ok: bool = True, exit_code: int = 0) -> Path:
        script = textwrap.dedent(
            f"""\
            #!{sys.executable}
            import json, pathlib, shutil, subprocess, sys

            args = sys.argv[1:]
            with open({str(log_file)!r}, "a", encoding="utf-8") as fh:
                fh.write(" ".join(args) + "\\n")

            if {exit_code} != 0:
                print(json.dumps({{"ok": False, "error": "forced_exit"}}))
                sys.exit({exit_code})

            if not {ok!r}:
                print(json.dumps({{"ok": False, "error": "not_ok"}}))
                sys.exit(0)

            if args[:2] == ["worktree", "rm"]:
                for idx, tok in enumerate(args):
                    if tok == "--worktree" and idx + 1 < len(args):
                        sel = args[idx + 1]
                        if sel.startswith("path:"):
                            wt_path = pathlib.Path(sel[len("path:"):])
                            if wt_path.exists():
                                shutil.rmtree(wt_path)
            print(json.dumps({{"ok": True, "result": {{}}}}))
            """
        )
        return write_executable(self.bin_dir / "mock-orca", script)

    def env_with_bin(self) -> dict[str, str]:
        return {"PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

    def test_full_land_merges_pushes_releases_and_cleans_merged_backups(self) -> None:
        repo, remote = self.init_repo(with_remote=True)
        assert remote is not None
        wt = self.make_worktree(repo, "t01")

        # Create an unmerged backup branch and a merged backup branch
        git(repo, "branch", "backup/unmerged-20261121", "main")
        unmerged_wt = self.make_worktree(repo, "tmp-unmerged")
        (unmerged_wt / "extra.txt").write_text("keep\n", encoding="utf-8")
        git(unmerged_wt, "add", "extra.txt")
        git(unmerged_wt, "commit", "-qm", "feat: unmerged backup commit")
        git(repo, "branch", "-f", "backup/unmerged-20261121", "tmp-unmerged")
        git(repo, "worktree", "remove", "--force", str(unmerged_wt))
        git(repo, "branch", "-D", "tmp-unmerged")

        (wt / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        (wt / "docs/progress.md").write_text("# Progress\n- done t01\n", encoding="utf-8")
        (wt / "issues/01-demo.md").write_text(
            "# 01: Demo\n\n**Status:** done\n\n- [x] works\n\n## Comments\nSession 紀錄：done\n",
            encoding="utf-8",
        )
        git(wt, "add", "-A")
        git(wt, "commit", "-qm", "feat: implement demo value")
        # Merged backup pointing to an ancestor of t01
        git(repo, "branch", "backup/t01-rewrite-20261121", "t01")

        gh_state = self.tmp / "gh_state.json"
        gh_state.write_text(json.dumps({"branch_calls": 0}), encoding="utf-8")
        write_executable(
            self.bin_dir / "gh",
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import json, sys

                args = sys.argv[1:]
                state_path = {str(gh_state)!r}
                state = json.loads(open(state_path, encoding="utf-8").read())

                if args[:2] == ["run", "list"] and "--branch" in args:
                    state["branch_calls"] += 1
                    open(state_path, "w", encoding="utf-8").write(json.dumps(state))
                    if state["branch_calls"] == 1:
                        print(json.dumps([{{"status": "in_progress", "workflowName": "test", "headSha": "1111111", "databaseId": 10}}]))
                    else:
                        print(json.dumps([]))
                elif args[:2] == ["run", "list"] and "--commit" in args:
                    print(json.dumps([{{"databaseId": 42, "status": "in_progress", "conclusion": None}}]))
                elif args[:2] == ["run", "view"]:
                    print(json.dumps({{"status": "completed", "conclusion": "success", "jobs": [{{"name": "test", "conclusion": "success"}}]}}))
                else:
                    print(json.dumps({{}}))
                """
            ),
        )
        orca_log = self.tmp / "orca.log"
        orca_bin = self.make_mock_orca(orca_log)

        res = run_cli(
            "land",
            "--repo", str(repo),
            "--worktree", str(wt),
            "--ticket", "issues/01-demo.md",
            "--require", "docs/progress.md",
            "--message", "merge: ticket 01 demo",
            "--workflow", "test.yml",
            "--dispatch", "ctx_01",
            "--orca", str(orca_bin),
            "--poll", "0.02",
            env=self.env_with_bin(),
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("MERGED", res.stdout)
        self.assertIn("ci=success run=42", res.stdout)
        self.assertIn("CLEANED dispatch=ctx_01", res.stdout)
        self.assertFalse((repo / ".git/push-ci.lock").exists())
        self.assertFalse(wt.exists())

        # Verify remote main received merge commit
        local_head = git(repo, "rev-parse", "main").stdout.strip()
        remote_head = git(remote, "rev-parse", "main").stdout.strip()
        self.assertEqual(local_head, remote_head)

        # Verify Orca call order: worker-release then worktree rm
        logged = orca_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(logged), 2)
        self.assertIn("orchestration worker-release --dispatch ctx_01 --json", logged[0])
        self.assertIn("worktree rm --worktree", logged[1])
        self.assertIn("--force --delete-branch --json", logged[1])

        # Merged ticket & backup branch deleted; unmerged backup preserved
        branches = git(repo, "branch", "--format=%(refname:short)").stdout.splitlines()
        self.assertNotIn("t01", branches)
        self.assertNotIn("backup/t01-rewrite-20261121", branches)
        self.assertIn("backup/unmerged-20261121", branches)

    def test_ticket_checkbox_skips_fenced_code_blocks_and_comments(self) -> None:
        repo, _ = self.init_repo(with_remote=False)
        wt = self.make_worktree(repo, "t02")

        (wt / "issues/01-demo.md").write_text(
            textwrap.dedent(
                """\
                # 01: Demo

                Status: done

                ## Acceptance
                - [x] Real requirement checked
                  ```markdown
                  - [ ] Example inside backtick fence
                  ```
                ~~~text
                - [ ] Example inside tilde fence
                ~~~

                ## Comments
                Session 紀錄：2026-11-21 finished
                - [ ] Deferred follow-up noted in comments
                """
            ),
            encoding="utf-8",
        )
        git(wt, "add", "issues/01-demo.md")
        git(wt, "commit", "-qm", "docs: mark ticket done with fenced examples")

        ok_res = run_cli(
            "merge",
            "--repo", str(repo),
            "--worktree", str(wt),
            "--ticket", "issues/01-demo.md",
            "--message", "merge: ticket 01 demo",
        )
        self.assertEqual(ok_res.returncode, 0, ok_res.stdout + ok_res.stderr)
        self.assertIn("MERGED", ok_res.stdout)

        # Real unchecked box before ## Comments must still block merge
        wt2 = self.make_worktree(repo, "t03")
        (wt2 / "issues/01-demo.md").write_text(
            "# 01: Demo\n\nStatus: done\n\n- [ ] Still unchecked\n\n## Comments\n",
            encoding="utf-8",
        )
        git(wt2, "add", "issues/01-demo.md")
        git(wt2, "commit", "-qm", "docs: incomplete checklist")
        bad_res = run_cli(
            "merge",
            "--repo", str(repo),
            "--worktree", str(wt2),
            "--ticket", "issues/01-demo.md",
            "--message", "merge: ticket 03",
        )
        self.assertEqual(bad_res.returncode, 1)
        self.assertIn("NOT READY:", bad_res.stdout)
        self.assertIn("1 個未勾的驗收條件", bad_res.stdout)

    def test_github_issue_mode_without_local_ticket_and_commit_subject_exemptions(self) -> None:
        repo, _ = self.init_repo(with_remote=False)
        wt = self.make_worktree(repo, "t-revert")

        (wt / "app.py").write_text("VALUE = 99\n", encoding="utf-8")
        git(wt, "add", "app.py")
        git(
            wt,
            "commit",
            "-qm",
            'Revert "feat: add a very long feature description that exceeds seventy-two characters easily."',
        )
        git(
            wt,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "Merge branch 'main' into a-ticket-branch-whose-merge-title-is-way-over-seventy-two-characters",
        )

        # Omit --ticket (GitHub Issue mode) -> passes!
        res = run_cli(
            "merge",
            "--repo", str(repo),
            "--worktree", str(wt),
            "--message", "merge: gh issue #12",
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("MERGED", res.stdout)

        # Trailing period and >72 non-exempt subject must fail
        wt_bad = self.make_worktree(repo, "t-bad-msg")
        (wt_bad / "app.py").write_text("VALUE = 100\n", encoding="utf-8")
        git(wt_bad, "add", "app.py")
        git(wt_bad, "commit", "-qm", "feat: add trailing period.")
        bad = run_cli("merge", "--repo", str(repo), "--worktree", str(wt_bad))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("結尾句號", bad.stdout)

    def test_merge_conflict_auto_aborts_and_leaves_main_clean(self) -> None:
        repo, _ = self.init_repo(with_remote=False)
        wt = self.make_worktree(repo, "t-conflict")

        (repo / "app.py").write_text("VALUE = 'main-edit'\n", encoding="utf-8")
        git(repo, "add", "app.py")
        git(repo, "commit", "-qm", "feat: update value on main")
        main_head_before = git(repo, "rev-parse", "HEAD").stdout.strip()

        (wt / "app.py").write_text("VALUE = 'branch-edit'\n", encoding="utf-8")
        git(wt, "add", "app.py")
        git(wt, "commit", "-qm", "feat: update value on branch")

        res = run_cli(
            "merge",
            "--repo", str(repo),
            "--worktree", str(wt),
            "--message", "merge: conflicting branch",
        )
        self.assertEqual(res.returncode, 3)
        self.assertIn("CONFLICT:", res.stdout)
        self.assertIn("app.py", res.stdout)

        # Main repo must NOT remain in MERGING state and must have clean working tree
        self.assertFalse((repo / ".git/MERGE_HEAD").exists())
        self.assertEqual(git(repo, "status", "--porcelain").stdout.strip(), "")
        self.assertEqual(git(repo, "rev-parse", "HEAD").stdout.strip(), main_head_before)

    def test_no_origin_remote_degrades_gracefully(self) -> None:
        repo, _ = self.init_repo(with_remote=False)

        pre = run_cli("preflight", "--repo", str(repo))
        self.assertEqual(pre.returncode, 0, pre.stdout + pre.stderr)
        self.assertIn("READY", pre.stdout)
        self.assertNotIn("fatal:", pre.stderr.lower())

        push = run_cli("push-ci", "--repo", str(repo))
        self.assertEqual(push.returncode, 0, push.stdout + push.stderr)
        self.assertIn("remote=none", push.stdout)
        self.assertNotIn("fatal:", push.stderr.lower())

    def test_gh_consecutive_failures_release_lock_and_exit_nonzero(self) -> None:
        repo, remote = self.init_repo(with_remote=True)
        assert remote is not None
        remote_before = git(remote, "rev-parse", "main").stdout.strip()

        (repo / "app.py").write_text("VALUE = 3\n", encoding="utf-8")
        git(repo, "add", "app.py")
        git(repo, "commit", "-qm", "feat: local change")

        gh_count = self.tmp / "gh_fail_count.txt"
        gh_count.write_text("0", encoding="utf-8")
        write_executable(
            self.bin_dir / "gh",
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import sys
                p = {str(gh_count)!r}
                n = int(open(p, encoding="utf-8").read()) + 1
                open(p, "w", encoding="utf-8").write(str(n))
                sys.stderr.write("HTTP 502 Bad Gateway\\n")
                sys.exit(1)
                """
            ),
        )

        res = run_cli(
            "push-ci",
            "--repo", str(repo),
            "--max-retries", "3",
            "--poll", "0.01",
            env=self.env_with_bin(),
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("連續失敗 3 次", res.stdout)
        self.assertEqual(int(gh_count.read_text(encoding="utf-8")), 3)
        self.assertFalse((repo / ".git/push-ci.lock").exists())
        # Must NOT have pushed when pre-push check failed
        self.assertEqual(git(remote, "rev-parse", "main").stdout.strip(), remote_before)

    def test_paths_ignore_empty_workflow_and_check_runs_passes(self) -> None:
        repo, remote = self.init_repo(with_remote=True)
        assert remote is not None
        (repo / "docs/progress.md").write_text("# Docs only\n", encoding="utf-8")
        git(repo, "add", "docs/progress.md")
        git(repo, "commit", "-qm", "docs: update progress only")

        write_executable(
            self.bin_dir / "gh",
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import json, sys
                args = sys.argv[1:]
                if args[:2] == ["run", "list"]:
                    print(json.dumps([]))
                elif args[:1] == ["api"]:
                    print(json.dumps({{"total_count": 0, "check_runs": []}}))
                else:
                    sys.exit(1)
                """
            ),
        )

        res = run_cli(
            "push-ci",
            "--repo", str(repo),
            "--workflow", "ci.yml",
            "--poll", "0.01",
            "--no-run-checks", "2",
            env=self.env_with_bin(),
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("ci=skipped", res.stdout)
        self.assertFalse((repo / ".git/push-ci.lock").exists())
        self.assertEqual(
            git(remote, "rev-parse", "main").stdout.strip(),
            git(repo, "rev-parse", "main").stdout.strip(),
        )

    def test_stale_pid_lock_reclaimed_and_live_pid_lock_waited(self) -> None:
        repo, _ = self.init_repo(with_remote=True)
        (repo / "app.py").write_text("VALUE = 5\n", encoding="utf-8")
        git(repo, "add", "app.py")
        git(repo, "commit", "-qm", "feat: test lock handling")

        write_executable(
            self.bin_dir / "gh",
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import json, sys
                args = sys.argv[1:]
                if args[:2] == ["run", "list"] and "--branch" in args:
                    print(json.dumps([]))
                elif args[:2] == ["run", "list"] and "--commit" in args:
                    print(json.dumps([{{"databaseId": 9, "status": "completed", "conclusion": "success"}}]))
                elif args[:2] == ["run", "view"]:
                    print(json.dumps({{"status": "completed", "conclusion": "success", "jobs": []}}))
                """
            ),
        )

        # Spawn and finish a subprocess to obtain a guaranteed dead PID
        dead_proc = subprocess.Popen([sys.executable, "-c", "pass"])
        dead_proc.wait()
        lock_dir = repo / ".git/push-ci.lock"
        lock_dir.mkdir()
        (lock_dir / "pid").write_text(f"{dead_proc.pid}\n", encoding="utf-8")

        res_stale = run_cli("push-ci", "--repo", str(repo), "--poll", "0.02", env=self.env_with_bin())
        self.assertEqual(res_stale.returncode, 0, res_stale.stdout + res_stale.stderr)
        self.assertIn("ci=success", res_stale.stdout)
        self.assertFalse(lock_dir.exists())

        # Now test waiting for a live PID holder
        (repo / "app.py").write_text("VALUE = 6\n", encoding="utf-8")
        git(repo, "add", "app.py")
        git(repo, "commit", "-qm", "feat: second push behind live lock")

        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.25)"])
        # 背景收屍：未被 wait 的子行程會變 zombie，kill(pid, 0) 仍回成功，鎖就永遠看似有人持有
        reaper = threading.Thread(target=holder.wait, daemon=True)
        reaper.start()
        lock_dir.mkdir()
        (lock_dir / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")

        t0 = time.monotonic()
        res_live = run_cli("push-ci", "--repo", str(repo), "--poll", "0.03", env=self.env_with_bin())
        elapsed = time.monotonic() - t0
        reaper.join(timeout=5)

        self.assertEqual(res_live.returncode, 0, res_live.stdout + res_live.stderr)
        self.assertGreaterEqual(elapsed, 0.12)
        self.assertFalse(lock_dir.exists())

    def test_cleanup_fails_when_orca_returns_ok_false(self) -> None:
        repo, _ = self.init_repo(with_remote=False)
        wt = self.make_worktree(repo, "t-fail-orca")
        orca_log = self.tmp / "orca_fail.log"
        bad_orca = self.make_mock_orca(orca_log, ok=False, exit_code=0)

        res = run_cli(
            "cleanup",
            "--repo", str(repo),
            "--worktree", str(wt),
            "--dispatch", "ctx_bad",
            "--orca", str(bad_orca),
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("ok=true", res.stdout)
        # Worktree and branch remain untouched when worker-release fails
        self.assertTrue(wt.exists())


if __name__ == "__main__":
    unittest.main()
