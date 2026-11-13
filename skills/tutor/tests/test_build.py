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
# 課件欄第一段是 §1，題目欄的「為什麼」連到它，並把那一塊課件截過來
WHY_FIG = '<figure><img src="a.png" data-zh="a.zh.png" alt=""><figcaption>Classnote Topic 3 p.4</figcaption></figure>'
WHY = f'<div class="why"><p>F 是訊號除以雜訊，見 §1</p>{WHY_FIG}</div>'
# 題目欄開頭的題型表：看到什麼 → 用什麼 → 示範題。題目欄第一段的 § 由 page() 算
TYPES = '<table class="types"><tr><th>看到什麼</th><th>用什麼</th><th>示範</th></tr><tr data-type="f-test"><td>ANOVA 表</td><td>F</td><td>§{n}</td></tr></table>'
# 定義框前面先用小數字舉例
EG = '<p>先用 2, 4, 6 算一次：平均是 4。</p>'
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
    """讓其他規則的測試只管自己那條：課件欄每個 h2 底下補「這頁重點」、結尾補自測；
    題目欄每個 h2 段落結尾補總結，最後接 recap。"""
    starts = [m.start() for m in re.finditer(r"<h2[\s>]", body, re.I)]
    tail = SUMMARY if recap else CHECK
    for pos in reversed(starts[1:]):
        body = body[:pos] + tail + body[pos:]
    body += tail if starts else ""
    if recap:
        return body + RECAP
    return re.sub(r"(<h2\b.*?</h2\s*>)", lambda m: m.group(1) + SUMMARY, body, flags=re.I | re.S)


def page(course=COURSE, problems=PROBLEMS, pages="Cover p.1", cover=COVER, close=True, head="", tail="",
         types=None, kind=""):
    """整頁 HTML：左欄課件、右欄題目。預設在課件欄開頭放一張整頁圖滿足頁數覆蓋，題目欄開頭放題型表，並補上總結。"""
    if close:
        course = close_sections(course, recap=False)
        problems = close_sections(problems, recap=True)
    if types is None:
        types = TYPES.replace("{n}", str(len(re.findall(r"<h2[\s>]", course, re.I)) + 1))
    body = f' data-problems="{kind}"' if kind else ""
    return (f'<!doctype html><html><head><title>x</title></head><body data-pages="{pages}"{body}>{head}'
            f'<section class="course">{cover}{course}</section>'
            f'<section class="problems">{types}{problems}</section>{tail}</body></html>')


def prob(body, **kw):
    """只寫題目欄，課件欄用預設的一段。"""
    return page(problems=body, **kw)


def prob_raw(problems, course=COURSE):
    """題目欄照寫、不補總結（測試自己決定每段怎麼結尾）；課件欄補好總結。"""
    return page(close_sections(course, recap=False), problems, close=False,
                types=TYPES.replace("{n}", str(len(re.findall(r"<h2[\s>]", course, re.I)) + 1)))


def ok(src):
    return build.lint(src) == []


