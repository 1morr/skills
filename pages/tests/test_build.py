"""build.py 的閘門與組裝：每條規則都驗兩個方向。

違規要紅；只改無關的格式（大小寫、空白、屬性順序、引號）或把網址寫在讀者讀的地方，不能紅。

在 pages/ 執行：python -m unittest discover -s tests
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


class WithMermaid(unittest.TestCase):
    """找不到瀏覽器時的退路頁，也是交給無頭瀏覽器畫圖的草稿。"""

    def test_inlines_mermaid_before_body_end(self):
        out = build.with_mermaid(page(DIAGRAM), FAKE_LIB)
        tail = out[out.index("</pre>"):]
        self.assertIn("window.mermaid", tail)
        self.assertIn("mermaid.initialize(", tail)
        self.assertLess(tail.index("window.mermaid"), tail.index("mermaid.initialize("))
        self.assertTrue(out.rstrip().endswith("</body></html>"))

    def test_theme(self):
        self.assertIn('theme: "dark"', build.with_mermaid(page(DIAGRAM), FAKE_LIB, "dark"))
        self.assertIn("prefers-color-scheme", build.with_mermaid(page(DIAGRAM), FAKE_LIB))

    def test_script_end_inside_lib_does_not_close_element(self):
        out = build.with_mermaid(page(DIAGRAM), FAKE_LIB)

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
            build.with_mermaid(page(DIAGRAM), 'var s="<!--<script>";')

    def test_tarball_integrity(self):
        self.assertFalse(build.verify(b"not mermaid"))
        good = base64.b64encode(hashlib.sha512(b"x").digest()).decode()
        orig = build.MERMAID_SHA512
        try:
            build.MERMAID_SHA512 = good
            self.assertTrue(build.verify(b"x"))
        finally:
            build.MERMAID_SHA512 = orig


def svg(sid, word):
    return (f'<svg id="{sid}"><style>#{sid} .node{{fill:red}}</style>'
            f'<path marker-end="url(#{sid}_pointEnd)"/><text>{word}</text></svg>')


class Embed(unittest.TestCase):
    def test_both_themes_replace_source(self):
        out = build.embed(page(DIAGRAM + "<p>中間</p>" + DIAGRAM),
                          [svg("m1", "淺1"), svg("m2", "淺2")], [svg("m3", "深1"), svg("m4", "深2")])
        self.assertNotIn("flowchart", out)
        self.assertEqual(out.count('<span data-theme="light"><svg'), 2)
        self.assertEqual(out.count('<span data-theme="dark"><svg'), 2)
        self.assertLess(out.index("淺1"), out.index("深1"))
        self.assertLess(out.index("深1"), out.index("中間"))
        self.assertLess(out.index("中間"), out.index("淺2"))
        self.assertEqual(out.count(build.STATIC_CSS), 1)
        self.assertNotIn("<script", out)

    def test_svg_ids_are_unique_and_internal_refs_follow(self):
        # 兩次渲染撞到同一個 id：改名後各自的樣式和 marker 只指向自己
        out = build.embed(page(DIAGRAM), [svg("mermaid-1", "淺")], [svg("mermaid-1", "深")])
        self.assertNotIn("mermaid-1", out)
        for t in ("light", "dark"):
            sid = f"diagram-1-{t}"
            self.assertIn(f'id="{sid}"', out)
            self.assertIn(f"#{sid} .node", out)
            self.assertIn(f"url(#{sid}_pointEnd)", out)

    def test_keeps_start_tag_and_spelling(self):
        out = build.embed(page('<PRE id="d" class="diagram  mermaid">flowchart TB\nA</PRE>'),
                          [svg("a", "x")], [svg("b", "y")])
        self.assertIn('<PRE id="d" class="diagram  mermaid"><span data-theme="light">', out)
        self.assertTrue(out.endswith("</span></PRE></body></html>"))

    def test_other_pre_untouched(self):
        code = '<pre class="code">flowchart TB</pre>'
        out = build.embed(page(code + DIAGRAM), [svg("a", "x")], [svg("b", "y")])
        self.assertIn(code, out)

    def test_count_mismatch_is_refused(self):
        with self.assertRaises(ValueError):
            build.embed(page(DIAGRAM + DIAGRAM), [svg("a", "x")], [svg("b", "y")])

    def test_drawn_reads_svgs_in_order(self):
        dom = page(DRAWN + '<pre class="code">x</pre>' + DRAWN.replace("開始", "結束"))
        got = build.drawn(dom)
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0].startswith("<svg") and "開始" in got[0] and "結束" in got[1])


DRAWN = '<pre class="mermaid" data-processed="true"><svg id="m1"><g><text>開始</text></g></svg></pre>'
BROKEN = ('<pre class="mermaid" data-processed="true"><div id="dm2"><svg id="m2">'
          '<text class="error-text">Syntax error in text</text></svg></div></pre>')
UNDRAWN = '<pre class="mermaid">\nflowchart TB\n  A --> B\n</pre>'


class Render(unittest.TestCase):
    def test_all_drawn(self):
        self.assertEqual(build.render_problems(page(DRAWN + DRAWN), 2), [])

    def test_unrelated_markup_is_fine(self):
        # 屬性順序、class 大小寫與多餘空白、svg 外多包一層、頁上文字提到語法錯誤
        dom = page('<p>Syntax error 是 Mermaid 的錯誤訊息</p>'
                   '<PRE data-processed="true" class=" x  mermaid "><div><svg><text>甲</text></svg></div></PRE>'
                   '<pre class="code">Syntax error</pre>')
        self.assertEqual(build.render_problems(dom, 1), [])

    def test_not_drawn(self):
        problems = build.render_problems(page(DRAWN + UNDRAWN), 2)
        self.assertEqual(len(problems), 1)
        self.assertIn("第 2 張", problems[0])

    def test_syntax_error(self):
        problems = build.render_problems(page(BROKEN + DRAWN), 2)
        self.assertEqual(len(problems), 1)
        self.assertIn("第 1 張", problems[0])
        self.assertIn("語法錯誤", problems[0])

    def test_diagram_count_mismatch(self):
        self.assertEqual(len(build.render_problems(page(DRAWN), 2)), 1)


def drawn_dom(n=1):
    """假瀏覽器：照草稿裡的主題畫 n 張圖。"""
    def render(draft):
        theme = "dark" if 'theme: "dark"' in draft.read_text(encoding="utf-8") else "neutral"
        return page(DRAWN.replace("開始", theme) * n)
    return render


class Cli(unittest.TestCase):
    def run_main(self, name, html, *extra, render=drawn_dom()):
        d = Path(tempfile.mkdtemp())
        src = d / name
        src.write_text(html, encoding="utf-8")
        code = build.main([str(src), *extra], loader=lambda: FAKE_LIB, render=render)
        return code, d

    def test_writes_static_page_without_src_suffix(self):
        code, d = self.run_main("m0-src.html", page(DIAGRAM))
        self.assertEqual(code, 0)
        out = (d / "m0.html").read_text(encoding="utf-8")
        self.assertNotIn("window.mermaid", out)
        self.assertIn('<span data-theme="light"><svg id="diagram-1-light"', out)
        self.assertIn("neutral", out)
        self.assertIn("dark", out)

    def test_render_problem_fails_but_keeps_page(self):
        code, d = self.run_main("m0-src.html", page(DIAGRAM), render=lambda out: page(BROKEN))
        self.assertEqual(code, 1)
        self.assertIn("window.mermaid", (d / "m0.html").read_text(encoding="utf-8"))

    def test_no_browser_falls_back_to_inlined_mermaid(self):
        code, d = self.run_main("m0-src.html", page(DIAGRAM), render=lambda out: None)
        self.assertEqual(code, 1)
        self.assertIn("window.mermaid", (d / "m0.html").read_text(encoding="utf-8"))

    def test_no_diagram_skips_render(self):
        def boom(out):
            raise AssertionError("沒有圖就不該開瀏覽器")
        code, _ = self.run_main("m0-src.html", page("<p>沒有圖</p>"), render=boom)
        self.assertEqual(code, 0)

    def test_over_orca_remote_limit_fails_but_keeps_page(self):
        big = page("<p>" + "字" * (build.ORCA_REMOTE_MAX // 3 + 1) + "</p>")
        code, d = self.run_main("m0-src.html", big)
        self.assertEqual(code, 1)
        self.assertTrue((d / "m0.html").exists())
        code, _ = self.run_main("m0-src.html", page("<p>" + "字" * (build.ORCA_REMOTE_MAX // 3 - 100) + "</p>"))
        self.assertEqual(code, 0)

    def test_problems_write_nothing(self):
        code, d = self.run_main("m0-src.html", page('<script src="https://cdn.x/y.js"></script>'))
        self.assertEqual(code, 1)
        self.assertFalse((d / "m0.html").exists())

    def test_refuses_to_overwrite_source(self):
        code, d = self.run_main("m0.html", page(DIAGRAM))
        self.assertEqual(code, 1)
        self.assertIn("flowchart", (d / "m0.html").read_text(encoding="utf-8"))


@unittest.skipUnless(build.find_browser(), "本機沒有 Chrome 或 Edge")
class RealBrowser(unittest.TestCase):
    """用真的 Mermaid 和瀏覽器跑：錯誤圖示的樣子是 Mermaid 決定的，假 DOM 驗不到。"""

    def check(self, body, diagrams):
        d = Path(tempfile.mkdtemp())
        out = d / "p.html"
        out.write_text(build.with_mermaid(page(body), build.load_mermaid()), encoding="utf-8")
        return build.render_problems(build.render_dom(out), diagrams)

    def test_good_diagram_passes(self):
        self.assertEqual(self.check(DIAGRAM, 1), [])

    def test_cli_writes_small_static_page(self):
        d = Path(tempfile.mkdtemp())
        src = d / "p-src.html"
        src.write_text(page(DIAGRAM), encoding="utf-8")
        self.assertEqual(build.main([str(src)]), 0)
        out = (d / "p.html").read_text(encoding="utf-8")
        self.assertNotIn("<script", out)
        self.assertEqual(out.count("<svg"), 2)
        self.assertLess(len(out.encode("utf-8")), build.ORCA_REMOTE_MAX)

    def test_broken_diagram_is_caught(self):
        broken = '<pre class="mermaid">\nflowchart TB\n  A["開始" --> \n</pre>'
        problems = self.check(DIAGRAM + broken, 2)
        self.assertEqual(len(problems), 1)
        self.assertIn("第 2 張", problems[0])


if __name__ == "__main__":
    unittest.main()
