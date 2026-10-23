"""build.py 的規則閘門：每條規則都驗兩個方向。

違規要紅；只改無關的格式（空白、屬性順序、大小寫、標題文字）不能紅。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
spec = importlib.util.spec_from_file_location("build", SCRIPT)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
FIG = '<figure><img src="a.png" alt=""><figcaption>Classnote Topic 3 p.4</figcaption></figure>'
CHECK = '<details class="check"><summary>t 值怎麼算？</summary><p>b 除以 SE</p></details>'


def page(body, mode="read"):
    return f'<!doctype html><html><head><title>x</title></head><body data-mode="{mode}">{body}</body></html>'


def ok(src):
    return build.lint(src) == []


class ModeRule(unittest.TestCase):
    def test_missing_mode_fails(self):
        self.assertFalse(ok("<html><body><h2>一</h2><p>短</p></body></html>"))

    def test_both_modes_pass(self):
        self.assertTrue(ok(page("<h2>一</h2><p>短</p>", "read")))
        self.assertTrue(ok(page("<h2>一</h2><p>短</p>" + CHECK, "learn")))


class FigureRule(unittest.TestCase):
    def test_bare_img_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><img src="a.png">')))

    def test_caption_without_page_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><figure><img src="a.png"><figcaption>講義</figcaption></figure>')))

    def test_figure_without_caption_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><figure><img src="a.png"></figure>')))

    def test_caption_formatting_variants_pass(self):
        for cap in ("Classnote p.4", "Classnote p. 4", "課本 pp.315", "<b>講義</b> p.12（紅框）"):
            with self.subTest(cap=cap):
                src = page(f'<h2>一</h2><FIGURE class="x">\n  <img alt="" src="a.png" />\n'
                           f'<figcaption>{cap}</figcaption></FIGURE>')
                self.assertTrue(ok(src), build.lint(src))


class RemoteRule(unittest.TestCase):
    def test_remote_img_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><figure><img src="https://x.y/a.png"><figcaption>p.1</figcaption></figure>')))

    def test_remote_script_fails(self):
        self.assertFalse(ok(page('<script src="//cdn.x/y.js"></script><h2>一</h2>')))

    def test_plain_links_pass(self):
        self.assertTrue(ok(page('<h2>一</h2><p><a href="https://moodle.example/x">Moodle</a></p>')))


class LengthRule(unittest.TestCase):
    per, total = build.LIMITS["read"]

    def test_long_section_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + "字" * (self.per + 1) + "</p>")))

    def test_same_text_split_into_sections_passes(self):
        half = "字" * (self.per // 2 + 1)
        self.assertTrue(ok(page(f"<h2>一</h2><p>{half}</p><h2>二</h2><p>{half}</p>")))

    def test_whole_page_limit_fails(self):
        n = self.total // self.per + 1
        body = "".join(f"<h2>{i}</h2><p>{'字' * self.per}</p>" for i in range(n))
        self.assertFalse(ok(page(body)))

    def test_english_counts_words_not_letters(self):
        words = " ".join(["regression"] * (self.per - 5))
        self.assertTrue(ok(page(f"<h2>一</h2><p>{words}</p>")))

    def test_sheet_table_figure_not_counted(self):
        big = "字" * (self.per * 2)
        body = (f'<h2>一</h2><div class="sheet"><p>{big}</p></div>'
                f"<table><tr><td>{big}</td></tr></table>"
                f'<figure><img src="a.png"><figcaption>p.2 {big}</figcaption></figure>')
        self.assertTrue(ok(page(body)), build.lint(page(body)))

    def test_unclosed_paragraphs_still_counted(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + "字" * self.per + "<p>多")))


class ExerciseRule(unittest.TestCase):
    def test_read_with_check_fails(self):
        self.assertFalse(ok(page("<h2>一</h2>" + CHECK, "read")))

    def test_read_with_input_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><input type="text">', "read")))

    def test_read_with_plain_details_passes(self):
        self.assertTrue(ok(page("<h2>一</h2><details><summary>延伸</summary><p>可略過</p></details>", "read")))

    def test_learn_without_check_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><p>短</p>", "learn")))


class Output(unittest.TestCase):
    def test_build_inlines_numbers_and_styles(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.png").write_bytes(PNG)
            out = build.build(page("<h2>甲</h2><h3>乙</h3><h3 id='keep'>丙</h3><h2>丁</h2>" + FIG), Path(d))
        self.assertIn("data:image/png;base64,", out)
        self.assertNotIn('src="a.png"', out)
        self.assertIn('id="s1"><span class="num">§1</span> 甲', out)
        self.assertIn('id="s1-1"><span class="num">§1.1</span> 乙', out)
        self.assertIn("id='keep'><span class=\"num\">§1.2</span> 丙", out)
        self.assertIn('<span class="num">§2</span> 丁', out)
        self.assertIn("<style>", out)

    def test_main_refuses_to_write_on_violation(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "guide-src.html"
            src.write_text(page('<h2>一</h2><img src="a.png">'), encoding="utf-8")
            self.assertEqual(build.main([str(src)]), 1)
            self.assertFalse((Path(d) / "guide.html").exists())


if __name__ == "__main__":
    unittest.main()
