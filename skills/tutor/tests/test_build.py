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
ZH_FIG = '<figure><img src="a.png" data-zh="a.zh.png" alt=""><figcaption>Classnote Topic 3 p.4</figcaption></figure>'
CHECK = '<details class="check"><summary>t 值怎麼算？</summary><p>b 除以 SE</p></details>'
# 課件欄第一段是 §1，題目欄的「為什麼」連到它
WHY = '<div class="why"><p>F 是訊號除以雜訊，見 §1</p></div>'
ORIGIN = '<table class="origin"><tr data-from="convention"><td>α = 0.05</td><td>慣例</td></tr></table>'
CALC = ('<div class="calc" id="c1"><p class="formula"><i>R</i>² = SSR / SST</p>'
        '<p class="subst">= 10556.1 / 11443.3 = 0.9225</p></div>')
ANOVA = TR + '<figure id="anova"><img src="a.png"><figcaption>Minitab p.3</figcaption></figure>'
SUMMARY = '<div class="summary"><ul><li>R² 是解釋了的比例</li></ul></div>'
RECAP = '<h2 class="recap">總結</h2><table><tr><td>看到什麼</td><td>結論</td></tr></table>'
COVER = ('<details><summary>看整頁</summary>'
         '<figure class="page"><img src="a.png" data-zh="a.png"><figcaption>Cover p.1</figcaption></figure></details>')
COURSE = "<h2>課</h2><p>內容</p>"
PROBLEMS = "<h2>例</h2><p>題目</p>"


def ans(inner, summary=True):
    """題目欄的做法和答案，收在 details.answer 裡，最後是這題記住。"""
    return f'<details class="answer"><summary>做法和答案</summary>{inner}{SUMMARY if summary else ""}</details>'


def close_sections(body, recap):
    """每個 h2 段落結尾補上總結（題目欄最後一段是 recap 就不補），讓其他規則的測試只管自己那條。"""
    starts = [m.start() for m in re.finditer(r"<h2[\s>]", body, re.I)]
    for pos in reversed(starts[1:]):
        body = body[:pos] + SUMMARY + body[pos:]
    return body + (SUMMARY if starts else "") + (RECAP if recap else "")


def page(course=COURSE, problems=PROBLEMS, pages="Cover p.1", cover=COVER, close=True, head="", tail=""):
    """整頁 HTML：左欄課件、右欄題目。預設在課件欄開頭放一張整頁圖滿足頁數覆蓋，並補上總結。"""
    if close:
        course = close_sections(course, recap=False)
        problems = close_sections(problems, recap=True)
    return (f'<!doctype html><html><head><title>x</title></head><body data-pages="{pages}">{head}'
            f'<section class="course">{cover}{course}</section>'
            f'<section class="problems">{problems}</section>{tail}</body></html>')


def prob(body, **kw):
    """只寫題目欄，課件欄用預設的一段。"""
    return page(problems=body, **kw)


def prob_raw(problems, course=COURSE):
    """題目欄照寫、不補總結（測試自己決定每段怎麼結尾）；課件欄補好總結。"""
    return page(close_sections(course, recap=False), problems, close=False)


def ok(src):
    return build.lint(src) == []


class PaneRule(unittest.TestCase):
    """左欄課件、右欄題目：body 底下只有這兩欄，兩欄都要有，課件欄在前。"""

    def test_content_outside_panes_fails(self):
        self.assertFalse(ok(page(head="<h1>Topic 4</h1>")))

    def test_h2_in_other_section_fails(self):
        self.assertFalse(ok(page(tail='<section class="extra"><h2>多</h2></section>')))

    def test_missing_problems_pane_fails(self):
        src = page().replace('<section class="problems">', '<section class="course">')
        self.assertFalse(ok(src))

    def test_course_after_problems_fails(self):
        src = (f'<html><body data-pages="Cover p.1"><section class="problems">{PROBLEMS}{SUMMARY}</section>'
               f'<section class="course">{COVER}{COURSE}{SUMMARY}{RECAP}</section></body></html>')
        self.assertFalse(ok(src))

    def test_formatting_variants_pass(self):
        src = ('<html><body data-pages="Cover p.1">\n  <!-- 左欄 -->\n'
               f'<SECTION CLASS="pane course" id="c"><h1>Topic 4</h1>{COVER}<section><h2>課</h2><p>內容</p>{SUMMARY}</section></SECTION>\n'
               f'<section data-x="1" class="problems wide"><section>{PROBLEMS}{SUMMARY}</section>{RECAP}</section>'
               '<script>console.log(1)</script></body></html>')
        self.assertTrue(ok(src), build.lint(src))


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

    def test_remote_translated_img_fails(self):
        self.assertFalse(ok(page('<h2>一</h2><figure><img src="a.png" data-zh="https://x.y/a.png">'
                                 '<figcaption>p.1</figcaption></figure>')))

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
        body = (f'<h2>一</h2>{WHY}' + ans(f'{ORIGIN}<div class="sheet"><p>{big}</p></div>')
                + f"<table><tr><td>{big}</td></tr></table>"
                f'{TR}<figure><img src="a.png"><figcaption>p.2 {big}</figcaption></figure>')
        self.assertTrue(ok(prob(body)), build.lint(prob(body)))

    def test_translation_not_counted(self):
        big = "字" * (self.per * 2)
        self.assertTrue(ok(page(f'<h2>一</h2><div class="tr"><p>{big}</p></div>' + FIG.removeprefix(TR))))

    def test_unclosed_paragraphs_still_counted(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + "字" * self.per + "<p>多")))


