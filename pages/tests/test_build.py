"""build.py 的閘門與組裝：每條規則都驗兩個方向。

違規要紅；只改無關的格式（大小寫、空白、屬性順序、引號）或把網址寫在讀者讀的地方，不能紅。

在 pages/ 執行：python -m unittest discover -s tests
"""

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

def page(body="", head=""):
    return f'<!doctype html><html><head><meta charset="utf-8">{head}</head><body>{body}</body></html>'


def ok(src):
    return build.lint(src) == []


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

    def test_page_defining_its_own_tokens(self):
        self.assertFalse(ok(page(head="<style>:root{--paper:#fff;--ink:#000}</style>")))
        self.assertFalse(ok(page(head="<STYLE>\n:root {\n  --font-doc : Georgia;\n}\n</STYLE>")))
        # 用變數、定義自己的變數、補自己的 class 都可以；內文提到變數名也可以
        self.assertTrue(ok(page("<p>顏色取 <code>--paper: …</code></p>",
                                "<style>.mine{color:var(--ink);--gap:1rem;background:var(--paper)}</style>")))

    def test_page_loading_mermaid_itself(self):
        self.assertFalse(ok(page(DIAGRAM + '<script>mermaid.initialize({startOnLoad:true})</script>')))
        self.assertTrue(ok(page(DIAGRAM + '<p>mermaid.initialize 是 build.py 放的</p>')))


