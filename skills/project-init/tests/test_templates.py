"""範本與 Day-0 工程護欄測試：instructions.md 瘦身指標、無 Python 純 POSIX commit-msg / pre-commit hooks、ci.yml 與種子對齊。

    python3 -m unittest discover -s skills/project-init/tests
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL / "templates"
PLACEHOLDERS = {"PROJECT": "Demo", "ONE_LINE": "示範專案。", "DATE": "2026-01-02", "MAIN_BRANCH": "main"}


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check_docs = load("check_docs")
scaffold = load("scaffold")


def fill(name: str) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: PLACEHOLDERS[m.group(1)], text)


def no_python_env(base_env: dict | None = None) -> dict:
    """構造不含 python/python3 的純系統工具環境，證明 POSIX sh hooks 零 Python 依賴。"""
    bin_dir = Path(tempfile.mkdtemp(prefix="posix-only-bin-"))
    for tool in ("sh", "git", "sed", "grep", "wc", "printf", "tr"):
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)
    env = dict(base_env or os.environ)
    for k in [n for n in env if n.startswith("GIT_")]:
        del env[k]
    env["PATH"] = str(bin_dir)
    env["_TMP_BIN_DIR"] = str(bin_dir)
    return env


class PlaceholderAndSizeTest(unittest.TestCase):
    def test_every_placeholder_is_known(self):
        for p in sorted(TEMPLATES.iterdir()):
            for name in re.findall(r"\{\{(\w+)\}\}", p.read_text(encoding="utf-8")):
                self.assertIn(name, PLACEHOLDERS, f"{p.name} 用了未知佔位 {{{{{name}}}}}")

    def test_instructions_template_stays_within_45_lines_and_2500_chars(self):
        raw = (TEMPLATES / "instructions.md").read_text(encoding="utf-8")
        filled = fill("instructions.md")
        lines = raw.rstrip("\n").split("\n")
        self.assertLessEqual(len(lines), 45, f"instructions.md 行數 {len(lines)} > 45")
        self.assertLessEqual(len(raw), 2500, f"instructions.md 字元數 {len(raw)} > 2500")
        self.assertLessEqual(len(filled), 2500)
        for needle in ("檔案:行", "文件與程式對不上", "docs/development.md", "docs/agents/milestone.md", "docs/agents/ticket-template.md"):
            self.assertIn(needle, filled)

    def test_commit_msg_hook_is_8_lines_posix_sh(self):
        lines = (TEMPLATES / "commit-msg").read_text(encoding="utf-8").rstrip("\n").split("\n")
        self.assertEqual(lines[0], "#!/bin/sh")
        self.assertEqual(len(lines), 8, f"commit-msg 應為 8 行純 POSIX sh，目前 {len(lines)} 行")
        self.assertNotIn("python", "\n".join(lines).lower())

    def test_ci_yml_has_permissions_timeout_and_branch_protected_concurrency(self):
        ci = (TEMPLATES / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", ci)
        self.assertIn("timeout-minutes: 15", ci)
        self.assertIn("cancel-in-progress: ${{ github.ref != 'refs/heads/{{MAIN_BRANCH}}' }}", ci)

    def test_gitignore_and_development_guardrails(self):
        gi = (TEMPLATES / "gitignore").read_text(encoding="utf-8")
        for pat in (".env", "!.env.example", "*.pem", "*.key", "__pycache__/", "node_modules/", ".DS_Store", ".scratch/"):
            self.assertIn(pat, gi)
        dev = (TEMPLATES / "development.md").read_text(encoding="utf-8")
        self.assertIn("雙 checkout", dev)
        self.assertIn("獨有標記", dev)


@unittest.skipUnless(shutil.which("git") and shutil.which("sh"), "要 git 和 sh")
class PosixHooksTest(unittest.TestCase):
    """在無 Python 的 PATH 環境下實跑 commit-msg 與 pre-commit hooks。"""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="posix-hooks-")).resolve()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.env = no_python_env()
        self.addCleanup(shutil.rmtree, self.env["_TMP_BIN_DIR"], ignore_errors=True)
        self.env.update({
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        })
        scaffold.scaffold(self.repo, PLACEHOLDERS)
        self.git("init", "-q", "-b", "main")
        self.git("config", "core.hooksPath", ".githooks")

    def git(self, *args, check=True):
        return subprocess.run(["git", "-C", str(self.repo), *args], env=self.env, capture_output=True, text=True, check=check)

    def check_msg_file(self, text: str) -> subprocess.CompletedProcess:
        msg = self.repo / ".git" / "TEST_MSG"
        msg.write_text(text, encoding="utf-8")
        return subprocess.run(["/bin/sh", str(self.repo / ".githooks/commit-msg"), str(msg)],
                              cwd=self.repo, env=self.env, capture_output=True, text=True)

    def test_commit_msg_accepts_valid_and_exempt_messages_without_python(self):
        for good in (
            "feat: add search\n",
            "fix(parser)!: handle bold blocked-by\n",
            "docs: 說明安裝步驟\n",
            "# comment line\n\nchore: bump deps\n",
            "feat: " + "a" * 66 + "\n",
            "Merge branch 'very-long-branch-name-" + "x" * 70 + "'\n",
            'Revert "feat: add search"\n',
        ):
            with self.subTest(good=good.strip()):
                r = self.check_msg_file(good)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_commit_msg_rejects_bad_subjects_without_python(self):
        for bad in (
            "Add search\n",
            "feature: wrong type\n",
            "feat: Capitalised subject\n",
            "feat: trailing period.\n",
            "feat: " + "a" * 67 + "\n",
            "merge: ticket 01 outside merge\n",
            "\n",
        ):
            with self.subTest(bad=bad.strip()):
                r = self.check_msg_file(bad)
                self.assertNotEqual(r.returncode, 0)

    def test_pre_commit_and_merge_head_work_in_real_git_workflow(self):
        # 1. 乾淨的 12 檔骨架可直接 commit（包含 .githooks/pre-commit 自身不自爆）
        self.git("add", "-A")
        self.git("commit", "-qm", "docs: scaffold guardrails")

        # 2. 攔截衝突標記 <<<<<<<
        (self.repo / "conflict.txt").write_text("normal\n<<<<<<< HEAD\ntheirs\n", encoding="utf-8")
        self.git("add", "conflict.txt")
        r = self.git("commit", "-qm", "fix: bad conflict", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("conflict", r.stderr)
        self.git("rm", "-fq", "conflict.txt")

        # 3. 攔截私鑰標頭
        for header in ("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN OPENSSH PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----"):
            with self.subTest(header=header):
                (self.repo / "secret.txt").write_text(f"{header}\nabc\n", encoding="utf-8")
                self.git("add", "secret.txt")
                r = self.git("commit", "-qm", "chore: leak key", check=False)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("private key", r.stderr)
                self.git("rm", "-fq", "secret.txt")

        # 4. 攔截 >2MB 大檔案
        (self.repo / "huge.bin").write_bytes(b"x" * (2 * 1024 * 1024 + 10))
        self.git("add", "huge.bin")
        r = self.git("commit", "-qm", "chore: huge file", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("2MB", r.stderr)
        self.git("rm", "-fq", "huge.bin")

        # 5. MERGE_HEAD 存在時放行 `merge: ticket 01 gates`
        self.git("checkout", "-q", "-b", "t01")
        (self.repo / "ok.txt").write_text("ok\n", encoding="utf-8")
        self.git("add", "ok.txt")
        self.git("commit", "-qm", "feat: add ok")
        self.git("checkout", "-q", "main")
        r = self.git("merge", "--no-ff", "-m", "merge: ticket 01 ok", "t01", check=False)
        self.assertEqual(r.returncode, 0, r.stderr)


SEEDS = {"issue-tracker.md": "issue-tracker-local.md", "triage-labels.md": "triage-labels.md", "domain.md": "domain.md"}
CONVENTIONS = re.compile(r"(^## Conventions[ \t]*\n)(.*?)(?=^## )", re.S | re.M)
PUBLISH = ("`.scratch/<feature-slug>/` (creating", "`.scratch/<milestone>/issues/` (creating")


def outside_conventions(text: str) -> str:
    return CONVENTIONS.sub(lambda m: m.group(1), text, count=1)


def installed_seed():
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    gemini = Path(os.environ.get("GEMINI_CONFIG_DIR") or Path.home() / ".gemini" / "config")
    candidates = (
        list(claude.glob("plugins/cache/*/mattpocock-skills/*/skills/*/setup-matt-pocock-skills"))
        + list(gemini.glob("plugins/mattpocock-skills/skills/*/setup-matt-pocock-skills"))
    )
    found = [d for d in candidates if all((d / s).is_file() for s in SEEDS.values())]
    return max(found, key=lambda d: d.stat().st_mtime) if found else None


class AgentDocsTest(unittest.TestCase):
    def test_issue_tracker_states_core_conventions(self):
        text = (TEMPLATES / "issue-tracker.md").read_text(encoding="utf-8")
        for needle in ("`.scratch/<milestone>/issues/<NN>-<slug>.md`", "`<NN>-<milestone>-acceptance.md`",
                       "`Status: done`", "`Blocked by:`", "`## Comments`", "1morr-skel"):
            self.assertIn(needle, text)

    @unittest.skipUnless(installed_seed(), "這台機器沒有裝 mattpocock-skills")
    def test_copies_match_the_installed_seed(self):
        seed = installed_seed()
        for ours, theirs in SEEDS.items():
            with self.subTest(ours):
                mine = (TEMPLATES / ours).read_text(encoding="utf-8")
                upstream = (seed / theirs).read_text(encoding="utf-8")
                if ours == "issue-tracker.md":
                    mine, upstream = outside_conventions(mine), outside_conventions(upstream.replace(*PUBLISH))
                self.assertEqual(mine, upstream)


if __name__ == "__main__":
    unittest.main()