def prose(n, word="字"):
    """n 個字的正文，切成不超過一句上限的短句。"""
    step = build.MAX_SENTENCE - 10
    glue, end = ("", "。") if word == "字" else (" ", ". ")
    return "".join(glue.join([word] * min(step, n - i)) + end for i in range(0, n, step))


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
        src = (f'<html><body data-pages="Cover p.1"><section class="problems">{TYPES.replace("{n}", "1")}{PROBLEMS}{SUMMARY}</section>'
               f'<section class="course">{COVER}{COURSE}{SUMMARY}{RECAP}</section></body></html>')
        self.assertFalse(ok(src))

    def test_formatting_variants_pass(self):
        src = ('<html><body data-pages="Cover p.1">\n  <!-- 左欄 -->\n'
               f'<SECTION CLASS="pane course" id="c"><h1>Topic 4</h1>{COVER}<section><h2>課</h2>{SUMMARY}<p>內容</p>{CHECK}</section></SECTION>\n'
               f'<section data-x="1" class="problems wide">{TYPES.replace("{n}", "2")}<section>{PROBLEMS}{SUMMARY}</section>{RECAP}</section>'
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
        self.assertFalse(ok(page("<h2>一</h2><p>" + prose(self.per + 1) + "</p>")))

    def test_same_text_split_into_sections_passes(self):
        half = prose(self.per // 2 + 1)
        self.assertTrue(ok(page(f"<h2>一</h2><p>{half}</p><h2>二</h2><p>{half}</p>")))

    def test_no_whole_page_limit(self):
        body = "".join(f"<h2>{i}</h2><p>{prose(self.per - 20)}</p>" for i in range(30))
        self.assertTrue(ok(page(body)), build.lint(page(body))[:2])

    def test_english_counts_words_not_letters(self):
        words = prose(self.per - 20, "regression")
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
        self.assertFalse(ok(page("<h2>一</h2><p>" + prose(self.per) + "<p>多")))


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
            '<h2>一</h2>' + ans(ORIGIN + CALC) + WHY + SUMMARY,
            f'<H2 class="x">二</H2><SECTION CLASS="wide why"><p>用到 <a href="#s1">§1</a> 的 F</p>{WHY_FIG}</SECTION>\n'
            '<DETAILS class="answer x" open><summary>做法</summary><div><table data-x="1" class="origin small">'
            '<tr data-from="convention"><td>0.05</td></tr></table></div>'
            f'<div class="sheet big">F = 29.74</div>{SUMMARY}</DETAILS>',
            f'<h2>一</h2><div class="why"><p>見 §1.1</p>{WHY_FIG}</div>' + ans(ORIGIN + CALC),
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                src = prob_raw(body + RECAP, course="<h2>課</h2><h3>甲</h3><p>內容</p>")
                self.assertTrue(ok(src), build.lint(src))


class AnswerFoldRule(unittest.TestCase):
    """題目欄的算式、答案紙、數字從哪來、常見錯誤都收進 details.answer；課件欄不用。"""

    BLOCKS = {
        "origin": ORIGIN,
        "calc": CALC,
        "sheet": '<div class="sheet">F = 29.74</div>',
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
            f'<table class="origin"><tr><th>值</th><th>從哪來</th></tr>{row}</table>{calc}'))

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
            f'<table class="origin"><tr data-from="table"><td>1.96</td><td><a href="#anova">圖</a></td></tr></table>{CALC}')
            + ANOVA + SUMMARY + RECAP)
        self.assertTrue(ok(src), build.lint(src))


