"""next_step.py 的測試：每個階段都說得出下一步，粗體 Blocked by 與排隊佇列一致運作。

    python3 -m unittest discover -s skills/project-init/tests
"""

import contextlib
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "next_step.py"
spec = importlib.util.spec_from_file_location("next_step", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ROADMAP = "# 路線圖\n\n## 里程碑\n\n| 里程碑 | 目標 | 狀態 |\n| --- | --- | --- |\n%s\n## M2 介面\n\n| 里程碑 | 狀態 |\n| --- | --- |\n| 別段的表 | 進行中 |\n"
PROGRESS = "# 進度\n\n## Session 紀錄\n\n| 日期 | 票 | 結果 | 下一步 |\n| --- | --- | --- | --- |\n| 2026-01-02 | 框架 | 建骨架 | 新 session 下 `/舊的` |\n| 2026-01-05 | M1 開工 | 拆票 | %s |\n"
TICKET = "# {n}: {title}\n\nStatus: {status}\nBlocked by: {blocked}\n\n## 驗收\n\n- [ ] 條件\n\n## Comments\n{notes}"


class NextStepTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="next-step-")).resolve()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.rows("| M0 骨架 | 閘門 | 已驗收，封存在 x |", "| M1 核心 | 第一個功能 | 進行中，已拆 4 張票 |", "| M2 介面 | 畫面 | 未開工 |")
        self.step("新 session 下 `/implement .scratch/m1/issues/01-a.md`")
        self.ticket("m0/issues/01-old.md", status="ready-for-agent")
        self.ticket("m1/issues/01-a.md", "甲")
        self.ticket("m1/issues/02-b.md", "乙", blocked="01")
        self.ticket("m1/issues/03-c.md", "丙", blocked="01, 02")
        self.ticket("m1/issues/04-m1-acceptance.md", "M1 驗收", blocked="01, 02, 03")

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def rows(self, *rows):
        self.write("docs/roadmap.md", ROADMAP % "".join(r + "\n" for r in rows))

    def step(self, text):
        self.write("docs/progress.md", PROGRESS % text)

    def ticket(self, rel, title="標題", status="ready-for-agent", blocked="None", notes=""):
        self.write(f".scratch/{rel}", TICKET.format(n=rel.split("/")[-1].split("-")[0], title=title, status=status, blocked=blocked, notes=notes))

    def done(self, *rels):
        for rel in rels:
            self.ticket(rel, status="done")

    def found(self):
        return m.report(self.repo)

    def test_the_first_ticket_nothing_blocks_is_now(self):
        f = self.found()
        self.assertEqual((f["waiting"], f["command"]), ([], "/implement .scratch/m1/issues/01-a.md"))
        self.assertIn("M1 票 01 甲。", f["why"])
        self.assertEqual(f["later"], ["M1 還有 3 張票，最後一張是驗收票（含試用與決策追認）", "M2 介面：還沒拆票"])

    def test_done_dropped_and_blocked_tickets_are_skipped(self):
        self.done("m1/issues/01-a.md")
        self.ticket("m1/issues/02-b.md", status="wontfix：不需要了", blocked="01")
        self.assertEqual(self.found()["command"], "/implement .scratch/m1/issues/03-c.md")
        self.done("m1/issues/03-c.md")
        f = self.found()
        self.assertEqual((f["command"], f["later"][0]), ("/implement .scratch/m1/issues/04-m1-acceptance.md", "這張是 M1 的驗收票（含試用與決策追認）"))

    def test_bold_status_and_bold_blocked_by_are_parsed(self):
        self.write(".scratch/m1/issues/01-a.md", "# 01 — 甲\n\n**Status:** ready-for-agent\n\n**Blocked by:** 02\n\n## Comments\n")
        self.write(".scratch/m1/issues/02-b.md", "# 02 — 乙\n\n**Status:** ready-for-agent\n\n**Blocked by:** None\n\n## Comments\n")
        f = self.found()
        self.assertEqual(f["command"], "/implement .scratch/m1/issues/02-b.md")

    def test_open_questions_and_waiting_skip(self):
        self.ticket("m1/issues/01-a.md", "甲", notes="\n- 等使用者：上限寫死還是做成設定？\n")
        self.ticket("m1/issues/02-b.md", "乙")
        f = self.found()
        self.assertEqual((len(f["waiting"]), f["command"]), (1, "/implement .scratch/m1/issues/02-b.md"))

    def test_a_second_queue_waits_for_the_row_it_names(self):
        self.ticket("docs-diet/issues/01-trim.md", "瘦身")
        self.rows("| docs-diet 文件瘦身 | 瘦身 | 未開工，排在 M1 之後 |", "| M1 核心 | 功能 | 已驗收，封存在 x |", "| M2 介面 | 畫面 | 未開工 |")
        f = self.found()
        self.assertEqual(f["command"], "/implement .scratch/docs-diet/issues/01-trim.md")
        self.assertIn("先把 docs/roadmap.md 里程碑表裡 docs-diet 那一列的狀態改成「進行中」", f["why"])
        # 排在未結束的 M2 之後 -> 不切過去
        self.rows("| docs-diet 文件瘦身 | 瘦身 | 未開工，排在 M2 之後 |", "| M1 核心 | 功能 | 已驗收 |", "| M2 介面 | 畫面 | 未開工 |")
        self.assertEqual(self.found()["command"], "/implement .scratch/m1/issues/01-a.md")

    def test_main_prints_three_sections(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(m.main([str(self.repo)]), 0)
        self.assertIn("現在\n  /implement .scratch/m1/issues/01-a.md", out.getvalue())


if __name__ == "__main__":
    unittest.main()