class MethodRule(unittest.TestCase):
    """題目欄有 .calc 或 .sheet 的段落要有 .why（連到課件欄的 §）和 .origin；課件欄不用。"""

    def test_calc_without_why_fails(self):
        self.assertFalse(ok(prob(f'<h2>一</h2>' + ans(ORIGIN + CALC))))

    def test_sheet_without_origin_fails(self):
        self.assertFalse(ok(prob(f'<h2>一</h2>{WHY}' + ans('<div class="sheet">α = 0.05</div>'))))

    def test_why_without_course_ref_fails(self):
        self.assertFalse(ok(prob('<h2>一</h2><div class="why"><p>F 是訊號除以雜訊</p></div>' + ans(ORIGIN + CALC))))

    def test_why_linking_to_problem_section_fails(self):
        self.assertFalse(ok(prob('<h2>一</h2><div class="why"><p>同 §2</p></div>' + ans(ORIGIN + CALC))))

    def test_ref_outside_why_does_not_count(self):
        self.assertFalse(ok(prob('<h2>一</h2><p>見 §1</p><div class="why"><p>F</p></div>' + ans(ORIGIN + CALC))))

    def test_blocks_in_another_section_do_not_count(self):
        self.assertFalse(ok(prob(f'<h2>一</h2>{WHY}' + ans(ORIGIN) + '<h2>二</h2>' + ans(CALC))))

    def test_section_without_method_needs_nothing(self):
        self.assertTrue(ok(prob("<h2>一</h2><p>Topic 3 在做什麼</p>")))

    def test_course_calc_needs_nothing(self):
        self.assertTrue(ok(page(f"<h2>一</h2><p>先用 5 個數算一次</p>{CALC}")), build.lint(page(f"<h2>一</h2>{CALC}")))

    def test_formatting_variants_pass(self):
        variants = [
            f'<h2>一</h2>{WHY}' + ans(ORIGIN + CALC),
            '<h2>一</h2>' + ans(CALC + ORIGIN) + WHY + SUMMARY,
            '<H2 class="x">二</H2><SECTION CLASS="wide why"><p>用到 <a href="#s1">§1</a> 的 F</p></SECTION>\n'
            '<DETAILS class="answer x" open><summary>做法</summary><div><table data-x="1" class="origin small">'
            '<tr data-from="convention"><td>0.05</td></tr></table></div>'
            f'<div class="sheet big">F = 29.74</div>{SUMMARY}</DETAILS>',
            '<h2>一</h2><div class="why"><p>見 §1.1</p></div>' + ans(ORIGIN + CALC),
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                src = prob_raw(body + RECAP, course="<h2>課</h2><h3>甲</h3><p>內容</p>")
                self.assertTrue(ok(src), build.lint(src))


class AnswerFoldRule(unittest.TestCase):
    """題目欄的算式、答案紙、數字從哪來、常見錯誤都收進 details.answer；課件欄不用。"""

    BLOCKS = {
        "calc": CALC,
        "sheet": '<div class="sheet">F = 29.74</div>',
        "origin": ORIGIN,
        "trap": '<div class="trap"><p>n 不是 8</p></div>',
    }

    def test_open_blocks_fail(self):
        for name, block in self.BLOCKS.items():
            with self.subTest(block=name):
                self.assertFalse(ok(prob(f"<h2>一</h2>{WHY}{block}" + ans(ORIGIN + CALC))))

    def test_plain_details_is_not_enough(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{WHY}<details><summary>答案</summary>{ORIGIN}{CALC}</details>")))

    def test_folded_blocks_pass(self):
        for folded in (ans("".join(self.BLOCKS.values())),
                       f'<DETAILS class="x answer"><summary>答案</summary><div>{"".join(self.BLOCKS.values())}</div>{SUMMARY}</DETAILS>'):
            with self.subTest(folded=folded[:30]):
                src = prob_raw(f"<h2>一</h2>{WHY}{folded}{RECAP}")
                self.assertTrue(ok(src), build.lint(src))

    def test_course_blocks_stay_open(self):
        src = page(f'<h2>一</h2>{CALC}<div class="trap"><p>小心</p></div>')
        self.assertTrue(ok(src), build.lint(src))


class TranslationRule(unittest.TestCase):
    """每張圖都要有翻譯：翻譯圖（data-zh），或緊接在前的譯文，或標明沒有字要翻。"""

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

    def test_empty_zh_does_not_count(self):
        self.assertFalse(ok(page('<h2>一</h2><figure><img src="a.png" data-zh=""><figcaption>p.4</figcaption></figure>')))

    def test_formatting_variants_pass(self):
        variants = [
            '<h2>一</h2><P CLASS="x tr">譯文</P>\n  <!-- 註解 -->\n<figure><img src="a.png"><figcaption>p.4</figcaption></figure>',
            '<h2>一</h2><div class="why"><div class="tr">譯</div><figure class="w"><img src="a.png">'
            '<figcaption>p.4</figcaption></figure></div>',
            '<h2>一</h2><figure data-tr="none"><img src="a.png"><figcaption>殘差圖 p.5</figcaption></figure>',
            f'<h2>一</h2>{ZH_FIG}',
            '<h2>一</h2><p>先看圖</p><FIGURE id="f"><IMG DATA-ZH="a.zh.png" alt="" SRC="a.png" /><figcaption>p.4</figcaption></FIGURE>',
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                self.assertTrue(ok(page(body)), build.lint(page(body)))


class OriginRule(unittest.TestCase):
    """「數字從哪來」只列不明顯的數字；查表和要數的連到同一段裡的圖或算式。"""

    def body(self, row, fig=ANOVA, calc=CALC):
        return prob(f'<h2>一</h2>{WHY}{fig}' + ans(
            f'{calc}<table class="origin"><tr><th>值</th><th>從哪來</th></tr>{row}</table>'))

    def test_row_without_kind_fails(self):
        self.assertFalse(ok(self.body('<tr><td>10556.1</td><td>Minitab SS（<a href="#anova">圖</a>）</td></tr>')))

    def test_calc_row_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="calc"><td>0.9225</td><td><a href="#c1">算式</a></td></tr>')))

    def test_unknown_kind_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="minitab"><td>10556.1</td></tr>')))

    def test_table_row_without_link_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="table"><td>1.96</td><td>常態表</td></tr>')))

    def test_count_row_without_link_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="count"><td>n = 36</td><td>9 年 × 4 季</td></tr>')))

    def test_link_to_missing_target_fails(self):
        self.assertFalse(ok(self.body('<tr data-from="table"><td>1.96</td><td><a href="#z">圖</a></td></tr>')))

    def test_link_to_figure_in_other_section_fails(self):
        src = prob(f'<h2>零</h2>{ANOVA}<h2>一</h2>{WHY}' + ans(
            f'{CALC}<table class="origin"><tr data-from="table"><td>1.96</td><td><a href="#anova">圖</a></td></tr></table>'))
        self.assertFalse(ok(src))

    def test_formatting_variants_pass(self):
        rows = [
            '<tr data-from="table"><td>F 臨界值</td><td>F 表 α = 0.05 那頁（<a href="#anova">圖</a>）</td></tr>',
            '<TR class="x" DATA-FROM="table"><td><a class="y" href="#anova">4.35</a></td></TR>',
            '<tr data-from="count"><td>n = 6</td><td>只數有預測的週（<a href="#c1">算式</a>）</td></tr>',
            '<tr data-from="convention"><td>α = 0.05</td><td>題目沒寫就用這個</td></tr>',
            '<tr data-from="rule"><td>DW 1.5–2.5</td><td>講義的經驗法則</td></tr>',
            '<tr class="z" data-from="constant"><td>1</td><td>截距</td></tr>',
        ]
        for row in rows:
            with self.subTest(row=row[:40]):
                self.assertTrue(ok(self.body(row)), build.lint(self.body(row)))

    def test_figure_after_table_passes(self):
        src = prob_raw(f'<h2>一</h2>{WHY}' + ans(
            f'{CALC}<table class="origin"><tr data-from="table"><td>1.96</td><td><a href="#anova">圖</a></td></tr></table>')
            + ANOVA + SUMMARY + RECAP)
        self.assertTrue(ok(src), build.lint(src))


class CalcRule(unittest.TestCase):
    """每個 .calc 都寫出公式，再代入數字；不能只寫答案或「用 §N 的公式」。"""

    def body(self, calc):
        return page(f'<h2>一</h2>{calc}')

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
    """每個 h2 段落以 .summary 結尾（題目欄可以是 details.answer 的最後一塊）；最後一段是 h2.recap。"""

    def raw(self, course, problems):
        return page(course, problems, close=False)  # 兩欄都照寫，不補總結

    def test_section_without_summary_fails(self):
        self.assertFalse(ok(self.raw("<h2>一</h2><p>內容</p>", f"<h2>例</h2>{SUMMARY}{RECAP}")))

    def test_summary_not_last_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}<h3>後面</h3><p>還有</p>", f"<h2>例</h2>{SUMMARY}{RECAP}")))

    def test_summary_only_in_next_section_fails(self):
        self.assertFalse(ok(self.raw("<h2>一</h2><p>內容</p>", f"<h2>二</h2>{SUMMARY}{RECAP}")))

    def test_missing_recap_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}", f"<h2>例</h2>{SUMMARY}")))

    def test_recap_not_last_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}", f"{RECAP}<h2>例</h2>{SUMMARY}")))

    def test_answer_without_summary_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}", f"<h2>例</h2>{ans('<p>答</p>', summary=False)}{RECAP}")))

    def test_summary_not_last_in_answer_fails(self):
        folded = f'<details class="answer"><summary>答案</summary>{SUMMARY}<p>還有</p></details>'
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}", f"<h2>例</h2>{folded}{RECAP}")))

    def test_summary_in_plain_details_fails(self):
        folded = f'<details><summary>延伸</summary>{SUMMARY}</details>'
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}", f"<h2>例</h2>{folded}{RECAP}")))

    def test_formatting_variants_pass(self):
        variants = [
            (f"<h2>一</h2><p>內容</p>{SUMMARY}", f"<h2>例</h2>{SUMMARY}{RECAP}"),
            (f'<h2>一</h2><p>內容</p><SECTION CLASS="x summary"><p>記住</p></SECTION>\n  <!-- 註解 -->\n',
             f"<h2>例</h2>{ans('<p>答</p>')}\n<!-- 註解 -->\n{RECAP}"),
            (f'<H2 id="a">一</H2>{SUMMARY}',
             f'<h2>例</h2><DETAILS CLASS="answer"><summary>答</summary><div>x</div>'
             f'<ASIDE class="summary y"><p>記住</p></ASIDE>\n</DETAILS><h2 class="x recap" id="r">總結</h2><p>判斷表</p>'),
        ]
        for course, problems in variants:
            with self.subTest(problems=problems[:40]):
                src = self.raw(course, problems)
                self.assertTrue(ok(src), build.lint(src))


