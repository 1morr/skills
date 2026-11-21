"""skel.py 統一 CLI 入口（check / next / notes / dashboard）的測試。

    python3 -m unittest discover -s skills/project-init/tests
"""

import contextlib
import importlib.util
import io
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


skel = _load("skel")
scaffold = _load("scaffold")


class SkelCliTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="skel-cli-")).resolve()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        scaffold.scaffold(self.repo, {"PROJECT": "Demo", "ONE_LINE": "示範。", "DATE": "2026-01-02", "MAIN_BRANCH": "main"}, with_scratch=True)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = skel.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_help_and_unknown_subcommand(self):
        code, out, _ = self.run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("1morr-skel", out)
        code_bad, _, err_bad = self.run_cli("unknown-cmd")
        self.assertEqual(code_bad, 2)
        self.assertIn("未知的子命令", err_bad)

    def test_check_next_notes_and_dashboard_subcommands(self):
        self.assertEqual(self.run_cli("check", str(self.repo))[0], 0)
        code_next, out_next, _ = self.run_cli("next", str(self.repo))
        self.assertEqual(code_next, 0)
        self.assertIn("現在", out_next)

        html_out = self.repo / "out.html"
        code_dash, out_dash, _ = self.run_cli("dashboard", str(self.repo), "-o", str(html_out))
        self.assertEqual(code_dash, 0)
        self.assertIn("專案總覽", html_out.read_text(encoding="utf-8"))
        self.assertEqual(Path(out_dash.strip()), html_out)


if __name__ == "__main__":
    unittest.main()
