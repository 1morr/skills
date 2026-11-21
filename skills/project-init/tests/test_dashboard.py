"""dashboard.py（收編進共用骨架套件）的測試：共用單一 Parser、粗體 Blocked by、佇列接棒與 worktrees 短效快取。

    python3 -m unittest discover -s skills/project-init/tests
"""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ROADMAP = """# 路線圖

## 里程碑

| 里程碑 | 目標 | 拆票前讀 | 狀態 |
| --- | --- | --- | --- |
| M0 骨架 | 閘門就位 | brief | 已驗收（2026-01-02），封存在 [`docs/archive/M0.md`](archive/M0.md) |
| M1 核心 | 第一個功能 | `ARCHITECTURE.md` | 進行中，已拆 3 張票 |
| M2 介面 | 畫面 | brief §4 | 未開工 |
"""
SPEC = """# M1

## 目標

打出第一個字。

## 範圍（做 / 不做）

### 做

- 查碼表
- 候選列

### 不做

- 學習

## 共同規則

## 驗收

## 票序
"""
TICKET = "# 01: 查碼表\n\nStatus: ready-for-agent\nBlocked by: None\n\n## What to build\n\n## 驗收\n\n- [x] 查得到\n- [ ] 全部檢查綠燈。\n\n## Comments\n"
DECISIONS = """# 決策紀錄

## 紀錄

- 2026-01-02 M0（使用者定）：用 Rust 寫核心。細節在 ADR 0001。
- 2026-01-05 M1 票 01（Agent 定）：碼表用 `fst` 存。
- 2026-01-04 M1(使用者同意)：候選列一頁九個。
"""
PROGRESS = """# 進度

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-01-04 | M1 開工 | 拆了 3 張票 | 新 session 下 `/implement .scratch/m1/issues/01-lookup.md` |
| 2026-01-05 | M1 01 | 查碼表做完 a\\|b | 新 session 下 `/implement .scratch/m1/issues/02-bar.md` |
"""


class Repo(unittest.TestCase):
    def setUp(self):
        m.clear_worktree_cache()
        self.root = Path(tempfile.mkdtemp(prefix="dashboard-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.repo = self.root / "demo"
        self.write("AGENTS.md", "# Demo\n\n示範。\n")
        self.write("docs/roadmap.md", ROADMAP)
        self.write("docs/decisions.md", DECISIONS)
        self.write("docs/progress.md", PROGRESS)
        self.write("docs/adr/0001-rust-core.md", "# 核心用 Rust\n")
        self.write(".scratch/m1/spec.md", SPEC)
        self.write(".scratch/m1/issues/01-lookup.md", TICKET)
        self.write(".scratch/m1/issues/02-bar.md", TICKET.replace("01: 查碼表", "02: 候選列").replace("[x]", "[ ]"))
        self.write(".scratch/m1/issues/03-m1-acceptance.md", "# 03: M1 驗收\n\n**Status:** ready-for-agent\n")

    def write(self, rel, text, base=None):
        p = (base or self.repo) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def sub(self, rel, old, new):
        text = (self.repo / rel).read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new))

    def collect(self, ttl=0):
        return m.collect(self.repo, worktree_ttl=ttl)


