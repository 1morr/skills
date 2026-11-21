"""check_docs.py（瘦身硬契約版）的測試：狀態機與閘門違規會紅，半形標點與排版差異放行，字元超標僅出 WARN 不擋 exit code。

    python3 -m unittest discover -s skills/project-init/tests
"""

import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

for _name in [n for n in os.environ if n.startswith("GIT_")]:
    del os.environ[_name]

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "check_docs.py"
spec = importlib.util.spec_from_file_location("check_docs", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PROGRESS = """# 進度

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-01-02 | M1 01 | 做了 a\\|b 兩件事 | 舊列不檢查 |
| 2026-01-03 | M1 02 | 做完 | 新 session 下 `/implement .scratch/m1/issues/03-x.md` |
"""

DECISIONS = """# 決策紀錄

## 紀錄

- 2026-01-02 M1 票 01（使用者同意）：改用另一個套件，見 ADR 0003。
"""

ROADMAP = """# 路線圖

## 里程碑

| 里程碑 | 目標 | 拆票前讀 | 狀態 |
| --- | --- | --- | --- |
| M0 骨架 | 閘門 | brief | 已驗收，封存在 [`docs/archive/M0.md`](archive/M0.md) |
| M1 核心 | 第一個功能 | plan §2 | 進行中，已拆 2 張票 |
| M2 介面 | 畫面 | brief §4 | 未開工 |
"""

SPEC = "# M1\n\n## 目標\n\n## 範圍（做 / 不做）\n\n## 共同規則\n\n## 驗收\n\n### Agent 驗\n\n### 使用者試\n\n- 啟動後打一個字。\n\n## 票序\n"
TICKET = "# 01: 標題\n\nStatus: ready-for-agent\nBlocked by: None\n\n## What to build\n\n## 驗收\n\n- [ ] 條件\n\n## Comments\n"


class Repo(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="check-docs-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.write("docs/progress.md", PROGRESS)
        self.write("docs/roadmap.md", ROADMAP)
        self.write("docs/decisions.md", DECISIONS)
        self.write(".scratch/m1/spec.md", SPEC)
        self.write(".scratch/m1/issues/01-first.md", TICKET)
        self.write(".scratch/m1/issues/02-m1-acceptance.md", TICKET)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def sub(self, rel, old, new):
        text = (self.root / rel).read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new))

    def row(self, name, state="未開工，排在 M1 之後"):
        self.sub("docs/roadmap.md", "| M2 介面 | 畫面 | brief §4 | 未開工 |\n", f"| M2 介面 | 畫面 | brief §4 | 未開工 |\n| {name} | 目標 | — | {state} |\n")

    def clean(self):
        self.assertEqual(m.run(self.root), [])

    def red(self, needle):
        found = m.run(self.root)
        self.assertTrue(any(needle in p for p in found), f"沒有一條違規提到「{needle}」：{found}")