class PageFoldRule(unittest.TestCase):
    """整頁圖收進 <details>，data-pages 的每一頁都要有。"""

    def whole(self, name, n, cls="page", fold=True):
        fig = f'<figure class="{cls}"><img src="a.png" data-zh="a.png"><figcaption>{name} p.{n}</figcaption></figure>'
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
    """內文的 §N、§N.M 要指向真的存在的段落，兩欄連續編號。"""

    def test_missing_section_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><p>見 §9</p><h2>二</h2>")))

    def test_missing_subsection_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><h3>甲</h3><p>見 §1.2</p>")))

    def test_existing_refs_pass(self):
        body = "<h2>一</h2><h3>甲</h3><p>見 §1.1、§2 和 §3（例題）、§4（總結）</p><h2 class='x'>二</h2><p>回到§1</p>"
        self.assertTrue(ok(page(body)), build.lint(page(body)))


class ExerciseRule(unittest.TestCase):
    def test_check_fails(self):
        self.assertFalse(ok(page("<h2>一</h2>" + CHECK)))

    def test_input_fails(self):
        self.assertFalse(ok(prob('<h2>一</h2><input type="text">')))

    def test_plain_details_passes(self):
        self.assertTrue(ok(page("<h2>一</h2><details><summary>延伸</summary><p>可略過</p></details>")))


