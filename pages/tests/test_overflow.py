"""overflow.py 的單元測試：HTML 量測注入、DOM 溢出解析、無瀏覽器 fallback 與 CLI 參數。

    python3 -m unittest discover -s pages/tests
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
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "overflow.py"
spec = importlib.util.spec_from_file_location("overflow", SCRIPT)
overflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overflow)


def page(body="<p>短</p>", head=""):
    return f'<!doctype html><html><head><meta charset="utf-8">{head}</head><body>{body}</body></html>'


MEASURED_CLEAN = '<meta name="overflow-report" content="[]">'
MEASURED_WIDE = (
    '<meta name="overflow-report" content="[{&quot;box&quot;:&quot;整頁&quot;,&quot;over&quot;:120,'
    '&quot;items&quot;:[{&quot;el&quot;:&quot;span.src&quot;,&quot;over&quot;:120,&quot;text&quot;:&quot;長標籤&quot;}]}]">'
)


class ProbeInjectionTest(unittest.TestCase):
    def test_injects_before_last_closing_body_tag(self):
        src = '<html><BODY><pre>const s = "</body>";</pre><p>正文</p></BODY></html>'
        out = overflow.with_probe(src, prepare="window.__ready = 1;")
        self.assertIn("window.__ready = 1;", out)
        self.assertNotIn("/*PREPARE*/", out)
        # 第一個字串內的 </body> 維持原處，PROBE 插在最後一個 </BODY> 之前
        self.assertLess(out.index('const s = "</body>"'), out.index('meta.name = "overflow-report"'))
        self.assertTrue(out.endswith("</BODY></html>"))

    def test_appends_when_body_closing_tag_missing(self):
        out = overflow.with_probe("<p>片段</p>")
        self.assertTrue(out.startswith("<p>片段</p><script>"))
        self.assertIn('meta.name = "overflow-report"', out)


class ProblemsParsingTest(unittest.TestCase):
    def test_clean_report_returns_empty_list(self):
        self.assertEqual(overflow.problems(page(head=MEASURED_CLEAN), 1440), [])

    def test_missing_report_meta_flags_incomplete_probe(self):
        found = overflow.problems(page("<p>沒有 meta</p>"), 1440)
        self.assertEqual(len(found), 1)
        self.assertIn("1440px", found[0])
        self.assertIn("量測沒有跑完", found[0])

    def test_decodes_escaped_entities_and_formats_offending_elements(self):
        found = overflow.problems(page(head=MEASURED_WIDE), 390)
        self.assertEqual(len(found), 1)
        self.assertIn("390px", found[0])
        self.assertIn("整頁被撐寬 120px", found[0])
        self.assertIn("<span.src> 超出 120px「長標籤」", found[0])


class RenderAndFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="overflow-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.page = self.tmp / "p.html"
        self.page.write_text(page(), encoding="utf-8")

    def test_no_browser_returns_none_and_deliverable_keeps_file(self):
        with mock.patch.object(overflow, "find_browser", return_value=None):
            self.assertIsNone(overflow.measure(self.page))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertTrue(overflow.deliverable(self.page, "src.html", None))
        self.assertTrue(self.page.exists())
        self.assertIn("找不到 Chrome 或 Edge", err.getvalue())

    def test_empty_browser_stdout_counts_as_unavailable_browser(self):
        failed = subprocess.CompletedProcess([], 1, b"", b"Failed to create socket directory")
        err = io.StringIO()
        with mock.patch.object(overflow, "find_browser", return_value="/apps/browser"), \
                mock.patch.object(overflow.subprocess, "run", return_value=failed), \
                contextlib.redirect_stderr(err):
            self.assertIsNone(overflow.measure(self.page))
        self.assertIn("browser 開了但沒有交回頁面", err.getvalue())
        self.assertIn("Failed to create socket directory", err.getvalue())

    def test_temp_copy_fd_closed_and_cleaned_up(self):
        fds, real_mkstemp = [], tempfile.mkstemp

        def spy_mkstemp(*a, **k):
            fd, path = real_mkstemp(*a, **k)
            fds.append(fd)
            return fd, path

        ok_proc = subprocess.CompletedProcess([], 0, page(head=MEASURED_CLEAN).encode("utf-8"), b"")
        with mock.patch.object(overflow.tempfile, "mkstemp", spy_mkstemp), \
                mock.patch.object(overflow, "find_browser", return_value="browser"), \
                mock.patch.object(overflow.subprocess, "run", return_value=ok_proc):
            dom = overflow.render(self.page, width=1440)
        self.assertIsNotNone(dom)
        self.assertEqual(len(fds), 1)
        with self.assertRaises(OSError):
            os.fstat(fds[0])
        self.assertEqual([f.name for f in self.tmp.iterdir()], ["p.html"])

    def test_narrow_width_uses_iframe_wrapper_and_min_window_size(self):
        seen_cmd = []

        def fake_run(cmd, **kw):
            seen_cmd.extend(cmd)
            return subprocess.CompletedProcess(cmd, 0, page(head=MEASURED_CLEAN).encode("utf-8"), b"")

        with mock.patch.object(overflow, "find_browser", return_value="browser"), \
                mock.patch.object(overflow.subprocess, "run", side_effect=fake_run):
            overflow.render(self.page, width=390)
        self.assertTrue(any(arg == f"--window-size={overflow.MIN_WINDOW},{overflow.HEIGHT}" for arg in seen_cmd))
        self.assertTrue(seen_cmd[-1].endswith("/frame.html"))

    def test_deliverable_unlinks_output_when_overflow_found(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            ok = overflow.deliverable(self.page, "src.html", ["視窗寬 390px：整頁被撐寬 50px"])
        self.assertFalse(ok)
        self.assertFalse(self.page.exists())
        self.assertIn("1 處水平溢出", err.getvalue())


class CliTest(unittest.TestCase):
    def test_wrong_arg_count_prints_usage_and_returns_two(self):
        for argv in ([], ["a.html", "b.html"]):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(overflow.main(argv), 2)
                self.assertIn("overflow.py", err.getvalue())

    def test_exit_codes_match_measurement_outcome(self):
        with mock.patch.object(overflow, "measure", return_value=[]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(overflow.main(["p.html"]), 0)
            self.assertIn("沒有水平溢出", out.getvalue())

        with mock.patch.object(overflow, "measure", return_value=["視窗寬 1440px：超出"]):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(overflow.main(["p.html"]), 1)
            self.assertIn("1 處水平溢出", err.getvalue())

        with mock.patch.object(overflow, "measure", return_value=None):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(overflow.main(["p.html"]), 2)
            self.assertIn("找不到 Chrome 或 Edge", err.getvalue())


if __name__ == "__main__":
    unittest.main()