class HardContractAndRelaxedStyleTest(Repo):
    def test_fixture_is_clean(self):
        self.clean()

    def test_missing_core_state_files_fail(self):
        for rel in ("docs/progress.md", "docs/roadmap.md", "docs/decisions.md"):
            with self.subTest(rel):
                self.setUp()
                (self.root / rel).unlink()
                self.red(f"找不到 {rel}")

    def test_style_preferences_are_no_longer_policed(self):
        """瘦身驗證：新加 docs/ 檔案不寫入 AGENTS.md、research 日期在開頭、長行、半形括號與半形 | 全部合法放行。"""
        self.write("AGENTS.md", "# Demo\n")
        self.write("docs/extra-guide.md", "# 額外說明\n")
        self.write("docs/research/2026-01-02-notes.md", "# 日期在開頭\n")
        self.write("docs/decisions.md", "# 決策\n\n## 紀錄\n\n- 2026-01-02 M1(Agent 定)：半形括號且超過兩百字" + "長" * 220 + "\n")
        self.write("CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- **搜尋**: 半形冒號也收。\n")
        done = TICKET.replace("ready-for-agent", "done") + "\nSession 紀錄：2026-01-04 做完。\n決定：半形括號(使用者定)\n變更：Added | 搜尋 | 半形直線分隔符。\n"
        self.write(".scratch/m1/issues/01-first.md", done)
        self.clean()

    def test_budget_is_soft_warning_and_exits_zero(self):
        """字元超標僅印 WARN 軟警告，exit code 維持 0。"""
        self.write("AGENTS.md", "# Demo\n" + "字" * 9000)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = m.main([str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn("WARN: AGENTS.md", err.getvalue())

    def test_progress_requires_sessions_table_and_next_step(self):
        self.sub("docs/progress.md", "新 session 下 `/implement .scratch/m1/issues/03-x.md`", "沒有指令的文字")
        self.red("下一步")
        self.setUp()
        self.sub("docs/progress.md", "新 session 下 `/implement .scratch/m1/issues/03-x.md`", "等使用者：確認方案")
        self.clean()

    def test_decisions_require_date_and_one_decider(self):
        self.sub("docs/decisions.md", "（使用者同意）", "")
        self.red("決定者")
        self.setUp()
        self.sub("docs/decisions.md", "- 2026-01-02", "- 沒日期")
        self.red("YYYY-MM-DD")

    def test_roadmap_at_most_one_active_and_valid_state_prefix(self):
        self.sub("docs/roadmap.md", "已驗收，封存在 [`docs/archive/M0.md`](archive/M0.md)", "進行中")
        self.red("最多一個")
        self.setUp()
        self.sub("docs/roadmap.md", "| 未開工 |", "| 待驗收 |")
        self.red("狀態要以")

    def test_archive_requires_three_sections(self):
        self.write("docs/archive/M0.md", "# M0\n\n## Session 紀錄\n\n## 決定\n\n- 2026-01-01 M0(使用者定)：OK\n\n## 使用者試\n\n- 通過。\n")
        self.clean()
        self.sub("docs/archive/M0.md", "- 通過。\n", "")
        self.red("缺〈使用者試〉段")

    def test_scratch_and_done_ticket_contracts(self):
        # 缺驗收票
        (self.root / ".scratch/m1/issues/02-m1-acceptance.md").unlink()
        self.red("沒有驗收票")
        self.setUp()
        # 進行中且 done 的票未留 Session 紀錄或留了未答的等使用者
        self.sub(".scratch/m1/issues/01-first.md", "Status: ready-for-agent", "Status: done")
        self.red("Session 紀錄：")
        self.write(".scratch/m1/issues/01-first.md", TICKET.replace("ready-for-agent", "done") + "\nSession 紀錄：2026-01-04 完成\n等使用者：還沒答？\n")
        self.red("還沒有回答")
        # 雙佇列未標排在誰之後
        self.setUp()
        self.write(".scratch/docs-diet/spec.md", SPEC)
        self.write(".scratch/docs-diet/issues/01-trim.md", TICKET)
        self.row("docs-diet 瘦身", "未開工")
        self.red("排在")
        self.sub("docs/roadmap.md", "| docs-diet 瘦身 | 目標 | — | 未開工 |", "| docs-diet 瘦身 | 目標 | — | 未開工，排在 M1 之後 |")
        self.clean()

    def test_gates_table_enforced_once_a_ticket_is_done(self):
        table = "# 開發\n\n## 閘門\n\n| 閘門 | 指令或設定檔 |\n| --- | --- |\n" + "".join(f"| {g} | 待定 |\n" for g in m.GATE_ROWS)
        self.write("docs/development.md", table)
        self.clean()
        self.write(".scratch/m1/issues/01-first.md", TICKET.replace("ready-for-agent", "done") + "\nSession 紀錄：2026-01-04 做完。\n")
        self.red("還沒有著落")
        self.write("docs/development.md", table.replace("| 待定 |", "| `make check` |").replace("| 型別 | `make check` |", "| 型別 | 不適用: 純 shell |"))
        self.clean()


if __name__ == "__main__":
    unittest.main()
