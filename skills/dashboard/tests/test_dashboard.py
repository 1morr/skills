"""dashboard.py 的測試：讀得出固定文件裡的東西，文件一改資料就變，無關的格式改動不影響。

    python -m unittest discover -s skills/dashboard/tests
"""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ROADMAP = """# 路線圖

## 里程碑

| 里程碑 | 目標 | 拆票前讀 | 狀態 |
| --- | --- | --- | --- |
| M0 骨架 | 閘門就位 | brief | 2026-01-02 驗收，紀錄封存在 [`docs/archive/M0.md`](archive/M0.md) |
| M1 核心 | 第一個功能 | `ARCHITECTURE.md` | 進行中，已拆 3 張票 |
| M2 介面 | 畫面 | brief §4 | 未開工 |

## M2 介面

目標：畫面。
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

## 寫法

- 2026-01-01 這一行在〈寫法〉裡，不是決策。

## 紀錄

- 2026-01-02 M0（使用者定）：用 Rust 寫核心。細節在 ADR 0001。
- 2026-01-05 M1 票 01（Agent 定）：碼表用 `fst` 存。
- 2026-01-04 M1（使用者同意）：候選列一頁九個。
"""
PROGRESS = """# 進度

## 寫法與封存

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-01-04 | M1 開工 | 拆了 3 張票 | 新 session 下 `/implement .scratch/m1/issues/01-lookup.md` |
| 2026-01-05 | M1 01 | 查碼表做完 a\\|b | 新 session 下 `/implement .scratch/m1/issues/02-bar.md` |
"""