class OriginFirstRule(unittest.TestCase):
    """題目欄先列「數字從哪來」，再代公式：讀者算到那一步時已經知道每個數字的來源。"""

    def test_calc_before_origin_fails(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{WHY}" + ans(CALC + ORIGIN))))

    def test_calc_in_earlier_fold_fails(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{WHY}" + ans(CALC, summary=False) + ans(ORIGIN))))

    def test_origin_of_other_section_does_not_count(self):
        src = prob(f"<h2>零</h2>{WHY}" + ans(ORIGIN + CALC) + f"<h2>一</h2>{WHY}" + ans(CALC + ORIGIN))
        self.assertFalse(ok(src))

    def test_course_pane_order_is_free(self):
        src = page(f"<h2>一</h2>{CALC}{ORIGIN}")
        self.assertTrue(ok(src), build.lint(src))

    def test_formatting_variants_pass(self):
        variants = [
            f"<h2>一</h2>{WHY}" + ans(ORIGIN + CALC),
            f"<h2>一</h2>{WHY}" + ans(ORIGIN + '<p>(a)</p>', summary=False) + ans(f'<div>{CALC}</div>'),
            f'<h2>一</h2>{WHY}<DETAILS class="answer"><summary>(a)</summary><TABLE CLASS="x origin">'
            '<tr data-from="convention"><td>0.05</td></tr></TABLE>\n<!-- 先找數字 -->\n'
            f'<DIV class="calc w" id="c9"><p class="formula">a = b</p><p class="subst">= 1</p></DIV>{SUMMARY}</DETAILS>',
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                self.assertTrue(ok(prob(body)), build.lint(prob(body)))


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
        return page(f'<h2>一</h2>{EG}{d}')

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


GOOD = f"<h2>一</h2>{SUMMARY}<p>內容</p>{CHECK}"  # 課件欄合格的一段：開頭重點、結尾自測


class SummaryRule(unittest.TestCase):
    """題目欄每個 h2 段落以 .summary 結尾（可以是 details.answer 的最後一塊）；最後一段是 h2.recap。"""

    def raw(self, problems, course=GOOD):
        return page(course, problems, close=False)  # 兩欄都照寫，不補總結

    def test_section_without_summary_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>例</h2><p>題目</p>{RECAP}")))

    def test_summary_not_last_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>例</h2>{SUMMARY}<p>還有</p>{RECAP}")))

    def test_summary_only_in_next_section_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>例</h2><p>題目</p><h2>二</h2>{SUMMARY}{RECAP}")))

    def test_missing_recap_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>例</h2>{SUMMARY}")))

    def test_recap_not_last_fails(self):
        self.assertFalse(ok(self.raw(f"{RECAP}<h2>例</h2>{SUMMARY}")))

    def test_answer_without_summary_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>例</h2>{ans('<p>答</p>', summary=False)}{RECAP}")))

    def test_summary_not_last_in_answer_fails(self):
        folded = f'<details class="answer"><summary>答案</summary>{SUMMARY}<p>還有</p></details>'
        self.assertFalse(ok(self.raw(f"<h2>例</h2>{folded}{RECAP}")))

    def test_summary_in_plain_details_fails(self):
        folded = f'<details><summary>延伸</summary>{SUMMARY}</details>'
        self.assertFalse(ok(self.raw(f"<h2>例</h2>{folded}{RECAP}")))

    def test_formatting_variants_pass(self):
        variants = [
            f"<h2>例</h2>{SUMMARY}{RECAP}",
            f"<h2>例</h2>{ans('<p>答</p>')}\n<!-- 註解 -->\n{RECAP}",
            f'<h2>例</h2><DETAILS CLASS="answer"><summary>答</summary><div>x</div>'
            f'<ASIDE class="summary y"><p>記住</p></ASIDE>\n</DETAILS><h2 class="x recap" id="r">總結</h2><p>判斷表</p>',
        ]
        for problems in variants:
            with self.subTest(problems=problems[:40]):
                src = self.raw(problems)
                self.assertTrue(ok(src), build.lint(src))


class CourseSectionRule(unittest.TestCase):
    """課件欄每個 h2：開頭（第一個 h3 之前）放「這頁重點」，最後一塊是摺起來的自測。"""
    P = f"<h2>例</h2>{SUMMARY}{RECAP}"

    def raw(self, course):
        return page(course, self.P, close=False)

    def test_good_section_passes(self):
        src = self.raw(GOOD)
        self.assertTrue(ok(src), build.lint(src))

    def test_no_key_points_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2><p>內容</p>{CHECK}")))

    def test_key_points_after_first_h3_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2><h3>甲</h3><p>內容</p>{SUMMARY}{CHECK}")))

    def test_key_points_only_in_previous_section_fails(self):
        self.assertFalse(ok(self.raw(f"{GOOD}<h2>二</h2><p>內容</p>{CHECK}")))

    def test_no_check_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}<p>內容</p>")))

    def test_check_not_last_fails(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}{CHECK}<p>還有</p>")))

    def test_plain_details_is_not_a_check(self):
        self.assertFalse(ok(self.raw(f"<h2>一</h2>{SUMMARY}<details><summary>延伸</summary><p>x</p></details>")))

    def test_formatting_variants_pass(self):
        variants = [
            f'<H2 id="a">一（講義 p.3）</H2>\n<details><summary>看整頁</summary><p>x</p></details>'
            f'<SECTION CLASS="x summary"><p>重點</p></SECTION><h3>甲</h3><p>內容</p>{CHECK}{CHECK}\n<!-- 註解 -->\n',
            f"<h2>一</h2>{SUMMARY}<h3>甲</h3>{CHECK}<h3>乙</h3><p>內容</p>"
            '<DETAILS open CLASS="wide check"><summary>算 r</summary><div class="calc"><p class="formula">r = 1 / 2</p>'
            '<p class="subst">= 0.5</p></div></DETAILS>',
        ]
        for course in variants:
            with self.subTest(course=course[:40]):
                src = self.raw(course)
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


class SentenceRule(unittest.TestCase):
    """一句不超過 MAX_SENTENCE 字：讀者是零基礎，一句一件事。"""
    cap = build.MAX_SENTENCE

    def test_long_sentence_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + "字" * (self.cap + 1) + "。</p>")))

    def test_long_sentence_without_period_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + "字" * (self.cap + 1) + "</p>")))

    def test_long_list_item_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><ul><li>" + "字" * (self.cap + 1) + "</li></ul>")))

    def test_long_english_sentence_fails(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + " ".join(["word"] * (self.cap + 1)) + ".</p>")))

    def test_same_text_split_into_sentences_passes(self):
        half = "字" * (self.cap // 2 + 1)
        src = page(f"<h2>一</h2><p>{half}。{half}！{half}？{half}；{half}</p><p>{half}</p>")
        self.assertTrue(ok(src), build.lint(src))

    def test_inline_tags_do_not_split_or_join(self):
        half = "字" * (self.cap // 2 + 1)
        self.assertFalse(ok(page(f"<h2>一</h2><p>{half}<b>{half}</b></p>")))
        src = page(f"<h2>一</h2><p>{half}。<i>{half}</i></p>")
        self.assertTrue(ok(src), build.lint(src))

    def test_decimal_point_does_not_end_sentence(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + "x 1.5 " * (self.cap // 2 + 2) + "</p>")))

    def test_english_period_ends_sentence(self):
        words = " ".join(["word"] * (self.cap // 2 + 1))
        src = page(f"<h2>一</h2><p>{words}. {words}.</p>")
        self.assertTrue(ok(src), build.lint(src))

    def test_blocks_end_sentences(self):
        half = "字" * (self.cap // 2 + 1)
        src = page(f"<h2>一</h2><p>{half}</p><p>{half}</p><ul><li>{half}</li><li>{half}</li></ul>"
                   f"<div class='why'>{half}</div><h3>{half}</h3>")
        self.assertTrue(ok(src), build.lint(src))

    def test_calc_table_figure_sheet_not_counted(self):
        long = " + ".join(["12"] * (self.cap + 1))
        body = (f'<h2>一</h2><p>先用 5 個數算一次</p><div class="calc"><p class="formula">S = Σx</p><p class="subst">= {long}</p></div>'
                f"<table><tr><td>{'字' * (self.cap + 1)}</td></tr></table>"
                f"<div class='tr'><p>{'字' * (self.cap + 1)}</p></div>"
                f'<figure><img src="a.png"><figcaption>p.2 {"字" * (self.cap + 1)}</figcaption></figure>')
        self.assertTrue(ok(page(body)), build.lint(page(body)))


class ExampleBeforeDefRule(unittest.TestCase):
    """定義框前面要先舉例：同一個 h2/h3 塊裡，定義框之前的正文要有數字。"""
    DEF = '<div class="def"><p><dfn>趨勢</dfn>：長期方向</p><p class="test">後半平均比前半高</p></div>'

    def test_def_first_fails(self):
        self.assertFalse(ok(page(f"<h2>一</h2>{self.DEF}")))

    def test_example_only_in_heading_fails(self):
        self.assertFalse(ok(page(f"<h2>講義 p.3 的 5 個數</h2>{self.DEF}")))

    def test_example_only_in_previous_block_fails(self):
        self.assertFalse(ok(page(f"<h2>一</h2>{EG}<h3>甲</h3>{self.DEF}")))

    def test_example_in_figure_or_table_does_not_count(self):
        body = f'<h2>一</h2><table><tr><td>2, 4, 6</td></tr></table>{TR}<figure><img src="a.png"><figcaption>p.2</figcaption></figure>{self.DEF}'
        self.assertFalse(ok(page(body)))

    def test_example_inside_the_def_does_not_count(self):
        d = '<div class="def"><p>例如 2, 4, 6。</p><p><dfn>趨勢</dfn>：長期方向</p><p class="test">後半高</p></div>'
        self.assertFalse(ok(page(f"<h2>一</h2>{d}")))

    def test_formatting_variants_pass(self):
        variants = [
            f"<h2>一</h2>{EG}{self.DEF}",
            f"<h2>一</h2><h3>甲</h3><p>先看 12 個月的銷量：往上。</p>\n{self.DEF}",
            f'<h2>一</h2><p>先用 5 個數算一次</p>{CALC}{self.DEF}',
            f"<h2>一</h2>{EG}{self.DEF}<p>再來。</p>{self.DEF}",
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                self.assertTrue(ok(page(body)), build.lint(page(body)))


class PrereqRule(unittest.TestCase):
    """不能把讀者推去看別的 topic：前置知識在原地教。"""

    def test_sending_reader_to_other_topic_fails(self):
        for text in ("ACF 是 Topic 4 的東西", "Topic 2 學過標準差", "見 Topic 3", "上個 topic 講過", "之前學過的 t 檢定",
                     "Topic 4 已經教過", "上學期的統計學"):
            with self.subTest(text=text):
                self.assertFalse(ok(page(f"<h2>一</h2><p>{text}</p>")))

    def test_mention_in_why_fails(self):
        self.assertFalse(ok(prob(f'<h2>一</h2><div class="why"><p>Topic 4 的東西，見 §1</p>{WHY_FIG}</div>' + ans(ORIGIN + CALC))))

    def test_teaching_in_place_passes(self):
        body = ("<h2>一</h2><p>這題會用到自相關係數 r₁。它是 Topic 4 的 ACF，這裡用 2, 4, 6, 8 從零算一次。</p>"
                "<p>Topic 4 Summary p.3 的公式長這樣：</p>" + FIG)
        self.assertTrue(ok(page(body)), build.lint(page(body)))

    def test_html_comment_is_exempt(self):
        src = page("<h2>一</h2><!-- 維護者：ACF 是 Topic 4 的東西，這裡只補用到的 --><p>內容</p>")
        self.assertTrue(ok(src), build.lint(src))


class CrossLinkRule(unittest.TestCase):
    """題目欄每一題最多連到課件欄 MAX_CROSS 段：定義和公式原地再寫，不叫讀者跳來跳去。"""
    cap = build.MAX_CROSS
    course = "".join(f"<h2>課{i}</h2><p>內容</p>" for i in range(cap + 2))

    def refs(self, n):
        return "、".join(f"§{i}" for i in range(1, n + 1))

    def test_too_many_course_sections_fails(self):
        body = f'<h2>一</h2><div class="why"><p>用到 {self.refs(self.cap + 1)}</p>{WHY_FIG}</div>' + ans(ORIGIN + CALC)
        self.assertFalse(ok(page(self.course, body)))

    def test_refs_spread_over_the_section_count(self):
        body = (f'<h2>一</h2><div class="why"><p>用到 §1</p>{WHY_FIG}</div>'
                + ans(ORIGIN + CALC + f"<p>見 {self.refs(self.cap + 1)}</p>"))
        self.assertFalse(ok(page(self.course, body)))

    def test_same_section_many_times_passes(self):
        body = (f'<h2>一</h2><div class="why"><p>用到 §1、§1.1、§1</p>{WHY_FIG}</div>'
                + ans(ORIGIN + CALC + f"<p>見 {self.refs(self.cap)}，再見 §1</p>"))
        src = page("<h2>課</h2><h3>甲</h3><p>內容</p>" + self.course, body)
        self.assertTrue(ok(src), build.lint(src))

    def test_links_to_problem_sections_do_not_count(self):
        n = self.cap + 2  # 課件欄有 cap+2 段，題目欄從 §n+1 起
        body = (f'<h2>一</h2><div class="why"><p>用到 §1，同 §{n + 2}</p>{WHY_FIG}</div>' + ans(ORIGIN + CALC)
                + "".join(f"<h2>題{i}</h2><p>見 §{n + 1}、§1、§2、§{self.cap + 1}</p>" for i in range(2, 5)))
        src = page(self.course, body)
        self.assertTrue(ok(src), build.lint(src))

    def test_course_pane_is_free(self):
        body = "".join(f"<h2>課{i}</h2><p>見 {self.refs(self.cap + 2)}</p>" for i in range(self.cap + 2))
        self.assertTrue(ok(page(body)), build.lint(page(body)))

    def test_recap_is_free(self):
        recap = f'<h2 class="recap">總結</h2><p>流程：{self.refs(self.cap + 2)}</p>'
        src = page(close_sections(self.course, recap=False), f"<h2>一</h2><p>題目</p>{SUMMARY}{recap}", close=False)
        self.assertTrue(ok(src), build.lint(src))


class WhyFigureRule(unittest.TestCase):
    """「為什麼」裡要有這題用到的那一塊課件的截圖。"""

    def test_why_without_figure_fails(self):
        self.assertFalse(ok(prob('<h2>一</h2><div class="why"><p>見 §1</p></div>' + ans(ORIGIN + CALC))))

    def test_figure_outside_why_does_not_count(self):
        self.assertFalse(ok(prob(f'<h2>一</h2><div class="why"><p>見 §1</p></div>{ZH_FIG}' + ans(ORIGIN + CALC))))

    def test_section_without_method_needs_no_figure(self):
        self.assertTrue(ok(prob('<h2>一</h2><div class="why"><p>見 §1</p></div><p>只是說明</p>')))

    def test_formatting_variants_pass(self):
        variants = [
            f'<h2>一</h2><SECTION class="x why"><p>見 §1</p>\n{ZH_FIG}</SECTION>' + ans(ORIGIN + CALC),
            f'<h2>一</h2><div class="why">{TR}<figure data-x="1"><img src="a.png"><figcaption>p.3</figcaption></figure><p>見 §1</p></div>' + ans(ORIGIN + CALC),
        ]
        for body in variants:
            with self.subTest(body=body[:40]):
                self.assertTrue(ok(prob(body)), build.lint(prob(body)))


class TypesTableRule(unittest.TestCase):
    """題目欄開頭要有題型表，每種題型連到示範題。"""

    def test_missing_table_fails(self):
        self.assertFalse(ok(page(types="")))

    def test_table_after_first_h2_fails(self):
        self.assertFalse(ok(page(problems="<h2>例</h2>" + TYPES.replace("{n}", "2"), types="")))

    def test_table_in_course_pane_fails(self):
        self.assertFalse(ok(page(course=TYPES.replace("{n}", "2") + COURSE, types="")))

    def test_table_without_problem_ref_fails(self):
        self.assertFalse(ok(page(types=TYPES.replace("{n}", "1"))))
        self.assertFalse(ok(page(types='<table class="types"><tr><td>看到 ANOVA</td><td>F</td></tr></table>')))

    def test_formatting_variants_pass(self):
        variants = [
            '<p>先看這張表。</p>\n<TABLE CLASS="wide types" id="t"><caption>題型</caption><tr><th>看到</th></tr>'
            '<tr DATA-TYPE = "f-test"><td>ANOVA</td><td>示範：§2、§2.1</td></tr></TABLE>',
            '<details open><summary>題型表</summary>' + TYPES.replace("{n}", "2") + "</details>",
        ]
        for types in variants:
            with self.subTest(types=types[:40]):
                src = page(problems="<h2>例</h2><h3>甲</h3><p>題目</p>", types=types)
                self.assertTrue(ok(src), build.lint(src))


    ROW = '<tr data-type="{slug}"><td>ANOVA 表</td><td>F</td><td>§2</td></tr>'

    def table(self, *slugs):
        return '<table class="types">' + "".join(self.ROW.replace("{slug}", x) for x in slugs) + "</table>"

    def test_row_without_type_fails(self):
        self.assertFalse(ok(page(types=TYPES.replace("{n}", "2").replace(' data-type="f-test"', ""))))
        self.assertFalse(ok(page(types=self.table("F 檢定"))))

    def test_duplicate_type_fails(self):
        self.assertFalse(ok(page(types=self.table("f-test", "f-test"))))

    def test_several_types_pass(self):
        src = page(types=self.table("f-test", "t-test", "r2"))
        self.assertTrue(ok(src), build.lint(src))


class NotExaminedRule(unittest.TestCase):
    """「不考」要有老師明示的出處；沒有就當會考。"""

    def test_claim_without_evidence_fails(self):
        for text in ("這一塊不會直接考。", "推導不考。", "看懂就好。", "這頁不會考", "這段不用考"):
            with self.subTest(text=text):
                self.assertFalse(ok(page(course=f"<h2>課</h2><p>{text}</p>")))

    def test_claim_with_evidence_passes(self):
        variants = ['<p data-evidence="Course Outline p.2">老師說這頁不會考。</p>',
                    "<table><tr DATA-EVIDENCE='10/31 公告'><td>p.7</td><td><b>不考</b></td></tr></table>"]
        for v in variants:
            with self.subTest(v=v[:30]):
                src = page(course=f"<h2>課</h2>{v}")
                self.assertTrue(ok(src), build.lint(src))

    def test_blank_evidence_fails(self):
        self.assertFalse(ok(page(course='<h2>課</h2><p data-evidence=" ">這頁不考。</p>')))

    def test_unrelated_wording_passes(self):
        for text in ("範圍：這個 topic 有什麼、考不考", "考試不用操作軟體。", "這頁會考：手算 r。", "不考慮季節時用這條。", "參考課本 p.3。"):
            with self.subTest(text=text):
                src = page(course=f"<h2>課</h2><p>{text}</p>")
                self.assertTrue(ok(src), build.lint(src))


class KindRule(unittest.TestCase):
    """data-problems="text"：文科題目欄不用「數字從哪來」；calc（預設）照舊。"""
    SHEET = '<div class="sheet"><p>Answer: the Treaty of 1842.</p></div>'

    def test_unknown_kind_fails(self):
        self.assertFalse(ok(page(kind="essay")))

    def test_text_sheet_without_origin_passes(self):
        src = prob(f"<h2>一</h2>{WHY}" + ans(self.SHEET), kind="text")
        self.assertTrue(ok(src), build.lint(src))

    def test_text_sheet_still_needs_why_with_figure(self):
        self.assertFalse(ok(prob("<h2>一</h2>" + ans(self.SHEET), kind="text")))
        self.assertFalse(ok(prob('<h2>一</h2><div class="why"><p>見 §1</p></div>' + ans(self.SHEET), kind="text")))

    def test_text_sheet_still_folded(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{WHY}{self.SHEET}{SUMMARY}", kind="text")))

    def test_both_kinds_allow_folded_check(self):
        for kind in ("text", "calc", ""):
            with self.subTest(kind=kind):
                src = prob(f"<h2>一</h2>{CHECK}", kind=kind)
                self.assertTrue(ok(src), build.lint(src))

    def test_text_still_forbids_inputs(self):
        self.assertFalse(ok(prob('<h2>一</h2><input type="text">', kind="text")))

    def test_calc_kind_explicit_behaves_as_default(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{WHY}" + ans(self.SHEET), kind="calc")))
        src = prob(f"<h2>一</h2>{WHY}" + ans(ORIGIN + CALC), kind="calc")
        self.assertTrue(ok(src), build.lint(src))


class ExerciseRule(unittest.TestCase):
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