class CollectTest(Repo):
    def test_milestones_decisions_and_progress(self):
        d = self.collect()
        self.assertEqual(d["title"], "Demo")
        self.assertEqual([(x["name"], x["state"], x["dir"]) for x in d["milestones"]],
                         [("M0 骨架", "done", "m0"), ("M1 核心", "active", "m1"), ("M2 介面", "todo", "m2")])
        self.assertEqual([(x["date"], x["milestone"], x["decider"]) for x in d["decisions"]],
                         [("2026-01-05", "M1", "Agent 定"), ("2026-01-04", "M1", "使用者同意"), ("2026-01-02", "M0", "使用者定")])

    def test_bold_blocked_by_is_honored_by_dashboard(self):
        """修復原 dashboard.py:77 漏認粗體 `**Blocked by:**` 的 Bug。"""
        self.sub(".scratch/m1/issues/01-lookup.md", "Blocked by: None", "**Blocked by:** 02")
        self.sub(".scratch/m1/issues/03-m1-acceptance.md", "ready-for-agent\n", "ready-for-agent\n**Blocked by:** 01, 02\n")
        d = self.collect()
        self.assertEqual(d["milestones"][1]["tickets"][0]["blocked"], ["02"])
        self.assertEqual(d["next_ticket"]["file"], "02-bar.md")
        self.assertEqual(d["next"], "新 session 下 `/implement .scratch/m1/issues/02-bar.md`")

    def test_switches_to_queued_milestone_when_none_is_active(self):
        """修復原 dashboard.py:230 無進行中里程碑時漏切 `排在 <已結束> 之後` 佇列的分叉。"""
        self.sub("docs/roadmap.md", "| M1 核心 | 第一個功能 | `ARCHITECTURE.md` | 進行中，已拆 3 張票 |",
                 "| M1 核心 | 第一個功能 | `ARCHITECTURE.md` | 已驗收 |\n| docs-diet 瘦身 | 文件 | — | 未開工，排在 M1 之後 |")
        self.write(".scratch/docs-diet/issues/01-trim.md", TICKET.replace("01: 查碼表", "01: 瘦身"))
        d = self.collect()
        self.assertEqual(d["next_ticket"]["command"], "/implement .scratch/docs-diet/issues/01-trim.md")
        self.assertEqual(d["next"], "新 session 下 `/implement .scratch/docs-diet/issues/01-trim.md`")

    def test_archived_sessions_and_decisions_use_clean_format(self):
        table = "| 日期 | 票 | 結果 | 下一步 |\n| --- | --- | --- | --- |\n| 2025-12-01 | M0 01 | 做完 a\\|b | x |\n"
        self.write("docs/archive/m0.md", "## Session 紀錄\n\n" + table + "\n## 決定\n\n- 2025-12-01 M0（使用者定）：定案。\n")
        d = self.collect()
        self.assertEqual(d["unreadable"], [])
        self.assertEqual(d["archived_sessions"][0]["milestone"], "M0")
        self.assertTrue(any(x["archived"] and x["milestone"] == "M0" for x in d["decisions"]))

    def test_changelog_and_features(self):
        self.write("CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- **候選列**：一頁九個。\n")
        self.sub(".scratch/m1/issues/02-bar.md", "## Comments\n", "## Comments\n\n變更：Changed | 候選列 | 改成五個。\n")
        d = self.collect()
        self.assertEqual([(e["kind"], e["pending"]) for e in d["changelog"][0]["entries"]], [("Added", ""), ("Changed", "M1 02")])
        self.assertEqual(d["features"][0]["name"], "候選列")


@unittest.skipUnless(shutil.which("git"), "要 git")
class WorktreeCacheTest(Repo):
    def git(self, cwd, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        subprocess.run(["git", "-C", str(cwd), "-c", "core.hooksPath=/dev/null", *args], env=env, check=True, capture_output=True)

    def setUp(self):
        super().setUp()
        self.git(self.repo, "init", "-q", "-b", "main")
        self.git(self.repo, "add", "-A")
        self.git(self.repo, "commit", "-qm", "docs: scaffold")
        self.work = self.root / "t01"
        self.git(self.repo, "worktree", "add", "-q", "-b", "t01", str(self.work))

    def test_worktrees_detects_active_work_and_uses_short_ttl_cache(self):
        t = self.work / ".scratch/m1/issues/01-lookup.md"
        t.write_text(t.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        first = self.collect(ttl=2.5)["working"]
        self.assertEqual([(w["worktree"], w["checked"]) for w in first], [("t01", 2)])

        # 2.5 秒 TTL 內第二次呼叫：命中記憶體快取，0 次 git 子行程呼叫！
        with mock.patch.object(m, "_git", side_effect=AssertionError("should hit worktree cache")):
            second = self.collect(ttl=2.5)["working"]
        self.assertEqual(second, first)

        # 清除快取後重新查詢最新狀態
        m.clear_worktree_cache()
        self.assertEqual(len(self.collect(ttl=2.5)["working"]), 1)


class PageAndServeTest(Repo):
    def test_page_loads_nothing_external_and_manual_dark_mode(self):
        self.sub("docs/decisions.md", "用 Rust 寫核心。", "用 Rust 寫核心。</script><b>")
        page = m.render(m.data([self.repo]))
        self.assertNotRegex(page, r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""")
        self.assertNotIn("prefers-color-scheme", page)
        embedded = page.split('<script id="data" type="application/json">')[1].split("</script>")[0]
        self.assertEqual(json.loads(embedded)["projects"][0]["name"], "demo")

    def test_served_data_and_path_traversal_guard(self):
        httpd = m.server([self.repo], "127.0.0.1", 0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close(), thread.join(5)))
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        with urllib.request.urlopen(base + "/data.json", timeout=5) as r:
            payload = json.loads(r.read().decode("utf-8"))
        self.assertEqual(payload["projects"][0]["name"], "demo")
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/../etc/passwd", timeout=5)


if __name__ == "__main__":
    unittest.main()
