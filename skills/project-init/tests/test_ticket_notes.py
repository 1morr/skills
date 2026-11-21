"""ticket_notes.py 與 notes --archive 直接封存寫出至 docs/archive/<M>.md 的測試。

    python3 -m unittest discover -s skills/project-init/tests
"""

import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

for _name in [n for n in os.environ if n.startswith("GIT_")]:
    del os.environ[_name]

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "ticket_notes.py"
spec = importlib.util.spec_from_file_location("ticket_notes", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

HEAD = "# {n}: {title}\n\nStatus: done\nBlocked by: None\n\n## What to build\n\n決定：這一行在 Comments 之前，不算。\n\n## 驗收\n\n- [x] 好了\n\n## Comments\n\n"


class TicketNotesTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="ticket-notes-")).resolve()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def ticket(self, rel, title, *lines):
        p = self.repo / ".scratch" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(HEAD.format(n=p.name.split("-")[0], title=title) + "\n".join(lines) + "\n", encoding="utf-8")
        return p

    def run_it(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = m.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_each_ticket_prints_its_notes(self):
        self.ticket("m0/issues/01-gates.md", "閘門", "Session 紀錄：2026-01-04 閘門就位。",
                    "決定：用 X 不用 Y（Agent 定）", "決定：埠由系統挑(使用者同意)")
        self.ticket("m0/issues/02-m0-acceptance.md", "M0 驗收")
        code, out, _ = self.run_it("m0", str(self.repo))
        self.assertEqual(code, 0)
        self.assertEqual(out, "M0 01 閘門（2026-01-04）\n  Session 紀錄：閘門就位。\n  決定：用 X 不用 Y（Agent 定）\n  決定：埠由系統挑（使用者同意）\n")

    def test_archive_writes_docs_archive_file_and_moves_progress_and_decisions(self):
        (self.repo / "docs").mkdir(parents=True, exist_ok=True)
        (self.repo / "docs/progress.md").write_text(
            "# 進度\n\n## Session 紀錄\n\n| 日期 | 票 | 結果 | 下一步 |\n| --- | --- | --- | --- |\n"
            "| 2026-01-01 | 框架 | 建骨架 | `/grill` |\n| 2026-01-03 | M0 開工 | 拆票 | `/implement` |\n| 2026-01-05 | M1 準備 | 留著 | `/next` |\n",
            encoding="utf-8",
        )
        (self.repo / "docs/decisions.md").write_text(
            "# 決策\n\n## 紀錄\n\n- 2026-01-01 框架（Agent 定）：先搭骨架。\n- 2026-01-03 M0（使用者定）：M0 目標。\n- 2026-01-05 M1（使用者定）：保留在原檔。\n",
            encoding="utf-8",
        )
        self.ticket("m0/issues/01-gates.md", "閘門", "Session 紀錄：2026-01-04 做完 a | b。", "決定：用 X（Agent 定）")

        # 支援 `--archive m0 <repo>` 順序直接寫出 docs/archive/M0.md
        code, out, err = self.run_it("--archive", "m0", str(self.repo), "--user-trial", "- 實跑通過。")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), "docs/archive/M0.md")

        archived = (self.repo / "docs/archive/M0.md").read_text(encoding="utf-8")
        self.assertIn("| 2026-01-01 | 框架 | 建骨架 | `/grill` |", archived)
        self.assertIn("| 2026-01-04 | M0 01 | 做完 a \\| b。 | |", archived)
        self.assertIn("- 2026-01-01 框架（Agent 定）：先搭骨架。", archived)
        self.assertIn("- 2026-01-04 M0 票 01（Agent 定）：用 X", archived)
        self.assertIn("- 實跑通過。", archived)

        # M1 的紀錄保留在原檔，已封存的框架與 M0 已從原檔移除
        rem_prog = (self.repo / "docs/progress.md").read_text(encoding="utf-8")
        self.assertNotIn("M0 開工", rem_prog)
        self.assertIn("M1 準備", rem_prog)
        rem_dec = (self.repo / "docs/decisions.md").read_text(encoding="utf-8")
        self.assertNotIn("先搭骨架", rem_dec)
        self.assertIn("M1（使用者定）：保留在原檔", rem_dec)

    def test_archive_stdout_mode_does_not_write_file(self):
        self.ticket("m1.5/issues/02-b.md", "乙", "Session 紀錄：2026-01-05 做完乙。", "決定：用 X（Agent 定）")
        code, out, _ = self.run_it("m1.5", str(self.repo), "--archive", "--stdout")
        self.assertEqual(code, 0)
        self.assertIn("## Session 紀錄", out)
        self.assertFalse((self.repo / "docs/archive/M1.5.md").exists())

    def test_changelog_entries_support_both_pipe_widths(self):
        self.ticket("m0/issues/01-a.md", "甲", "Session 紀錄：2026-01-04 做完甲。",
                    "變更：Fixed | 候選列 | 半形直線也認。", "變更：Added｜搜尋｜全形直線也認。", "變更：無")
        self.assertEqual(m.changelog(self.repo, "m0"), ["### Added", "- **搜尋**：全形直線也認。", "", "### Fixed", "- **候選列**：半形直線也認。"])

    @unittest.skipUnless(shutil.which("git"), "要 git")
    def test_undated_ticket_in_git_takes_last_commit_date(self):
        self.ticket("m0/issues/01-gates.md", "閘門", "Session 紀錄：閘門就位。")
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
                   GIT_AUTHOR_DATE="2026-01-03T12:00:00", GIT_COMMITTER_DATE="2026-01-03T12:00:00")
        for args in (("init", "-q"), ("add", "-A"), ("-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "docs: t")):
            subprocess.run(["git", "-C", str(self.repo), *args], env=env, check=True, capture_output=True)
        self.assertEqual(m.notes(self.repo, "m0")[0]["date"], "2026-01-03")


if __name__ == "__main__":
    unittest.main()