class Repo(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="dashboard-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.repo = self.root / "demo"
        self.write("AGENTS.md", "# Demo\n\n示範。\n")
        self.write("docs/roadmap.md", ROADMAP)
        self.write("docs/decisions.md", DECISIONS)
        self.write("docs/progress.md", PROGRESS)
        self.write("docs/adr/0001-rust-core.md", "# 核心用 Rust\n")
        self.write("docs/adr/template.md", "# 範本\n")
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

    def collect(self):
        return m.collect(self.repo)


class CollectTest(Repo):
    def test_milestones_and_ticket_progress(self):
        d = self.collect()
        self.assertEqual(d["title"], "Demo")
        self.assertEqual([(x["name"], x["state"], x["dir"]) for x in d["milestones"]],
                         [("M0 骨架", "done", "m0"), ("M1 核心", "active", "m1"), ("M2 介面", "todo", "m2")])
        m1 = d["milestones"][1]
        self.assertEqual([(t["title"], t["done"], t["checked"], t["boxes"]) for t in m1["tickets"]],
                         [("01: 查碼表", False, 1, 2), ("02: 候選列", False, 0, 2), ("03: M1 驗收", False, 0, 0)])
        self.assertEqual((m1["goal"], m1["detail"], m1["scope"]), ("第一個功能", "打出第一個字。", ["查碼表", "候選列"]))

    def test_finishing_a_ticket_changes_the_data(self):
        before = self.collect()
        self.sub(".scratch/m1/issues/01-lookup.md", "Status: ready-for-agent", "Status: done")
        self.sub(".scratch/m1/issues/01-lookup.md", "- [ ]", "- [x]")
        after = self.collect()
        self.assertNotEqual(before, after)
        self.assertEqual((after["milestones"][1]["tickets"][0]["done"], after["milestones"][1]["tickets"][0]["checked"]), (True, 2))

    def test_status_only_counts_before_the_first_section(self):
        self.sub(".scratch/m1/issues/01-lookup.md", "## Comments\n", "## Comments\n\nStatus: done\n")
        self.assertFalse(self.collect()["milestones"][1]["tickets"][0]["done"])

    def test_decisions_newest_first_with_decider_and_milestone(self):
        self.assertEqual([(d["date"], d["milestone"], d["decider"], d["text"]) for d in self.collect()["decisions"]],
                         [("2026-01-05", "M1", "Agent 定", "碼表用 fst 存。"),
                          ("2026-01-04", "M1", "使用者同意", "候選列一頁九個。"),
                          ("2026-01-02", "M0", "使用者定", "用 Rust 寫核心。細節在 ADR 0001。")])

    def test_decisions_moved_from_an_older_format_are_read_too(self):
        self.write("docs/decisions.md", DECISIONS + "\n## 搬移前的紀錄\n\n- 2025-12-30 框架：流程照另一個專案。\n")
        last = self.collect()["decisions"][-1]
        self.assertEqual((last["date"], last["milestone"], last["decider"], last["text"]), ("2025-12-30", "框架", "不明", "流程照另一個專案。"))

    def test_decisions_left_in_milestone_archives_are_read_too(self):
        self.write("docs/archive/M0.md", "# M0\n\n## Session 紀錄\n\n- 2025-12-01 這一行不是決定。\n\n## 偏差與決定\n\n- 2025-12-31 M0 票 02（使用者決定，試用後）：改用另一個套件。\n")
        last = self.collect()["decisions"][-1]
        self.assertEqual((last["date"], last["milestone"], last["decider"], last["text"]), ("2025-12-31", "M0", "使用者定", "改用另一個套件。"))

    def test_a_decision_without_a_decider_is_shown_as_unknown(self):
        self.sub("docs/decisions.md", "（使用者定）", "")
        self.assertEqual(self.collect()["decisions"][-1]["decider"], "不明")

    def test_adrs_sessions_and_next_step(self):
        d = self.collect()
        self.assertEqual(d["adrs"], [{"number": "0001", "title": "核心用 Rust", "file": "0001-rust-core.md"}])
        self.assertEqual([(s["date"], s["ticket"], s["result"]) for s in d["sessions"]],
                         [("2026-01-05", "M1 01", "查碼表做完 a|b"), ("2026-01-04", "M1 開工", "拆了 3 張票")])
        self.assertEqual(d["next"], "新 session 下 `/implement .scratch/m1/issues/02-bar.md`")

    def test_unrelated_formatting_does_not_change_the_data(self):
        before = self.collect()
        self.sub("docs/roadmap.md", "| --- | --- | --- | --- |", "|:---|:---:|---|---:|")
        self.sub("docs/roadmap.md", "## M2 介面\n\n目標：畫面。\n", "## M2 介面\n\n改寫過的說明。\n\n## 不排里程碑\n")
        self.sub("docs/decisions.md", "## 寫法\n", "## 寫法\n\n另一段說明。\n")
        self.sub("docs/progress.md", "## 寫法與封存\n", "## 寫法與封存\n\n- 規則。\n")
        self.sub(".scratch/m1/spec.md", "## 共同規則\n", "## 共同規則\n\n- 這裡的清單不算範圍。\n")
        self.write(".scratch/m1/notes-shape.md", "# shape\n")
        self.assertEqual(before, self.collect())

    def test_a_repo_without_the_skeleton_reports_what_is_missing(self):
        bare = self.root / "bare"
        bare.mkdir()
        d = m.collect(bare)
        self.assertEqual(d["missing"], ["docs/roadmap.md", "docs/decisions.md", "docs/progress.md"])
        self.assertEqual((d["milestones"], d["decisions"], d["sessions"], d["next"]), ([], [], [], ""))


@unittest.skipUnless(shutil.which("git"), "要 git")
class WorktreeTest(Repo):
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

    def test_a_ticket_being_worked_on_shows_up(self):
        self.assertEqual(self.collect()["working"], [])
        t = self.work / ".scratch/m1/issues/01-lookup.md"
        t.write_text(t.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        for committed in (False, True):
            if committed:
                self.git(self.work, "commit", "-qam", "feat: lookup")
            with self.subTest(committed=committed):
                self.assertEqual([(w["worktree"], w["branch"], w["milestone"], w["title"], w["checked"]) for w in self.collect()["working"]],
                                 [("t01", "t01", "M1 核心", "01: 查碼表", 2)])

    def test_a_stale_worktree_behind_main_does_not(self):
        self.sub(".scratch/m1/issues/02-bar.md", "Status: ready-for-agent", "Status: done")
        self.git(self.repo, "commit", "-qam", "docs: close ticket 02")
        self.assertEqual(self.collect()["working"], [])


class PageTest(Repo):
    def test_page_embeds_the_data_and_loads_nothing_external(self):
        self.sub("docs/decisions.md", "用 Rust 寫核心。", "用 Rust 寫核心。</script><b>")
        page = m.render(m.data([self.repo]))
        self.assertNotRegex(page, r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""")
        self.assertNotIn("@import", page)
        self.assertEqual(page.count("</script>"), 2)
        embedded = page.split('<script id="data" type="application/json">')[1].split("</script>")[0]
        self.assertEqual(json.loads(embedded), m.data([self.repo]))

    def test_static_output(self):
        out = self.root / "out.html"
        self.assertEqual(m.main([str(self.repo), "-o", str(out)]), 0)
        self.assertIn("專案總覽", out.read_text(encoding="utf-8"))
        self.assertEqual(m.main([str(self.root / "nope")]), 1)


class ServeTest(Repo):
    def test_served_data_follows_the_files(self):
        other = self.root / "other"
        self.write("AGENTS.md", "# Other\n", base=other)
        httpd = m.server([self.repo, other], "127.0.0.1", 0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close(), thread.join(5)))
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        def get(path):
            with urllib.request.urlopen(base + path, timeout=5) as r:
                return r.read().decode("utf-8")

        first = json.loads(get("/data.json"))
        self.assertEqual([p["name"] for p in first["projects"]], ["demo", "other"])
        self.assertIn("專案總覽", get("/"))
        self.sub(".scratch/m1/issues/01-lookup.md", "Status: ready-for-agent", "Status: done")
        second = json.loads(get("/data.json"))
        self.assertTrue(second["projects"][0]["milestones"][1]["tickets"][0]["done"])
        self.assertEqual(httpd.server_address[0], "127.0.0.1")
        with self.assertRaises(urllib.error.HTTPError):
            get("/../etc/passwd")


if __name__ == "__main__":
    unittest.main()
