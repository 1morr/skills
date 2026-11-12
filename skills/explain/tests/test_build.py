"""build.py 的閘門與組裝：每條規則都驗兩個方向。

違規要紅；只改無關的格式（大小寫、空白、屬性順序、引號）或把網址寫在讀者讀的地方，不能紅。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import base64
import hashlib
import importlib.util
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
spec = importlib.util.spec_from_file_location("build", SCRIPT)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

DIAGRAM = '<pre class="mermaid">\nflowchart TB\n  A["開始"] --> B["結束"]\n</pre>'
FAKE_LIB = 'window.mermaid={initialize(){}};var s="</script>";'


def page(body="", head=""):
    return f'<!doctype html><html><head><meta charset="utf-8">{head}</head><body>{body}</body></html>'


def ok(src):
    return build.lint(src) == []


def never():
    raise AssertionError("沒有圖就不該載入 Mermaid")


class Lint(unittest.TestCase):
    def test_remote_script_src(self):
        self.assertFalse(ok(page('<script src="https://cdn.x/y.js"></script>')))
        self.assertFalse(ok(page("<SCRIPT defer SRC='//cdn.x/y.js'></SCRIPT>")))
        self.assertTrue(ok(page('<script src="y.js"></script>')))

    def test_remote_module_import(self):
        old = ('<script type="module">\n  import mermaid from '
               '"https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";\n</script>')
        self.assertFalse(ok(page(old)))
        self.assertFalse(ok(page("<script>import('//cdn.x/m.mjs')</script>")))
        self.assertFalse(ok(page('<script type="module">import "https://cdn.x/side.js"</script>')))
        self.assertTrue(ok(page('<script type="module">import { a } from "./a.js";</script>')))
        # 頁內 JS 用到網址字串但沒載入東西
        self.assertTrue(ok(page('<script>const u = new URL("https://x.y/");</script>')))

    def test_remote_stylesheet(self):
        self.assertFalse(ok(page(head='<link rel="stylesheet" href="https://fonts.x/css">')))
        self.assertFalse(ok(page(head='<link href="//fonts.x/css" rel=stylesheet>')))
        self.assertFalse(ok(page(head='<style>@import url("https://fonts.x/css");</style>')))
        self.assertFalse(ok(page(head="<style>body{background:url(//x.y/a.png)}</style>")))
        self.assertTrue(ok(page(head="<style>body{background:url(data:image/png;base64,AA==)}</style>")))

    def test_remote_media(self):
        self.assertFalse(ok(page('<img alt="" src="https://x.y/a.png">')))
        self.assertFalse(ok(page('<iframe src="https://x.y/"></iframe>')))
        self.assertTrue(ok(page('<img src="data:image/png;base64,AA==" alt="">')))

    def test_urls_readers_read_are_fine(self):
        self.assertTrue(ok(page('<p><a href="https://github.com/x/y">repo</a></p>')))
        # 頁上解說舊寫法的程式碼，不是真的 script
        self.assertTrue(ok(page('<pre><code>import mermaid from "https://cdn.x/m.mjs"</code></pre>')))
        self.assertTrue(ok(page('<p>import 一個 "https://x.y" 的模組</p>')))

    def test_page_loading_mermaid_itself(self):
        self.assertFalse(ok(page(DIAGRAM + '<script>mermaid.initialize({startOnLoad:true})</script>')))
        self.assertTrue(ok(page(DIAGRAM + '<p>mermaid.initialize 是 build.py 放的</p>')))


class Build(unittest.TestCase):
    def test_inlines_mermaid_before_body_end(self):
        out = build.build(page(DIAGRAM), lambda: FAKE_LIB)
        tail = out[out.index("</pre>"):]
        self.assertIn("window.mermaid", tail)
        self.assertIn("mermaid.initialize(", tail)
        self.assertLess(tail.index("window.mermaid"), tail.index("mermaid.initialize("))
        self.assertTrue(out.rstrip().endswith("</body></html>"))

    def test_class_spelling_does_not_matter(self):
        out = build.build(page('<PRE id="d" class="diagram  mermaid">flowchart TB\nA</PRE>'), lambda: FAKE_LIB)
        self.assertIn("window.mermaid", out)

    def test_no_diagram_no_mermaid(self):
        src = page("<p>沒有圖</p>")
        self.assertEqual(build.build(src, never), src)
        self.assertEqual(build.build(page('<pre class="code">flowchart</pre>'), never),
                         page('<pre class="code">flowchart</pre>'))

    def test_script_end_inside_lib_does_not_close_element(self):
        out = build.build(page(DIAGRAM), lambda: FAKE_LIB)

        class Scripts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.bodies, self.inside = [], False

            def handle_starttag(self, tag, attrs):
                self.inside = tag == "script"

            def handle_data(self, data):
                if self.inside:
                    self.bodies.append(data)

            def handle_endtag(self, tag):
                self.inside = False

        p = Scripts()
        p.feed(out)
        self.assertIn('var s="<\\/script>";', p.bodies[0])
        self.assertIn("mermaid.initialize(", p.bodies[1])

    def test_lib_containing_script_start_is_refused(self):
        with self.assertRaises(ValueError):
            build.build(page(DIAGRAM), lambda: 'var s="<!--<script>";')

    def test_tarball_integrity(self):
        self.assertFalse(build.verify(b"not mermaid"))
        good = base64.b64encode(hashlib.sha512(b"x").digest()).decode()
        orig = build.MERMAID_SHA512
        try:
            build.MERMAID_SHA512 = good
            self.assertTrue(build.verify(b"x"))
        finally:
            build.MERMAID_SHA512 = orig


class Cli(unittest.TestCase):
    def run_main(self, name, html, *extra):
        d = Path(tempfile.mkdtemp())
        src = d / name
        src.write_text(html, encoding="utf-8")
        code = build.main([str(src), *extra], loader=lambda: FAKE_LIB)
        return code, d

    def test_writes_page_without_src_suffix(self):
        code, d = self.run_main("m0-src.html", page(DIAGRAM))
        self.assertEqual(code, 0)
        self.assertIn("window.mermaid", (d / "m0.html").read_text(encoding="utf-8"))

    def test_problems_write_nothing(self):
        code, d = self.run_main("m0-src.html", page('<script src="https://cdn.x/y.js"></script>'))
        self.assertEqual(code, 1)
        self.assertFalse((d / "m0.html").exists())

    def test_refuses_to_overwrite_source(self):
        code, d = self.run_main("m0.html", page(DIAGRAM))
        self.assertEqual(code, 1)
        self.assertNotIn("window.mermaid", (d / "m0.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
