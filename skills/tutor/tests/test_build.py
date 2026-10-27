"""build.py 的規則閘門：每條規則都驗兩個方向。

違規要紅；只改無關的格式（空白、屬性順序、大小寫、標題文字）不能紅。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import base64
import importlib.util
import re
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
CALC = ('<div class="calc" id="c1"><p class="formula"><i>R</i>² = SSR / SST</p>'
        '<p class="subst">= 10556.1 / 11443.3 = 0.9225</p></div>')
ANOVA = TR + '<figure id="anova"><img src="a.png"><figcaption>Minitab p.3</figcaption></figure>'
SUMMARY = '<div class="summary"><ul><li>R² 是解釋了的比例</li></ul></div>'
RECAP = '<h2 class="recap">總結</h2><table><tr><td>看到什麼</td><td>結論</td></tr></table>'
COVER = ('<details><summary>看整頁</summary>' + TR +
         '<figure class="page"><img src="a.png"><figcaption>Cover p.1</figcaption></figure></details>')


def close_sections(body):
    """每個 h2 段落結尾補上總結，頁尾補上 topic 總結，讓其他規則的測試只管自己那條。"""
    starts = [m.start() for m in re.finditer(r"<h2[\s>]", body, re.I)]
    for pos in reversed(starts[1:]):
        body = body[:pos] + SUMMARY + body[pos:]
    return body + (SUMMARY if starts else "") + RECAP


def page(body, mode="read", pages="Cover p.1", cover=COVER, close=True):
    """整頁 HTML。預設在第一個 h2 之前放一張整頁圖滿足頁數覆蓋，並補上總結。"""
    if close:
        body = close_sections(body)
    return (f'<!doctype html><html><head><title>x</title></head>'
            f'<body data-mode="{mode}" data-pages="{pages}">{cover}{body}</body></html>')


def ok(src):
    return build.lint(src) == []


class ModeRule(unittest.TestCase):
    def test_missing_mode_fails(self):
        self.assertFalse(ok("<html><body><h2>一</h2><p>短</p></body></html>"))

    def test_both_modes_pass(self):
        for mode in ("read", "learn"):
            with self.subTest(mode=mode):
                self.assertTrue(ok(page("<h2>一</h2><p>短</p>", mode)), build.lint(page("<h2>一</h2><p>短</p>", mode)))


class FigureRule(unittest.TestCase):
    def test_bare_img_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><img src="a.png">')))

    def test_caption_without_page_fails(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{TR}<figure><img src="a.png"><figcaption>講義</figcaption></figure>')))

    def test_figure_without_caption_fails(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{TR}<figure><img src="a.png"></figure>')))

    def test_caption_formatting_variants_pass(self):
        for cap in ("Classnote p.4", "Classnote p. 4", "課本 pp.315", "<b>講義</b> p.12（紅框）"):
            with self.subTest(cap=cap):
                src = page(f'<h2>一</h2>{TR}<FIGURE class="x">\n  <img alt="" src="a.png" />\n'
                           f'<figcaption>{cap}</figcaption></FIGURE>')
                self.assertTrue(ok(src), build.lint(src))


class RemoteRule(unittest.TestCase):
    def test_remote_img_fails(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{TR}<figure><img src="https://x.y/a.png"><figcaption>p.1</figcaption></figure>')))

    def test_remote_script_fails(self):
        self.assertFalse(ok(page('<script src="//cdn.x/y.js"></script><h2>一</h2>')))

    def test_plain_links_pass(self):
        self.assertTrue(ok(page('<h2>一</h2><p><a href="https://moodle.example/x">Moodle</a></p>')))


class LengthRule(unittest.TestCase):
    per = build.PER_SECTION

    def test_long_section_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + "字" * (self.per + 1) + "</p>")))

    def test_same_text_split_into_sections_passes(self):
        half = "字" * (self.per // 2 + 1)
        self.assertTrue(ok(page(f"<h2>一</h2><p>{half}</p><h2>二</h2><p>{half}</p>")))

    def test_no_whole_page_limit(self):
        body = "".join(f"<h2>{i}</h2><p>{'字' * (self.per - 20)}</p>" for i in range(30))
        self.assertTrue(ok(page(body)), build.lint(page(body))[:2])

    def test_english_counts_words_not_letters(self):
        words = " ".join(["regression"] * (self.per - 20))
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
        self.assertFalse(ok(page(f'<h2>一</h2>{ORIGIN}{CALC}')))

    def test_sheet_without_origin_fails(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{WHY}<div class="sheet">α = 0.05</div>')))

    def test_blocks_in_another_section_do_not_count(self):
        self.assertFalse(ok(page(f'<h2>一</h2>{WHY}{ORIGIN}<h2>二</h2>{CALC}')))

    def test_section_without_method_needs_nothing(self):
        self.assertTrue(ok(page("<h2>一</h2><p>Topic 3 在做什麼</p>")))

    def test_formatting_variants_pass(self):
        variants = [
            f'<h2>一</h2>{WHY}{ORIGIN}{CALC}',
            f'<h2>一</h2>{CALC}{ORIGIN}{WHY}',
            '<H2 class="x">二</H2><SECTION CLASS="wide why"><p>為什麼</p></SECTION>\n'
            '<div><table data-x="1" class="origin small"><tr data-from="convention"><td>0.05</td></tr></table></div>'
            '<div class="sheet big">F = 29.74</div>',
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                self.assertTrue(ok(page(body)), build.lint(page(body)))


class TranslationRule(unittest.TestCase):
    """每張圖前面緊接著譯文，整頁圖之後的小截圖也一樣。"""

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

    def test_crop_after_page_figure_still_needs_translation(self):
        self.assertFalse(ok(page(f'<h2>p.5</h2>{COVER}<h3>R²</h3><figure><img src="a.png">'
                                 '<figcaption>p.5（R² 那塊）</figcaption></figure>')))

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


class OriginRule(unittest.TestCase):
    """「數字從哪來」的每一列：材料上的數字連到圈出它的圖，算出來的連到寫出算式的 .calc。"""

    def body(self, row, fig=ANOVA, calc=CALC):
        return page(f'<h2>一</h2>{WHY}{fig}{calc}'
                    f'<table class="origin"><tr><th>值</th><th>從哪來</th></tr>{row}</table>')

    def test_row_without_figure_fails(self):
        self.assertFalse(ok(self.body('<tr><td>10556.1</td><td>Minitab SS</td></tr>')))

    def test_link_to_missing_target_fails(self):
        self.assertFalse(ok(self.body('<tr><td>10556.1</td><td><a href="#coef">圖</a></td></tr>')))

    def test_link_to_figure_in_other_section_fails(self):
        src = page(f'<h2>零</h2>{ANOVA}<h2>一</h2>{WHY}{CALC}'
                   '<table class="origin"><tr><td>10556.1</td><td><a href="#anova">圖</a></td></tr></table>')
        self.assertFalse(ok(src))

    def test_unknown_from_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="minitab"><td>10556.1</td></tr>')))

    def test_calc_row_without_link_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="calc"><td>0.9225</td><td>上一步算的</td></tr>')))

    def test_calc_row_linked_to_figure_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="calc"><td>0.9225</td><td><a href="#anova">圖</a></td></tr>')))

    def test_formatting_variants_pass(self):
        rows = [
            '<tr><td>10556.1</td><td>Minitab ANOVA 的 SS（<a href="#anova">圖</a>）</td></tr>',
            '<TR class="x"><td><a class="y" href="#anova">10556.1</a></td></TR>',
            '<tr data-from="calc"><td>0.9225</td><td>上面算的（<a href="#c1">算式</a>）</td></tr>',
            '<tr class="z" data-from="calc"><td><A HREF="#c1">0.9225</A></td></tr>',
            '<tr data-from="constant"><td>1</td><td>截距</td></tr>',
        ]
        for row in rows:
            with self.subTest(row=row[:40]):
                self.assertTrue(ok(self.body(row)), build.lint(self.body(row)))

    def test_figure_after_table_passes(self):
        src = page(f'<h2>一</h2>{WHY}{CALC}'
                   '<table class="origin"><tr><td>10556.1</td><td><a href="#anova">圖</a></td></tr></table>' + ANOVA)
        self.assertTrue(ok(src), build.lint(src))


class CalcRule(unittest.TestCase):
    """每個 .calc 都寫出公式，再代入數字；不能只寫答案或「用 §N 的公式」。"""

    def body(self, calc):
        return page(f'<h2>一</h2>{WHY}{ORIGIN}{calc}')

    def test_answer_only_fails(self):
        self.assertFalse(ok(self.body('<div class="calc">R² = 0.9225</div>')))

    def test_reference_instead_of_formula_fails(self):
        self.assertFalse(ok(self.body('<div class="calc"><p class="formula">用 §1 的公式</p>'
                                      '<p class="subst">= 10556.1 / 11443.3 = 0.9225</p></div>')))

    def test_formula_without_numbers_fails(self):
        self.assertFalse(ok(self.body('<div class="calc"><p class="formula">R² = SSR / SST</p>'
                                      '<p class="subst">= 解釋的 / 全部</p></div>')))

    def test_formatting_variants_pass(self):
        variants = [
            CALC,
            '<DIV CLASS="calc wide"><span class="formula">MAD ＝ (1/<var>n</var>) Σ|e|</span><br>'
            '<span class="x subst">= (8 + 4) / 2</span></DIV>',
            '<div class="calc"><div class="formula"><span class="frac"><span>a</span><span>b</span></span> = r</div>'
            '<div class="subst"><span class="frac"><span>16</span><span>40</span></span> = 0.4</div></div>',
        ]
        for calc in variants:
            with self.subTest(calc=calc[:40]):
                self.assertTrue(ok(self.body(calc)), build.lint(self.body(calc)))


class DefRule(unittest.TestCase):
    """術語寫成 .def：一個 <dfn>，加上「怎樣才算」的 .test。"""

    def body(self, d):
        return page(f'<h2>一</h2>{d}')

    def test_dfn_outside_def_fails(self):
        self.assertFalse(ok(self.body('<p><dfn>趨勢</dfn>是長期方向</p>')))

    def test_def_without_test_fails(self):
        self.assertFalse(ok(self.body('<div class="def"><p><dfn>趨勢</dfn>：長期方向</p></div>')))

    def test_def_with_empty_test_fails(self):
        self.assertFalse(ok(self.body('<div class="def"><p><dfn>趨勢</dfn>：長期方向</p><p class="test"> </p></div>')))

    def test_two_terms_in_one_def_fails(self):
        self.assertFalse(ok(self.body('<div class="def"><p><dfn>趨勢</dfn>、<dfn>季節</dfn></p>'
                                      '<p class="test">整體往上</p></div>')))

    def test_formatting_variants_pass(self):
        variants = [
            '<div class="def"><p><dfn>趨勢</dfn>：長期方向</p><p class="test">後半平均明顯比前半高</p></div>',
            '<ASIDE CLASS="x def"><DFN>趨勢（trend）</DFN><ul class="test"><li>圖整體往上</li></ul></ASIDE>',
            '<div class="def">\n  <p><b><dfn>平穩</dfn></b></p>\n  <div class="test"><p>沒有趨勢</p></div>\n</div>',
        ]
        for d in variants:
            with self.subTest(d=d[:40]):
                self.assertTrue(ok(self.body(d)), build.lint(self.body(d)))


class SummaryRule(unittest.TestCase):
    """每個 h2 段落以 .summary 結尾；最後一段是 h2.recap。"""

    def test_section_without_summary_fails(self):
        self.assertFalse(ok(page(f"<h2>一</h2><p>內容</p>{RECAP}", close=False)))

    def test_summary_not_last_fails(self):
        self.assertFalse(ok(page(f"<h2>一</h2>{SUMMARY}<h3>後面</h3><p>還有</p>{RECAP}", close=False)))

    def test_summary_only_in_next_section_fails(self):
        self.assertFalse(ok(page(f"<h2>一</h2><p>內容</p><h2>二</h2>{SUMMARY}{RECAP}", close=False)))

    def test_missing_recap_fails(self):
        self.assertFalse(ok(page(f"<h2>一</h2>{SUMMARY}", close=False)))

    def test_recap_not_last_fails(self):
        self.assertFalse(ok(page(f"{RECAP}<h2>一</h2>{SUMMARY}", close=False)))

    def test_formatting_variants_pass(self):
        variants = [
            f"<h2>一</h2><p>內容</p>{SUMMARY}{RECAP}",
            f'<h2>一</h2><p>內容</p><SECTION CLASS="x summary"><p>記住</p></SECTION>\n  <!-- 註解 -->\n{RECAP}',
            f'<H2 id="a">一</H2>{SUMMARY}<h2 class="x recap" id="r">總結</h2><p>判斷表</p>',
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                src = page(body, close=False)
                self.assertTrue(ok(src), build.lint(src))


class PageFoldRule(unittest.TestCase):
    """整頁圖和整頁譯文收進 <details>，data-pages 的每一頁都要有。"""

    def whole(self, name, n, cls="page", fold=True):
        fig = f'{TR}<figure class="{cls}"><img src="a.png"><figcaption>{name} p.{n}</figcaption></figure>'
        if fold:
            fig = f"<details><summary>看整頁</summary>{fig}</details>"
        return f"<h2>{name} p.{n}</h2>{fig}"

    def test_unfolded_page_fails(self):
        self.assertFalse(ok(page(self.whole("Topic 3", 1, fold=False), pages="Topic 3 p.1", cover="")))

    def test_missing_declaration_fails(self):
        self.assertFalse(ok(page("<h2>一</h2>", pages="")))

    def test_missing_page_fails(self):
        body = self.whole("Topic 3", 1) + self.whole("Topic 3", 3)
        self.assertFalse(ok(page(body, pages="Topic 3 p.1-3", cover="")))

    def test_p10_does_not_cover_p1(self):
        self.assertFalse(ok(page(self.whole("Topic 4", 10), pages="Topic 4 p.1", cover="")))

    def test_other_file_same_page_does_not_count(self):
        self.assertFalse(ok(page(self.whole("Topic 3 Eg", 1), pages="Topic 4 p.1", cover="")))

    def test_crop_is_not_a_whole_page(self):
        self.assertFalse(ok(page(self.whole("Topic 3", 1, cls="crop"), pages="Topic 3 p.1", cover="")))

    def test_unparsable_item_fails(self):
        self.assertFalse(ok(page(self.whole("Topic 3", 1), pages="Topic 3 第一頁", cover="")))

    def test_formatting_variants_pass(self):
        body = (self.whole("Classnote Topic 3", 1) + self.whole("Classnote Topic 3", 2, cls="wide page")
                + f'<h2>x</h2><DETAILS class="full"><summary>整頁</summary><div>{TR}<FIGURE CLASS="page">'
                  '<img src="a.png"><figcaption>2023 Topic 4 Summary p. 10（整頁）</figcaption></FIGURE></div></DETAILS>')
        for pages in ("Classnote Topic 3 p.1-2; Topic 4 Summary p.10",
                      " Classnote Topic 3 p. 1 - 2 ;Topic 4 Summary p.10; ",
                      "Topic 4 Summary p.10; Classnote Topic 3 p.1; Classnote Topic 3 p.2"):
            with self.subTest(pages=pages):
                src = page(body, pages=pages, cover="")
                self.assertTrue(ok(src), build.lint(src))


class RefRule(unittest.TestCase):
    """內文的 §N、§N.M 要指向真的存在的段落。"""

    def test_missing_section_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><p>見 §4</p><h2>二</h2>")))

    def test_missing_subsection_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><h3>甲</h3><p>見 §1.2</p>")))

    def test_existing_refs_pass(self):
        body = "<h2>一</h2><h3>甲</h3><p>見 §1.1、§2 和 §3（總結）</p><h2 class='x'>二</h2><p>回到§1</p>"
        self.assertTrue(ok(page(body)), build.lint(page(body)))


class ExerciseRule(unittest.TestCase):
    def test_check_fails_in_both_modes(self):
        for mode in ("read", "learn"):
            with self.subTest(mode=mode):
                self.assertFalse(ok(page("<h2>一</h2>" + CHECK, mode)))

    def test_input_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><input type="text">', "learn")))

    def test_plain_details_passes(self):
        self.assertTrue(ok(page("<h2>一</h2><details><summary>延伸</summary><p>可略過</p></details>", "read")))


class LearnSheetRule(unittest.TestCase):
    """learn 的答案紙要摺起來，使用者先在對話裡做。"""

    SHEET = '<div class="sheet">F = 29.74</div>'

    def body(self, sheet):
        return f"<h2>一</h2>{WHY}{ORIGIN}{sheet}"

    def test_open_sheet_fails_in_learn(self):
        self.assertFalse(ok(page(self.body(self.SHEET), "learn")))

    def test_open_sheet_passes_in_read(self):
        self.assertTrue(ok(page(self.body(self.SHEET), "read")))

    def test_folded_sheet_passes_in_learn(self):
        for folded in (f"<details><summary>做完再打開</summary>{self.SHEET}</details>",
                       f'<DETAILS class="x"><summary>答案</summary><div>{self.SHEET}</div></DETAILS>'):
            with self.subTest(folded=folded[:30]):
                src = page(self.body(folded), "learn")
                self.assertTrue(ok(src), build.lint(src))


class Output(unittest.TestCase):
    def built(self, body):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.png").write_bytes(PNG)
            return build.build(page(body), Path(d))

    def test_inlines_numbers_and_styles(self):
        out = self.built("<h2>甲</h2><h3>乙</h3><h3 id='keep'>丙</h3><h2>丁</h2>" + FIG)
        self.assertIn("data:image/png;base64,", out)
        self.assertNotIn('src="a.png"', out)
        self.assertIn('id="s1"><span class="num">§1</span> 甲', out)
        self.assertIn('id="s1-1"><span class="num">§1.1</span> 乙', out)
        self.assertIn("id='keep'><span class=\"num\">§1.2</span> 丙", out)
        self.assertIn('<span class="num">§2</span> 丁', out)
        self.assertIn("<style>", out)

    def test_toc_lists_every_h2(self):
        out = self.built("<h2>甲 <i>x</i></h2><h3>乙</h3><h2 id='own'>丁</h2>")
        toc = out[out.index('<nav class="toc">'):out.index("</nav>")]
        self.assertIn('<a href="#s1">§1 甲 x</a>', toc)
        self.assertIn('<a href="#own">§2 丁</a>', toc)
        self.assertNotIn("乙", toc)
        self.assertLess(out.index('<nav class="toc">'), out.index("<h2"))

    def test_refs_become_links(self):
        out = self.built("<h2>甲</h2><h3>乙</h3><h3 id='keep'>丙</h3><p>見 §1.1 和 §1.2</p>"
                         '<p><a href="#x">§1</a></p><h2>丁</h2>')
        self.assertIn('見 <a href="#s1-1">§1.1</a> 和 <a href="#keep">§1.2</a>', out)
        self.assertIn('<a href="#x">§1</a>', out)
        self.assertIn('<span class="num">§1</span> 甲', out)

    def test_main_refuses_to_write_on_violation(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "guide-src.html"
            src.write_text(page('<h2>一</h2><img src="a.png">'), encoding="utf-8")
            self.assertEqual(build.main([str(src)]), 1)
            self.assertFalse((Path(d) / "guide.html").exists())


if __name__ == "__main__":
    unittest.main()