class Output(unittest.TestCase):
    def built(self, course=COURSE, problems=PROBLEMS, zh=True):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.png").write_bytes(PNG)
            if zh:
                (Path(d) / "a.zh.png").write_bytes(PNG + b"zh")
            return build.build(page(course, problems), Path(d))

    def test_inlines_numbers_and_styles(self):
        out = self.built("<h2>甲</h2><h3>乙</h3><h3 id='keep'>丙</h3><h2>丁</h2>" + FIG)
        self.assertIn("data:image/png;base64,", out)
        self.assertNotIn('src="a.png"', out)
        self.assertIn('id="s1"><span class="num">§1</span> 甲', out)
        self.assertIn('id="s1-1"><span class="num">§1.1</span> 乙', out)
        self.assertIn("id='keep'><span class=\"num\">§1.2</span> 丙", out)
        self.assertIn('<span class="num">§2</span> 丁', out)
        self.assertIn('<span class="num">§3</span> 例', out)
        self.assertIn("<style>", out)
        self.assertIn("<script>", out)

    def test_each_pane_gets_its_own_toc(self):
        out = self.built("<h2>甲 <i>x</i></h2><h3>乙</h3><h2 id='own'>丁</h2>", "<h2>例一</h2><h2>例二</h2>")
        split = out.index('<section class="problems">')
        course, problems = out[:split], out[split:]
        self.assertEqual(course.count('<details class="toc">'), 1)
        self.assertEqual(problems.count('<details class="toc">'), 1)
        ctoc = course[course.index('<details class="toc">'):course.index("</details>", course.index('<details class="toc">'))]
        self.assertIn('<a href="#s1">§1 甲 x</a>', ctoc)
        self.assertIn('<a href="#own">§2 丁</a>', ctoc)
        self.assertNotIn("乙", ctoc)
        self.assertNotIn("例一", ctoc)
        self.assertIn('<a href="#s3">§3 例一</a>', problems)
        self.assertLess(course.index('<details class="toc">'), course.index("<h2"))

    def test_translated_image_becomes_two(self):
        out = self.built(f"<h2>甲</h2>{ZH_FIG}")
        zh = base64.b64encode(PNG + b"zh").decode()
        en = base64.b64encode(PNG).decode()
        self.assertIn(f'<img class="zh" src="data:image/png;base64,{zh}" alt="">', out)
        self.assertIn(f'<img class="en" src="data:image/png;base64,{en}" alt="">', out)
        self.assertNotIn("data-zh", out.split("</style>", 1)[1])
        self.assertIn('data-act="lang"', out)

    def test_existing_class_is_kept(self):
        out = self.built('<h2>甲</h2><figure><img class="wide" data-zh="a.zh.png" src="a.png"><figcaption>p.1</figcaption></figure>')
        self.assertIn('class="zh wide"', out)
        self.assertIn('class="en wide"', out)

    def test_no_lang_button_without_translations(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.png").write_bytes(PNG)
            src = page(f"<h2>甲</h2>{FIG}", cover=COVER.replace(' data-zh="a.png"', ""))
            out = build.build(src, Path(d))
        self.assertNotIn('data-act="lang"', out)
        self.assertIn('data-act="answers"', out)

    def test_missing_translated_image_stops(self):
        with self.assertRaises(SystemExit):
            self.built('<h2>甲</h2><figure><img src="a.png" data-zh="nope.png"><figcaption>p.1</figcaption></figure>')

    def test_refs_become_links_across_panes(self):
        out = self.built("<h2>甲</h2><h3>乙</h3><h3 id='keep'>丙</h3><p>見 §1.1 和 §1.2</p>"
                         '<p><a href="#x">§1</a></p><h2>丁</h2>', "<h2>例</h2><p>用到 §1.1</p>")
        self.assertIn('見 <a href="#s1-1">§1.1</a> 和 <a href="#keep">§1.2</a>', out)
        self.assertIn('用到 <a href="#s1-1">§1.1</a>', out)
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
