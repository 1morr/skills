"""check_docs.py 的測試：每條規則違規會紅，無關的改動不紅。
在 plugin 裡腳本在 ../scripts/，複製進專案後在上一層；兩種位置都找。

    python -m unittest discover -s <這個資料夾>
"""

import contextlib
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = next(p for p in (HERE.parent / "scripts" / "check_docs.py", HERE.parent / "check_docs.py") if p.is_file())
spec = importlib.util.spec_from_file_location("check_docs", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PROGRESS = """# 進度

開頭的說明不屬於任何段。

## 寫法與封存

- 規則寫在這裡，這一段的行可以很長：%s

## 里程碑與閱讀指引

| 里程碑 | 票目錄 | 拆票前讀 | 備註 |
| --- | --- | --- | --- |
| M0 | `.scratch/m0/issues/` | brief | 完成，[已封存](archive/M0.md) |
| M1 | `.scratch/m1/issues/` | plan §2 | 進行中，已拆 3 張票 |

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-01-02 | M1 01 | 做了 a\\|b 兩件事 | 沒寫指令的舊列不檢查 |
| 2026-01-03 | M1 02 | 做完 | 新 session 下 `/implement .scratch/m1/issues/03-x.md` |

## 偏差與決定

- 2026-01-02 M1 票 01：改用另一個套件，見 ADR 0003。
""" % ("長" * 300)

SPEC = "# M1\n\n## 目標\n\n## 範圍（做 / 不做）\n\n## 共同規則\n\n## 驗收\n\n## 票序\n"
TICKET = "# 01: 標題\n\nStatus: ready-for-agent\nBlocked by: None\n\n## What to build\n\n## 驗收\n\n- [ ] 條件\n\n## Comments\n"


class Repo(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="check-docs-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.write("docs/progress.md", PROGRESS)
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

    def clean(self):
        self.assertEqual(m.run(self.root), [])

    def red(self, needle):
        found = m.run(self.root)
        self.assertTrue(any(needle in p for p in found), f"沒有一條違規提到「{needle}」：{found}")


class BasicsTest(Repo):
    def test_fixture_is_clean(self):
        self.clean()

    def test_main_exit_codes(self):
        self.assertEqual(m.main([str(self.root)]), 0)
        self.sub("docs/progress.md", "## 偏差與決定", "## 其他")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(m.main([str(self.root)]), 1)
        self.assertIn("2 條違規", err.getvalue())

    def test_missing_progress(self):
        (self.root / "docs/progress.md").unlink()
        self.red("找不到")


class ProgressSectionsTest(Repo):
    def test_missing_section(self):
        self.sub("docs/progress.md", "## 寫法與封存", "## 寫法")
        self.red("缺〈寫法與封存〉")

    def test_duplicate_section(self):
        self.sub("docs/progress.md", "## 偏差與決定", "## 偏差與決定\n\n## 偏差與決定")
        self.red("出現 2 次")

    def test_wrong_order(self):
        text = (self.root / "docs/progress.md").read_text(encoding="utf-8")
        a, b = text.index("## Session 紀錄"), text.index("## 偏差與決定")
        self.write("docs/progress.md", text[:a] + text[b:] + "\n" + text[a:b])
        self.red("順序不對")

    def test_extra_section(self):
        self.sub("docs/progress.md", "## 偏差與決定", "## 待辦\n\n## 偏差與決定")
        self.red("多了〈待辦〉")

    def test_heading_in_code_block_and_h3_are_not_sections(self):
        self.sub("docs/progress.md", "- 規則寫在這裡", "### 小節\n\n```\n## 範例\n```\n\n- 規則寫在這裡")
        self.clean()


class SessionsTest(Repo):
    def test_text_outside_the_table(self):
        self.sub("docs/progress.md", "\n## 偏差與決定", "補充說明寫在表外。\n\n## 偏差與決定")
        self.red("表外不放別的字")

    def test_row_too_long(self):
        self.sub("docs/progress.md", "| 做完 |", "| " + "字" * 200 + " |")
        self.red("上限 200")

    def test_row_of_exactly_200_is_fine(self):
        row = "| 2026-01-03 | M1 02 | 做完 | 新 session 下 `/implement .scratch/m1/issues/03-x.md` |"
        self.sub("docs/progress.md", row, row.replace("做完", "做完" + "字" * (200 - len(row))))
        self.clean()

    def test_last_row_without_a_command(self):
        self.sub("docs/progress.md", "新 session 下 `/implement .scratch/m1/issues/03-x.md`", "繼續做下一張票")
        self.red("下一步")

    def test_code_that_is_not_a_command(self):
        self.sub("docs/progress.md", "新 session 下 `/implement .scratch/m1/issues/03-x.md`", "看 `docs/plan.md`")
        self.red("下一步")

    def test_waiting_for_the_user_or_the_coordinator_is_fine(self):
        for step in ("等使用者：決定要不要支援 Windows", "由協調者決定"):
            with self.subTest(step):
                original = (self.root / "docs/progress.md").read_text(encoding="utf-8")
                self.sub("docs/progress.md", "新 session 下 `/implement .scratch/m1/issues/03-x.md`", step)
                self.clean()
                self.write("docs/progress.md", original)

    def test_no_rows(self):
        self.sub("docs/progress.md", "| 2026-01-02 | M1 01 | 做了 a\\|b 兩件事 | 沒寫指令的舊列不檢查 |\n", "")
        self.sub("docs/progress.md", "| 2026-01-03 | M1 02 | 做完 | 新 session 下 `/implement .scratch/m1/issues/03-x.md` |\n", "")
        self.red("沒有任何一列")

    def test_missing_next_column(self):
        self.sub("docs/progress.md", "| 日期 | 票 | 結果 | 下一步 |", "| 日期 | 票 | 結果 | 之後 |")
        self.red("「下一步」欄")

    def test_column_order_and_alignment_do_not_matter(self):
        self.sub("docs/progress.md", "| 日期 | 票 | 結果 | 下一步 |\n| --- | --- | --- | --- |", "| 日期 | 票 | 結果 | 下一步 |\n|:---|:---:|---|---:|")
        self.clean()


class DeviationsTest(Repo):
    def test_entry_without_a_date(self):
        self.sub("docs/progress.md", "- 2026-01-02 M1 票 01", "- M1 票 01")
        self.red("YYYY-MM-DD")

    def test_wrapped_entry(self):
        self.sub("docs/progress.md", "見 ADR 0003。", "見 ADR 0003。\n  第二行的補充。")
        self.red("每條一行")

    def test_entry_too_long(self):
        self.sub("docs/progress.md", "見 ADR 0003。", "見 ADR 0003。" + "字" * 200)
        self.red("上限 200")

    def test_empty_section_is_fine(self):
        self.sub("docs/progress.md", "- 2026-01-02 M1 票 01：改用另一個套件，見 ADR 0003。\n", "")
        self.clean()


class MilestonesTest(Repo):
    def test_two_active(self):
        self.sub("docs/progress.md", "| 完成，[已封存](archive/M0.md) |", "| 進行中，還有 1 張 |")
        self.red("最多一個")

    def test_none_active_is_fine(self):
        self.sub("docs/progress.md", "| 進行中，已拆 3 張票 |", "| 未拆票，上一個里程碑還在進行中的檢查不算 |")
        self.clean()

    def test_missing_note_column(self):
        self.sub("docs/progress.md", "| 里程碑 | 票目錄 | 拆票前讀 | 備註 |", "| 里程碑 | 票目錄 | 拆票前讀 | 狀態 |")
        self.red("「備註」欄")


class ScratchTest(Repo):
    def test_tickets_without_spec(self):
        (self.root / ".scratch/m1/spec.md").unlink()
        self.red("沒有 spec.md")

    def test_spec_missing_a_section(self):
        self.sub(".scratch/m1/spec.md", "## 共同規則\n\n", "")
        self.red("缺〈共同規則〉")

    def test_spec_extra_sections_and_order_do_not_matter(self):
        self.write(".scratch/m1/spec.md", "# M1\n\n## 票序\n\n## 細節\n\n## 驗收\n\n## 共同規則\n\n## 範圍\n\n## 目標(做什麼)\n")
        self.clean()

    def test_milestone_without_acceptance_ticket(self):
        (self.root / ".scratch/m1/issues/02-m1-acceptance.md").rename(self.root / ".scratch/m1/issues/02-m1-close.md")
        self.red("沒有驗收票")

    def test_effort_that_is_not_a_milestone_needs_no_acceptance_ticket(self):
        self.write(".scratch/docs-cleanup/spec.md", SPEC)
        self.write(".scratch/docs-cleanup/issues/01-trim.md", TICKET)
        self.clean()

    def test_decimal_milestone_needs_one(self):
        self.write(".scratch/m1.5/spec.md", SPEC)
        self.write(".scratch/m1.5/issues/01-x.md", TICKET)
        self.red(".scratch/m1.5/issues/：沒有驗收票")

    def test_directory_without_issues_is_ignored(self):
        self.write(".scratch/notes/draft.md", "隨手記")
        self.clean()

    def test_ticket_without_status(self):
        self.sub(".scratch/m1/issues/01-first.md", "Status: ready-for-agent\n", "")
        self.red("Status:")

    def test_status_only_in_a_later_section_does_not_count(self):
        self.sub(".scratch/m1/issues/01-first.md", "Status: ready-for-agent\n", "")
        self.sub(".scratch/m1/issues/01-first.md", "## Comments\n", "## Comments\n\nStatus: done\n")
        self.red("Status:")

    def test_status_value_and_bold_do_not_matter(self):
        self.sub(".scratch/m1/issues/01-first.md", "Status: ready-for-agent", "**Status:** done")
        self.clean()


if __name__ == "__main__":
    unittest.main()
