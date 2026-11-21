"""scaffold.py 的測試：寫入下游業務 repo 0 行 Python 腳本與測試、預設總寫入檔數 <= 12、含 .gitignore，且過得了 skel check。

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

SKILL = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load("scaffold")
skel = _load("skel")

ARGS = ("--project", "Demo", "--one-line", "示範專案。", "--main-branch", "trunk", "--date", "2026-01-02")


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="scaffold-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def run_it(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = m.main(list(args))
        return code, out.getvalue()

    def test_every_template_is_accounted_for_and_zero_python_gates(self):
        self.assertEqual(m.GATES, {})
        self.assertEqual(m.KEPT_DIRS, ())
        all_templates = set(m.TEMPLATES) | set(m.SCRATCH_TEMPLATES)
        self.assertEqual(sorted(all_templates), sorted(p.name for p in (SKILL / "templates").iterdir()))
        self.assertLessEqual(len(m.TEMPLATES), 12)

    def test_fresh_project_writes_at_most_12_files_and_zero_python(self):
        code, out = self.run_it(str(self.root), *ARGS)
        self.assertEqual(code, 0)
        lines = out.strip().split("\n")
        self.assertLessEqual(len(lines), 12)
        self.assertEqual(len(lines), len(m.TEMPLATES))
        self.assertTrue(all(l.startswith("寫入\t") for l in lines))

        written_files = [p for p in self.root.rglob("*") if p.is_file()]
        self.assertLessEqual(len(written_files), 12)
        # 業務 repo 內 0 行 Python 腳本與測試
        self.assertEqual(list(self.root.rglob("*.py")), [])
        self.assertTrue((self.root / ".gitignore").is_file())
        self.assertTrue(os.access(self.root / ".githooks/pre-commit", os.X_OK))
        self.assertTrue(os.access(self.root / ".githooks/commit-msg", os.X_OK))

        ci_text = (self.root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [trunk]", ci_text)
        self.assertIn("refs/heads/trunk", ci_text)
        left = [rel for rel in m.TEMPLATES.values() if m.PLACEHOLDER.search((self.root / rel).read_text(encoding="utf-8"))]
        self.assertEqual(left, [])

        # 剛寫好的骨架直接通過 skel check
        self.assertEqual(skel.main(["check", str(self.root)]), 0)

    def test_with_scratch_flag_adds_optional_ticket_templates(self):
        code, out = self.run_it(str(self.root), *ARGS, "--with-scratch")
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "docs/agents/milestone.md").is_file())
        self.assertTrue((self.root / "docs/agents/ticket-template.md").is_file())
        self.assertTrue((self.root / "CHANGELOG.md").is_file())
        self.assertEqual(list(self.root.rglob("*.py")), [])
        self.assertEqual(skel.main(["check", str(self.root)]), 0)

    def test_existing_files_are_left_alone_and_reported(self):
        (self.root / "AGENTS.md").write_text("# 我的\n", encoding="utf-8")
        code, out = self.run_it(str(self.root), *ARGS)
        self.assertEqual((code, (self.root / "AGENTS.md").read_text(encoding="utf-8")), (0, "# 我的\n"))
        self.assertIn(f"已存在\tAGENTS.md\t{SKILL / 'templates' / 'instructions.md'}", out.split("\n"))
        again = self.run_it(str(self.root), *ARGS)[1].strip().split("\n")
        self.assertTrue(all(l.startswith("已存在\t") for l in again), again)

    def test_list_and_wrong_usage(self):
        code, out = self.run_it("--list")
        self.assertEqual((code, len(out.strip().split("\n"))), (0, len(m.TEMPLATES)))
        code_all, out_all = self.run_it("--list", "--with-scratch")
        self.assertEqual((code_all, len(out_all.strip().split("\n"))), (0, len(m.TEMPLATES) + len(m.SCRATCH_TEMPLATES)))
        self.assertEqual(self.run_it(str(self.root / "nope"), *ARGS)[0], 1)
        with self.assertRaises(SystemExit):
            self.run_it(str(self.root), "--project", "Demo")


if __name__ == "__main__":
    unittest.main()