class Build(unittest.TestCase):
    def test_css_then_libs_then_diagram_js_before_body_end(self):
        out = build.build(page(DIAGRAM))
        tail = out[out.index("</pre>"):]
        order = [tail.index(x) for x in ("pre.dz-open", build.MERMAID.url, build.PANZOOM.url, "mermaid.run(")]
        self.assertEqual(order, sorted(order))
        self.assertTrue(out.rstrip().endswith("</body></html>"))

    def test_class_spelling_does_not_matter(self):
        out = build.build(page('<PRE id="d" class="diagram  mermaid">flowchart TB\nA</PRE>'))
        self.assertIn(build.MERMAID.url, out)

    def test_no_diagram_no_libs(self):
        for src in (page("<p>沒有圖</p>"), page('<pre class="code">flowchart</pre>')):
            out = build.build(src)
            self.assertNotIn("<script", out)
            self.assertNotIn("dz-bar", out)

    def test_shared_styles_come_first_in_head(self):
        out = build.build(page("<p>內容</p>", "<style>.mine{color:red}</style>"))
        head = out[:out.index("</head>")]
        order = [head.index(x) for x in ("--paper:", "main {", ".mine{color:red}")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(out.count("--paper: oklch(0.985"), 1)
        # 沒有 <head> 的頁也拿得到樣式
        self.assertIn("--paper:", build.build("<p>只有一段</p>"))
        self.assertIn("--paper:", build.build("<!DOCTYPE html><HTML lang=zh><body><p>x</p></body></HTML>"))

    def test_libs_are_pinned_with_integrity(self):
        out = build.build(page(DIAGRAM))

        class Scripts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.remote = []

            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag == "script" and a.get("src"):
                    self.remote.append(a)

        p = Scripts()
        p.feed(out)
        self.assertEqual([a["src"] for a in p.remote], [
            "https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.min.js",
            "https://cdn.jsdelivr.net/npm/@panzoom/panzoom@4.6.2/dist/panzoom.min.js"])
        for a in p.remote:
            # 沒有 crossorigin 時瀏覽器不驗 integrity；版本沒釘死時 CDN 換了檔 integrity 就會對不上
            self.assertRegex(a["integrity"], r"^sha384-[A-Za-z0-9+/]{64}$")
            self.assertEqual(a["crossorigin"], "anonymous")
            self.assertRegex(a["src"], r"@\d+\.\d+\.\d+/")

    def test_script_end_inside_inlined_js_does_not_close_element(self):
        self.assertEqual(build.inline_script('var s="</script>";'), '<script>var s="<\\/script>";</script>')
        self.assertEqual(build.inline_script("var a = 1 < 2;"), "<script>var a = 1 < 2;</script>")

    def test_inlined_js_containing_script_start_is_refused(self):
        with self.assertRaises(ValueError):
            build.inline_script('var s="<!--<script>";')


BAR = '<span class="dz-bar"><button class="panzoom-exclude">+</button></span>'
DRAWN = ('<pre class="mermaid" data-processed="true"><span class="dz-stage"><svg id="m1"><g><text>開始</text>'
         '</g></svg></span>' + BAR + '</pre>')
BROKEN = ('<pre class="mermaid" data-processed="true"><div id="dm2"><svg id="m2">'
          '<text class="error-text">Syntax error in text</text></svg></div></pre>')
UNDRAWN = '<pre class="mermaid">\nflowchart TB\n  A --> B\n</pre>'
NO_ZOOM = '<pre class="mermaid" data-processed="true"><svg id="m3"><text>開始</text></svg></pre>'


MEASURED = '<meta name="overflow-report" content="[]">'
WIDE = ('<meta name="overflow-report" content="[{&quot;box&quot;:&quot;整頁&quot;,&quot;over&quot;:120,&quot;items&quot;:'
        '[{&quot;el&quot;:&quot;span.src&quot;,&quot;over&quot;:120,&quot;text&quot;:&quot;很長的來源&quot;}]}]">')


def drawn(n=1):
    return lambda out, width=1440: page(DRAWN * n, MEASURED)


class Render(unittest.TestCase):
    def test_all_drawn(self):
        self.assertEqual(build.render_problems(page(DRAWN + DRAWN), 2), [])

    def test_unrelated_markup_is_fine(self):
        # 屬性順序、class 大小寫與多餘空白、svg 外多包一層、頁上文字提到語法錯誤
        dom = page('<p>Syntax error 是 Mermaid 的錯誤訊息</p>'
                   '<PRE data-processed="true" class=" x  mermaid "><div><svg><text>甲</text></svg></div>'
                   '<span class=" dz-bar  x"></span></PRE>'
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

    def test_zoom_not_attached(self):
        problems = build.render_problems(page(DRAWN + NO_ZOOM), 2)
        self.assertEqual(len(problems), 1)
        self.assertIn("第 2 張", problems[0])
        self.assertIn("縮放", problems[0])
        # 按鈕列在 pre 外面不算
        self.assertEqual(len(build.render_problems(page(NO_ZOOM + BAR), 1)), 1)

    def test_diagram_count_mismatch(self):
        self.assertEqual(len(build.render_problems(page(DRAWN), 2)), 1)


class Cli(unittest.TestCase):
    def run_main(self, name, html, *extra, render=drawn()):
        d = Path(tempfile.mkdtemp())
        src = d / name
        src.write_text(html, encoding="utf-8")
        code = build.main([str(src), *extra], render=render)
        return code, d

    def test_writes_page_without_src_suffix(self):
        code, d = self.run_main("m0-src.html", page(DIAGRAM))
        self.assertEqual(code, 0)
        self.assertIn(build.MERMAID.url, (d / "m0.html").read_text(encoding="utf-8"))

    def test_render_problem_fails_but_keeps_page(self):
        code, d = self.run_main("m0-src.html", page(DIAGRAM), render=lambda out, width=1440: page(BROKEN, MEASURED))
        self.assertEqual(code, 1)
        self.assertTrue((d / "m0.html").exists())

    def test_no_browser_fails(self):
        code, d = self.run_main("m0-src.html", page(DIAGRAM), render=lambda out, width=1440: None)
        self.assertEqual(code, 1)
        self.assertTrue((d / "m0.html").exists())

    def test_no_diagram_is_still_measured_at_every_width(self):
        seen = []

        def render(out, width):
            seen.append(width)
            return page("<p>沒有圖</p>", MEASURED)
        code, d = self.run_main("m0-src.html", page("<p>沒有圖</p>"), render=render)
        self.assertEqual(code, 0)
        self.assertEqual(seen, list(build.overflow.WIDTHS))
        self.assertEqual((d / "m0.html").read_text(encoding="utf-8"), build.build(page("<p>沒有圖</p>")))

    def test_overflow_at_any_width_writes_nothing(self):
        for bad in build.overflow.WIDTHS:
            with self.subTest(bad):
                code, d = self.run_main("m0-src.html", page(DIAGRAM),
                                        render=lambda out, width, bad=bad: page(DRAWN, WIDE if width == bad else MEASURED))
                self.assertEqual(code, 1)
                self.assertFalse((d / "m0.html").exists())

    def test_measurement_that_never_ran_writes_nothing(self):
        code, d = self.run_main("m0-src.html", page(DIAGRAM), render=lambda out, width=1440: page(DRAWN))
        self.assertEqual(code, 1)
        self.assertFalse((d / "m0.html").exists())

    def test_problems_write_nothing(self):
        code, d = self.run_main("m0-src.html", page('<script src="https://cdn.x/y.js"></script>'))
        self.assertEqual(code, 1)
        self.assertFalse((d / "m0.html").exists())

    def test_refuses_to_overwrite_source(self):
        code, d = self.run_main("m0.html", page(DIAGRAM))
        self.assertEqual(code, 1)
        self.assertNotIn(build.MERMAID.url, (d / "m0.html").read_text(encoding="utf-8"))


@unittest.skipUnless(build.find_browser(), "本機沒有 Chrome 或 Edge")
class RealBrowser(unittest.TestCase):
    """用真的 Mermaid、Panzoom（從 CDN 載入，integrity 也在這裡驗到）、diagram.js 和瀏覽器跑：
    錯誤圖示的樣子是 Mermaid 決定的，假 DOM 驗不到。要連得到 cdn.jsdelivr.net。"""

    def check(self, body, diagrams):
        d = Path(tempfile.mkdtemp())
        out = d / "p.html"
        out.write_text(build.build(page(body)), encoding="utf-8")
        return build.render_problems(build.render_dom(out), diagrams)

    def test_good_diagram_passes(self):
        self.assertEqual(self.check(DIAGRAM, 1), [])

    def test_broken_diagram_is_caught(self):
        broken = '<pre class="mermaid">\nflowchart TB\n  A["開始" --> \n</pre>'
        problems = self.check(DIAGRAM + broken, 2)
        self.assertEqual(len(problems), 1)
        self.assertIn("第 2 張", problems[0])


@unittest.skipUnless(build.find_browser(), "本機沒有 Chrome 或 Edge")
class RealOverflow(unittest.TestCase):
    """溢出要在真的瀏覽器裡量：版面是瀏覽器排的。"""

    LONG = "來源" * 300
    STYLE = "<style>main{max-width:40rem;margin:0 auto}.src{white-space:nowrap}.pane{height:100vh;overflow-y:auto}</style>"

    def measure(self, body):
        d = Path(tempfile.mkdtemp())
        out = d / "p.html"
        out.write_text(page(f"<main>{body}</main>", self.STYLE), encoding="utf-8")
        return build.overflow.measure(out)

    def test_unbreakable_label_is_caught_and_named(self):
        found = self.measure(f'<p>前文 <span class="src">{self.LONG}</span></p>')
        self.assertTrue(found)
        self.assertIn("span.src", found[0])

    def test_wide_content_in_its_own_scroller_is_fine(self):
        self.assertEqual(self.measure(f'<div style="overflow-x:auto"><span class="src">{self.LONG}</span></div>'), [])
        self.assertEqual(self.measure(f"<p>{self.LONG}</p>" * 3), [])

    def test_folded_details_are_opened_before_measuring(self):
        self.assertTrue(self.measure(f'<details><summary>摺起來</summary><span class="src">{self.LONG}</span></details>'))

    def test_pane_that_scrolls_vertically_is_caught(self):
        tall = "<p>一段</p>" * 200
        found = self.measure(f'<div class="pane">{tall}<span class="src">{self.LONG}</span></div>')
        self.assertTrue(any("div.pane" in p for p in found), found)

    def test_phone_width_is_really_measured(self):
        # 450px 寬的一塊：在 1440 和無頭 Chrome 最窄的 500px 視窗都放得下，只有真的 390px 才超出
        found = self.measure('<div class="block" style="width:450px;height:20px"></div>')
        self.assertEqual(len(found), 1, found)
        self.assertIn("390px", found[0])
        self.assertIn("div.block", found[0])

    def test_probe_is_not_left_in_the_page(self):
        d = Path(tempfile.mkdtemp())
        out = d / "p.html"
        out.write_text(page("<p>短</p>"), encoding="utf-8")
        build.overflow.measure(out)
        self.assertEqual(out.read_text(encoding="utf-8"), page("<p>短</p>"))
        self.assertEqual([f.name for f in d.iterdir()], ["p.html"])


if __name__ == "__main__":
    unittest.main()
