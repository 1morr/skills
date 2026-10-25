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
TR = '<div class="tr"><p>判定係數 R² = 解釋了的變異 ÷ 總變異</p></div>'
FIG = TR + '<figure><img src="a.png" alt=""><figcaption>Classnote Topic 3 p.4</figcaption></figure>'
CHECK = '<details class="check"><summary>t 值怎麼算？</summary><p>b 除以 SE</p></details>'
WHY = '<div class="why"><p>F 是訊號除以雜訊</p></div>'
ORIGIN = '<table class="origin"><tr data-from="convention"><td>α = 0.05</td><td>慣例</td></tr></table>'
ANOVA = TR + '<figure id="anova"><img src="a.png"><figcaption>Minitab p.3</figcaption></figure>'


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
                src = page(f'<h2>一</h2>{TR}<FIGURE class="x">\n  <img alt="" src="a.png" />\n'
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
        body = (f'<h2>一</h2>{WHY}{ORIGIN}<div class="sheet"><p>{big}</p></div>'
                f"<table><tr><td>{big}</td></tr></table>"
                f'{TR}<figure><img src="a.png"><figcaption>p.2 {big}</figcaption></figure>')
        self.assertTrue(ok(page(body)), build.lint(page(body)))

    def test_translation_not_counted(self):
        big = "字" * (self.per * 2)
        self.assertTrue(ok(page(f'<h2>一</h2><div class="tr"><p>{big}</p></div>' + FIG.removeprefix(TR))))

    def test_unclosed_paragraphs_still_counted(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + "字" * self.per + "<p>多")))


class MethodRule(unittest.TestCase):
    """有 .calc 或 .sheet 的段落要有 .why 和 .origin。"""

    def test_calc_without_why_fails(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{ORIGIN}<div class="calc">F = 29.74</div>')))

    def test_sheet_without_origin_fails(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{WHY}<div class="sheet">α = 0.05</div>')))

    def test_blocks_in_another_section_do_not_count(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{WHY}{ORIGIN}<h2>二</h2><div class="calc">F</div>')))

    def test_section_without_method_needs_nothing(self):
        self.assertTrue(ok(page("<h2>一</h2><p>Topic 3 在做什麼</p>")))

    def test_formatting_variants_pass(self):
        variants = [
            f'<h2>一</h2>{WHY}{ORIGIN}<div class="calc">F</div>',
            f'<h2>一</h2><div class="calc">F</div>{ORIGIN}{WHY}',
            '<H2 class="x">二</H2><SECTION CLASS="wide why"><p>為什麼</p></SECTION>\n'
            '<div><table data-x="1" class="origin small"><tr data-from="convention"><td>0.05</td></tr></table></div>'
            '<div class="sheet big">F = 29.74</div>',
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                self.assertTrue(ok(page(body)), build.lint(page(body)))


class TranslationRule(unittest.TestCase):
    """每張圖前面緊接著譯文。"""

    def test_figure_without_translation_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><figure><img src="a.png"><figcaption>p.4</figcaption></figure>')))

    def test_translation_after_figure_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><figure><img src="a.png"><figcaption>p.4</figcaption></figure>' + TR)))

    def test_translation_separated_by_paragraph_fails(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{TR}<p>先看下面</p><figure><img src="a.png">'
                                 '<figcaption>p.4</figcaption></figure>')))

    def test_translation_inside_previous_sibling_fails(self):
        self.assertFalse(ok(page(f'<h2>一</h2><div>{TR}<p>別的</p></div><figure><img src="a.png">'
                                 '<figcaption>p.4</figcaption></figure>')))

    def test_formatting_variants_pass(self):
        variants = [
            '<h2>一</h2><P CLASS="x tr">譯文</P>\n  <!-- 註解 -->\n<figure><img src="a.png"><figcaption>p.4</figcaption></figure>',
            '<h2>一</h2><div class="why"><div class="tr">譯</div><figure class="w"><img src="a.png">'
            '<figcaption>p.4</figcaption></figure></div>',
            '<h2>一</h2><figure data-tr="none"><img src="a.png"><figcaption>殘差圖 p.5</figcaption></figure>',
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                self.assertTrue(ok(page(body)), build.lint(page(body)))


class OriginFigureRule(unittest.TestCase):
    """「數字從哪來」的每一列，要嘛連到這一段圈出它的圖，要嘛說明材料上看不到。"""

    def body(self, row, fig=ANOVA, between=""):
        return page(f'<h2>一</h2>{WHY}{fig}{between}<div class="calc">R²</div>'
                    f'<table class="origin"><tr><th>值</th><th>從哪來</th></tr>{row}</table>')

    def test_row_without_figure_fails(self):
        self.assertFalse(ok(self.body('<tr><td>10556.1</td><td>Minitab SS</td></tr>')))

    def test_link_to_missing_figure_fails(self):
        self.assertFalse(ok(self.body('<tr><td>10556.1</td><td><a href="#coef">圖</a></td></tr>')))

    def test_link_to_figure_in_other_section_fails(self):
        src = page(f'<h2>零</h2>{ANOVA}<h2>一</h2>{WHY}<div class="calc">R²</div>'
                   '<table class="origin"><tr><td>10556.1</td><td><a href="#anova">圖</a></td></tr></table>')
        self.assertFalse(ok(src))

    def test_unknown_from_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="minitab"><td>10556.1</td></tr>')))

    def test_formatting_variants_pass(self):
        rows = [
            '<tr><td>10556.1</td><td>Minitab ANOVA 的 SS（<a href="#anova">圖</a>）</td></tr>',
            '<TR class="x"><td><a class="y" href="#anova">10556.1</a></td></TR>',
            '<tr data-from="calc"><td>0.9225</td><td>上一步算的</td></tr>',
            '<tr data-from="constant"><td>1</td><td>截距</td></tr>',
        ]
        for row in rows:
            with self.subTest(row=row[:40]):
                self.assertTrue(ok(self.body(row)), build.lint(self.body(row)))

    def test_figure_after_table_passes(self):
        src = page(f'<h2>一</h2>{WHY}<div class="calc">R²</div>'
                   '<table class="origin"><tr><td>10556.1</td><td><a href="#anova">圖</a></td></tr></table>' + ANOVA)
        self.assertTrue(ok(src), build.lint(src))


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
