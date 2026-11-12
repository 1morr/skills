"""check_commit_msg.py 的測試。在 plugin 裡腳本在 ../scripts/，複製進專案後在上一層；兩種位置都找。

    python -m unittest discover -s <這個資料夾>
"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = next(p for p in (HERE.parent / "scripts" / "check_commit_msg.py", HERE.parent / "check_commit_msg.py") if p.is_file())
spec = importlib.util.spec_from_file_location("check_commit_msg", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SubjectTest(unittest.TestCase):
    def ok(self, subject):
        self.assertEqual(m.problems(subject), [], subject)

    def bad(self, subject):
        self.assertNotEqual(m.problems(subject), [], subject)

    def test_accepts_conventional_subjects(self):
        for s in ("feat: add search", "fix(parser): keep the last token", "feat(api)!: drop v1 routes",
                  "docs: 說明安裝步驟", "chore: bump 3 dependencies", "refactor(core): x" + "y" * 50):
            self.ok(s)

    def test_accepts_git_default_messages(self):
        self.ok("Merge branch 'main' into t04")
        self.ok('Revert "feat: add search"')
        self.ok("Merge branch 'a-very-long-branch-name-that-goes-on-and-on-past-the-seventy-two-character-limit'")

    def test_rejects_unknown_type_or_shape(self):
        for s in ("add search", "feature: add search", "feat:add search", "feat (api): add", "feat():  add", "merge: ticket 01 x", ""):
            self.bad(s)

    def test_rejects_capitalised_subject(self):
        self.bad("feat: Add search")
        self.bad("fix(parser): Keep the last token")

    def test_rejects_trailing_period(self):
        self.bad("feat: add search.")
        self.ok("feat: add search for v1.2")

    def test_length_limit_is_72(self):
        self.ok("feat: " + "a" * 66)
        self.bad("feat: " + "a" * 67)

    def test_type_inside_scope_or_subject_is_not_a_type(self):
        self.bad("(feat): add search")
        self.bad("add feat: search")


class FileTest(unittest.TestCase):
    def run_file(self, text):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()):
            p = Path(d) / "MSG"
            p.write_text(text, encoding="utf-8")
            return m.main([str(p)])

    def test_reads_the_first_non_comment_line(self):
        self.assertEqual(self.run_file("# 請輸入 commit message\n\nfeat: add search\n\nBody Starts With A Capital.\n"), 0)

    def test_body_does_not_rescue_a_bad_subject(self):
        self.assertEqual(self.run_file("Add search\n\nfeat: add search\n"), 1)

    def test_subject_flag(self):
        self.assertEqual(m.main(["--subject", "fix: handle empty input"]), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(m.main(["--subject", "Fix stuff"]), 1)


if __name__ == "__main__":
    unittest.main()
