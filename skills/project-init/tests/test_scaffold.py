"""scaffold.py 的測試：範本全部寫得進去、佔位填完、已存在的檔不動，寫出來的骨架過得了它自己的閘門。只在 plugin 裡跑。

    python -m unittest discover -s skills/project-init/tests
"""

import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scaffold", SKILL / "scripts" / "scaffold.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

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

    def test_every_template_and_gate_has_a_destination(self):
        self.assertEqual(sorted(m.TEMPLATES), sorted(p.name for p in (SKILL / "templates").iterdir()))
        for source, _, _ in m.sources():
            self.assertTrue(source.is_file(), source)
        scripts = {p.name for p in (SKILL / "scripts").glob("*.py")} - {"scaffold.py", "doc_reads.py"}
        self.assertEqual({Path(k).name for k in m.GATES if k.startswith("scripts/")}, scripts)
        self.assertEqual(len(set(m.TEMPLATES.values()) | set(m.GATES.values())), len(m.TEMPLATES) + len(m.GATES))

    def test_a_fresh_project_gets_everything_filled_in(self):
        code, out = self.run_it(str(self.root), *ARGS)
        self.assertEqual(code, 0)
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), len(m.TEMPLATES) + len(m.GATES) + len(m.KEPT_DIRS))
        self.assertTrue(all(l.startswith("寫入\t") for l in lines))
        for rel in list(m.TEMPLATES.values()) + list(m.GATES.values()) + [f"{d}/.gitkeep" for d in m.KEPT_DIRS]:
            self.assertTrue((self.root / rel).is_file(), rel)
        self.assertIn("# Demo\n\n示範專案。文件是唯一的記憶", (self.root / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("- 2026-01-02 框架", (self.root / "docs/decisions.md").read_text(encoding="utf-8"))
        self.assertIn("branches: [trunk]", (self.root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
        left = [rel for rel in m.TEMPLATES.values() if m.PLACEHOLDER.search((self.root / rel).read_text(encoding="utf-8"))]
        self.assertEqual(left, [])
        self.assertTrue(os.access(self.root / ".githooks/pre-commit", os.X_OK) and os.access(self.root / ".githooks/commit-msg", os.X_OK))

    def test_the_skeleton_passes_its_own_gates(self):
        self.run_it(str(self.root), *ARGS)
        for command in (["scripts/check_docs.py"], ["-m", "unittest", "discover", "-s", "scripts/tests"]):
            r = subprocess.run([sys.executable, *command], cwd=self.root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_existing_files_are_left_alone_and_reported(self):
        (self.root / "docs/adr").mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# 我的\n", encoding="utf-8")
        code, out = self.run_it(str(self.root), *ARGS)
        self.assertEqual((code, (self.root / "AGENTS.md").read_text(encoding="utf-8")), (0, "# 我的\n"))
        self.assertIn(f"已存在\tAGENTS.md\t{SKILL / 'templates' / 'instructions.md'}", out.split("\n"))
        self.assertFalse((self.root / "docs/adr/.gitkeep").exists())
        again = self.run_it(str(self.root), *ARGS)[1].strip().split("\n")
        self.assertTrue(all(l.startswith("已存在\t") for l in again), again)

    def test_list_and_wrong_usage(self):
        code, out = self.run_it("--list")
        self.assertEqual((code, len(out.strip().split("\n"))), (0, len(m.TEMPLATES) + len(m.GATES)))
        self.assertIn(f"{SKILL / 'templates' / 'roadmap.md'}\tdocs/roadmap.md", out.split("\n"))
        self.assertEqual(self.run_it(str(self.root / "nope"), *ARGS)[0], 1)
        with self.assertRaises(SystemExit):
            self.run_it(str(self.root), "--project", "Demo")


if __name__ == "__main__":
    unittest.main()
