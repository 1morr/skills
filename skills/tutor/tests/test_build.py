"""build.py 的規則閘門：每條規則都驗兩個方向。

違規要紅；只改無關的格式（空白、屬性順序、大小寫、標題文字）不能紅。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import base64
import contextlib
import importlib.util
import io
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
CHECK = '<details class="check"><summary>t 值怎麼算？</summary><p>b 除以 SE。還不會：回 §1</p></details>'
# 課件欄第一段是 §1，題目欄每題的「這題用到」連到它
USES = '<ul class="uses"><li>F 是訊號除以雜訊，見 §1</li></ul>'
# 「為什麼」是選用的；寫了就先寫出它在回答的問題
WHY = '<div class="why"><p><b>F 為什麼是除法？</b>F 是訊號除以雜訊</p></div>'
# 題目欄開頭的題型表：看到什麼 → 用什麼 → 示範題。題目欄第一段的 § 由 page() 算
TYPES = '<div class="cheat"><table class="types"><tr><th>看到什麼</th><th>用什麼</th><th>示範</th></tr><tr data-type="f-test"><td>ANOVA 表</td><td>F</td><td>§{n}</td></tr></table></div>'
# 定義框前面先用小數字舉例
EG = '<p>先用 2, 4, 6 算一次：平均是 4。</p>'
ORIGIN = '<table class="origin"><tr data-from="convention"><td>α = 0.05</td><td>慣例</td></tr></table>'
CALC = ('<div class="calc" id="c1"><p class="formula"><i>R</i>² = SSR / SST</p>'
        '<p class="subst">= 10556.1 / 11443.3 = <span class="ans">0.9225</span></p></div>')
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


def has(src, needle):
    """lint 的問題裡有沒有哪一條含 needle：確認是這條規則紅，不是別條。"""
    return any(needle in p for p in build.lint(src))


def numbered(course, problems):
    """兩部各寫自己的 h2，照 build 的順序編號、連好 §：回傳 (HTML, anchors)。"""
    # 題型表（types）寫一段字：真的頁題目欄的第一個 h2 前面一定有它
    src, anchors = build.number_headings(page(course, problems, close=False, types="<p>題型表</p>"))
    return build.link_refs(src, anchors), anchors


def h2_tag(out, anchor):
    return re.search(rf'<h2[^>]*\bid="{anchor}"[^>]*>', out).group(0)


def meta_of(out, anchor):
    return re.search(rf'<h2[^>]*\bid="{anchor}"[^>]*>.*?</h2><p class="meta">(.*?)</p>', out, re.S).group(1)


def h2(n, title, cls=""):
    """add_meta 之後的編號 h2。"""
    c = f' class="{cls}"' if cls else ""
    return f'<h2{c} id="s{n}" data-n="{n}"><span class="num">§{n}</span> {title}</h2>'


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
        body = "".join(f"<h2>{i}</h2><p>{prose(self.per - 40)}</p>" for i in range(30))
        self.assertTrue(ok(page(body)), build.lint(page(body))[:2])

    def test_english_counts_words_not_letters(self):
        words = prose(self.per - 40, "regression")
        self.assertTrue(ok(page(f"<h2>一</h2><p>{words}</p>")))

    def test_sheet_table_figure_not_counted(self):
        big = "字" * (self.per * 2)
        body = (f'<h2>一</h2>{USES}' + ans(f'{ORIGIN}<div class="sheet"><p>{big}</p></div>')
                + f"<table><tr><td>{big}</td></tr></table>"
                f'{TR}<figure><img src="a.png"><figcaption>p.2 {big}</figcaption></figure>')
        self.assertTrue(ok(prob(body)), build.lint(prob(body)))

    def test_translation_not_counted(self):
        big = "字" * (self.per * 2)
        self.assertTrue(ok(page(f'<h2>一</h2><div class="tr"><p>{big}</p></div>' + FIG.removeprefix(TR))))

    def test_unclosed_paragraphs_still_counted(self):
        self.assertFalse(ok(page("<h2>一</h2><p>" + prose(self.per) + "<p>多")))


class MethodRule(unittest.TestCase):
    """題目欄有 .calc 或 .sheet 的段落要有 .uses（寫出連到課件欄的 §）和 .origin；課件欄不用；.why 選用。"""
    NO_USES = '沒有 <ul class="uses">'
    NO_REF = "沒有連到講義"
    SHEET = '<div class="sheet">F = 29.74</div>'

    def test_calc_without_uses_fails(self):
        self.assertTrue(has(prob("<h2>一</h2>" + ans(ORIGIN + CALC)), self.NO_USES))

    def test_sheet_without_uses_fails(self):
        self.assertTrue(has(prob("<h2>一</h2>" + ans(ORIGIN + self.SHEET)), self.NO_USES))

    def test_sheet_without_origin_fails(self):
        self.assertTrue(has(prob(f"<h2>一</h2>{USES}" + ans(self.SHEET)), "數字從哪來"))

    def test_uses_without_course_ref_fails(self):
        src = prob('<h2>一</h2><ul class="uses"><li>F 是訊號除以雜訊</li></ul>' + ans(ORIGIN + CALC))
        self.assertTrue(has(src, self.NO_REF))
        self.assertFalse(has(src, self.NO_USES))

    def test_uses_linking_to_problem_section_fails(self):
        # 課件欄只有 §1，這一題是 §2
        src = prob('<h2>一</h2><ul class="uses"><li>同 §2</li></ul>' + ans(ORIGIN + CALC))
        self.assertTrue(has(src, self.NO_REF))

    def test_ref_outside_uses_does_not_count(self):
        src = prob('<h2>一</h2><p>見 §1</p><ul class="uses"><li>F</li></ul>' + ans(ORIGIN + CALC))
        self.assertTrue(has(src, self.NO_REF))

    def test_uses_in_another_section_does_not_count(self):
        src = prob(f"<h2>一</h2>{USES}" + ans(ORIGIN) + "<h2>二</h2>" + ans(CALC))
        self.assertTrue(has(src, self.NO_USES))

    def test_why_is_optional(self):
        for why in ("", WHY, '<div class="why"><p><b>為什麼看 §2？</b>沒有連到講義也行</p></div>'):
            with self.subTest(why=why[:30]):
                src = prob(f"<h2>一</h2>{USES}{why}" + ans(ORIGIN + CALC))
                self.assertTrue(ok(src), build.lint(src))

    def test_section_without_method_needs_nothing(self):
        for body in ("<p>Topic 3 在做什麼</p>", '<ul class="uses"><li>沒有連結</li></ul>'):
            with self.subTest(body=body[:20]):
                self.assertTrue(ok(prob("<h2>一</h2>" + body)))

    def test_course_calc_needs_nothing(self):
        self.assertTrue(ok(page(f"<h2>一</h2><p>先用 5 個數算一次</p>{CALC}")), build.lint(page(f"<h2>一</h2>{CALC}")))

    def test_formatting_variants_pass(self):
        variants = [
            f"<h2>一</h2>{USES}" + ans(ORIGIN + CALC),
            "<h2>一</h2>" + ans(ORIGIN + CALC, summary=False) + USES + SUMMARY,
            '<H2 class="x">二</H2><UL CLASS="wide uses">\n<li>用到 <a href="#s1">§1</a> 的 F</li></UL>\n'
            '<DETAILS class="answer x" open><summary>做法</summary><div><table data-x="1" class="origin small">'
            '<tr data-from="convention"><td>0.05</td></tr></table></div>'
            f'<div class="sheet big">F = 29.74</div>{SUMMARY}</DETAILS>',
            '<h2>一</h2><div class="uses"><p>見 §1.1</p></div>' + ans(ORIGIN + CALC),
            '<h2>一</h2><ul class="x uses"><li><b>F</b>（§1）</li><li>t 表</li></ul>' + ans(ORIGIN + CALC),
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
                self.assertFalse(ok(prob(f"<h2>一</h2>{USES}{block}" + ans(ORIGIN + CALC))))

    def test_plain_details_is_not_enough(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{USES}<details><summary>答案</summary>{ORIGIN}{CALC}</details>")))

    def test_folded_blocks_pass(self):
        for folded in (ans("".join(self.BLOCKS.values())),
                       f'<DETAILS class="x answer"><summary>答案</summary><div>{"".join(self.BLOCKS.values())}</div>{SUMMARY}</DETAILS>'):
            with self.subTest(folded=folded[:30]):
                src = prob_raw(f"<h2>一</h2>{USES}{folded}{RECAP}")
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
            '<h2>一</h2><div class="wrap"><div class="tr">譯</div><figure class="w"><img src="a.png">'
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
        return prob(f'<h2>一</h2>{USES}{fig}' + ans(
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
        src = prob(f'<h2>零</h2>{ANOVA}<h2>一</h2>{USES}' + ans(
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
        src = prob_raw(f'<h2>一</h2>{USES}' + ans(
            f'<table class="origin"><tr data-from="table"><td>1.96</td><td><a href="#anova">圖</a></td></tr></table>{CALC}')
            + ANOVA + SUMMARY + RECAP)
        self.assertTrue(ok(src), build.lint(src))


class OriginFirstRule(unittest.TestCase):
    """題目欄先列「數字從哪來」，再代公式：讀者算到那一步時已經知道每個數字的來源。"""

    def test_calc_before_origin_fails(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{USES}" + ans(CALC + ORIGIN))))

    def test_calc_in_earlier_fold_fails(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{USES}" + ans(CALC, summary=False) + ans(ORIGIN))))

    def test_origin_of_other_section_does_not_count(self):
        src = prob(f"<h2>零</h2>{USES}" + ans(ORIGIN + CALC) + f"<h2>一</h2>{USES}" + ans(CALC + ORIGIN))
        self.assertFalse(ok(src))

    def test_course_pane_order_is_free(self):
        src = page(f"<h2>一</h2>{CALC}{ORIGIN}")
        self.assertTrue(ok(src), build.lint(src))

    def test_formatting_variants_pass(self):
        variants = [
            f"<h2>一</h2>{USES}" + ans(ORIGIN + CALC),
            f"<h2>一</h2>{USES}" + ans(ORIGIN + '<p>(a)</p>', summary=False) + ans(f'<div>{CALC}</div>'),
            f'<h2>一</h2>{USES}<DETAILS class="answer"><summary>(a)</summary><TABLE CLASS="x origin">'
            '<tr data-from="convention"><td>0.05</td></tr></TABLE>\n<!-- 先找數字 -->\n'
            f'<DIV class="calc w" id="c9"><p class="formula">a = b</p><p class="subst">= <span class="ans">1</span></p></DIV>{SUMMARY}</DETAILS>',
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
            '<span class="x subst">= (8 + 4) / 2 = <B CLASS="big ans">6</B></span></DIV>',
            '<div class="calc"><div class="formula"><span class="frac"><span>a</span><span>b</span></span> = r</div>'
            '<div class="subst"><span class="frac"><span>16</span><span>40</span></span> = <span class="ans">0.4</span></div></div>',
        ]
        for calc in variants:
            with self.subTest(calc=calc[:40]):
                self.assertTrue(ok(self.body(calc)), build.lint(self.body(calc)))


class DefRule(unittest.TestCase):
    """術語寫成 .def：一個 <dfn>，加上這一種術語必填的那一格（data-kind 沒寫就是要分辨的東西，必填「怎樣才算」）。"""

    def body(self, d):
        return page(f'<h2>一</h2>{EG}{d}')

    def test_dfn_outside_def_fails(self):
        self.assertFalse(ok(self.body('<p><dfn>趨勢</dfn>是長期方向</p>')))

    def test_def_without_test_fails(self):
        self.assertFalse(ok(self.body('<div class="def"><p><dfn>趨勢</dfn>：長期方向</p></div>')))

    def test_def_with_empty_test_fails(self):
        self.assertFalse(ok(self.body('<div class="def"><p><dfn>趨勢</dfn>：長期方向</p><p class="test"> </p></div>')))

    def test_kind_needs_its_own_slot(self):
        cases = [('<div class="def" data-kind="quantity"><p><dfn>季節指數</dfn>：比一般季高多少</p><p class="test">加起來 400</p></div>', "怎麼算"),
                 ('<div class="def" data-kind="method"><p><dfn>比率移動平均法</dfn>：和附近一年比</p><p class="io">進去 Y，出來 S</p></div>',
                  "什麼時候用"),
                 ('<div class="def" data-kind="class"><p><dfn>趨勢</dfn>：長期方向</p><p class="how">後半減前半</p></div>', "怎樣才算")]
        for d, label in cases:
            with self.subTest(d=d[:50]):
                self.assertTrue(has(self.body(d), f"的「{label}」"), build.lint(self.body(d)))

    def test_unknown_kind_fails(self):
        d = '<div class="def" data-kind="number"><p><dfn>季節指數</dfn>：比一般季高多少</p><p class="test">加起來 400</p></div>'
        self.assertTrue(has(self.body(d), 'data-kind="number" 看不懂'))

    def test_other_kinds_pass_without_yes_and_no(self):
        variants = [
            '<div class="def" data-kind="quantity"><p><dfn>季節指數</dfn>：比一般季高多少</p>'
            '<p class="how">7 ÷ 10 × 100 = 70</p><p class="big">高於 100 是旺季</p><p class="small">低於 100 是淡季</p></div>',
            '<DIV DATA-KIND="quantity" CLASS="def x"><p><dfn>移動平均</dfn></p><ul class="how"><li>(8 + 12 + 10 + 10) ÷ 4</li></ul></DIV>',
            '<div class="def" data-kind="method"><p><dfn>比率移動平均法</dfn>：和附近一年比</p><p class="io">進去 Y，出來 S</p>'
            '<p class="when">資料有趨勢</p><p class="without">年尾的季被墊高</p></div>',
            '<div data-kind=" method " class="def"><p><dfn>分解</dfn></p><div class="when"><p>要預測的時候</p></div></div>',
        ]
        for d in variants:
            with self.subTest(d=d[:50]):
                self.assertTrue(ok(self.body(d)), build.lint(self.body(d)))

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
            '<p class="subst">= <span class="ans">0.5</span></p></div><p>還不會：回 §1.1</p></DETAILS>',
        ]
        for course in variants:
            with self.subTest(course=course[:40]):
                src = self.raw(course)
                self.assertTrue(ok(src), build.lint(src))


class CheckAnswerRule(unittest.TestCase):
    """講義那部的自測，答案要指回講義的 §；題目那部補完用的自測不用。"""
    NO_REF = "的答案沒有指回講義的 §"

    def raw(self, course):
        return page(course, f"<h2>例</h2><p>題目</p>{SUMMARY}{RECAP}", close=False)

    def test_answer_without_section_fails(self):
        cases = ['<details class="check"><summary>三件事各是哪個成分？</summary><p>(1) 季節 S：每年同一個月重複。</p></details>',
                 # § 寫在問題裡不算：答不出來的人打開答案才要知道回哪裡
                 '<details class="check"><summary>§1 的三件事各是哪個成分？</summary><p>季節。</p></details>']
        for check in cases:
            with self.subTest(check=check[:60]):
                self.assertTrue(has(self.raw(f"<h2>一</h2>{SUMMARY}<p>內容</p>{check}"), self.NO_REF))

    def test_answer_pointing_back_passes(self):
        cases = ['<details class="check"><summary>哪個成分？</summary><p>季節 S。線索是「每年 7 月」。</p><p>還不會：回 §1</p></details>',
                 '<DETAILS CLASS="x check" open><summary>哪個成分？</summary><ul><li>季節 S（§1 的「怎樣才算」）</li></ul></DETAILS>']
        for check in cases:
            with self.subTest(check=check[:60]):
                src = self.raw(f"<h2>一</h2>{SUMMARY}<p>內容</p>{check}")
                self.assertTrue(ok(src), build.lint(src))

    def test_completion_check_in_problems_needs_no_section(self):
        check = '<details class="check"><summary>這一步代入後是多少？</summary><p>0.5</p></details>'
        src = prob(f"<h2>一</h2><p>題目</p>{check}")
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
                   f"<div class='x'>{half}</div><h3>{half}</h3>")
        self.assertTrue(ok(src), build.lint(src))

    def test_calc_table_figure_sheet_not_counted(self):
        long = " + ".join(["12"] * (self.cap + 1))
        body = (f'<h2>一</h2><p>先用 5 個數算一次</p><div class="calc"><p class="formula">S = Σx</p><p class="subst">= {long} = <span class="ans">9</span></p></div>'
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
        src = prob(f'<h2>一</h2><div class="why"><p><b>這從哪來？</b>Topic 4 的東西，見 §1</p></div>{USES}' + ans(ORIGIN + CALC))
        self.assertTrue(has(src, "把讀者推去看別的 topic"))

    def test_teaching_in_place_passes(self):
        body = ("<h2>一</h2><p>這題會用到自相關係數 r₁。它是 Topic 4 的 ACF，這裡用 2, 4, 6, 8 從零算一次。</p>"
                "<p>Topic 4 Summary p.3 的公式長這樣：</p>" + FIG)
        self.assertTrue(ok(page(body)), build.lint(page(body)))

    def test_html_comment_is_exempt(self):
        src = page("<h2>一</h2><!-- 維護者：ACF 是 Topic 4 的東西，這裡只補用到的 --><p>內容</p>")
        self.assertTrue(ok(src), build.lint(src))


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
            '<SECTION CLASS="wide cheat"><p>先看這張表。</p>\n<TABLE CLASS="wide types" id="t"><caption>題型</caption><tr><th>看到</th></tr>'
            '<tr DATA-TYPE = "f-test"><td>ANOVA</td><td>示範：§2、§2.1</td></tr></TABLE><p>F = MSR / MSE</p></SECTION>',
            '<details open><summary>題型表</summary>' + TYPES.replace("{n}", "2") + "</details>",
        ]
        for types in variants:
            with self.subTest(types=types[:40]):
                src = page(problems="<h2>例</h2><h3>甲</h3><p>題目</p>", types=types)
                self.assertTrue(ok(src), build.lint(src))


    ROW = '<tr data-type="{slug}"><td>ANOVA 表</td><td>F</td><td>§2</td></tr>'

    def table(self, *slugs):
        return '<div class="cheat"><table class="types">' + "".join(self.ROW.replace("{slug}", x) for x in slugs) + "</table></div>"

    def test_table_outside_cheat_card_fails(self):
        bare = TYPES.replace("{n}", "2").replace('<div class="cheat">', "").replace("</table></div>", "</table>")
        self.assertFalse(ok(page(types=bare)))
        self.assertFalse(ok(page(types='<div class="cheat"><p>公式</p></div>' + bare)))

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


class AnswerMarkRule(unittest.TestCase):
    """每個 .calc 把算出來的結果標成 .ans。"""
    BARE = CALC.replace('<span class="ans">0.9225</span>', "0.9225")

    def test_calc_without_ans_fails(self):
        self.assertFalse(ok(page("<h2>一</h2>" + self.BARE)))

    def test_ans_outside_calc_does_not_count(self):
        self.assertFalse(ok(page(f'<h2>一</h2><p>答案是 <span class="ans">0.9225</span></p>{self.BARE}')))

    def test_each_calc_needs_its_own(self):
        self.assertFalse(ok(page("<h2>一</h2>" + CALC + self.BARE.replace("c1", "c2"))))

    def test_marked_calcs_pass(self):
        src = page("<h2>一</h2>" + CALC + CALC.replace("c1", "c2"))
        self.assertTrue(ok(src), build.lint(src))


class WhyRule(unittest.TestCase):
    """「為什麼」框開頭是它在回答的問題：一個 <b>，問號結尾。"""
    NO_QUESTION = "沒有先寫出它在回答的問題"

    def test_statement_without_question_fails(self):
        cases = ['<p class="why">第一種方法只適合沒有強烈趨勢的序列。</p>',
                 '<div class="why"><p>拆開的目的是預測。</p></div>',
                 '<p class="why"><b>第一種方法的限制</b>有趨勢時會被墊高。</p>',
                 '<p class="why">先說結論。<b>為什麼要先拿掉趨勢？</b>有趨勢時會被墊高。</p>',
                 '<p class="why"></p>']
        for why in cases:
            with self.subTest(why=why):
                self.assertTrue(has(page(f"<h2>一</h2>{why}"), self.NO_QUESTION))

    def test_question_first_passes(self):
        cases = ['<p class="why"><b>為什麼不直接用季平均 ÷ 總平均？</b>有趨勢時，後面幾年整體比較高。</p>',
                 '<div class="why"><p><b>分母為什麼是 n − 1?</b> 少一個自由度。</p><p>再補一句。</p></div>',
                 '<P CLASS="x why">\n  <B>拿掉平方會怎樣？</B>\n  正負會抵銷。</P>',
                 '<p class="why"><b>為什麼 <i>S</i> 要調到 400？</b>四季平均才會是 100。</p>']
        for why in cases:
            with self.subTest(why=why):
                src = page(f"<h2>一</h2>{why}")
                self.assertTrue(ok(src), build.lint(src))


class LabelRule(unittest.TestCase):
    """框的標籤由樣式加上，內文開頭不重寫。"""
    DEF = ('<div class="def"><p><dfn>趨勢</dfn>是長期方向</p><p class="test">{}</p></div>')
    REPEAT = "開頭重複了標籤"

    def test_repeated_label_fails(self):
        cases = [prob("<h2>一</h2>" + ans('<div class="trap">\n <p><b>常見錯誤</b>：把 n 算成 8</p></div>')),
                 page('<h2>一</h2><div class="summary"><p>這頁重點：r 介於 −1 和 1</p></div>'),
                 page(f'<h2>一</h2>{EG}<div class="def"><p>定義：<dfn>趨勢</dfn>是長期方向</p><p class="test">前後平均不同</p></div>'),
                 prob('<h2>一</h2><ul class="uses"><li>這題用到 §1 的 F</li></ul>'),
                 prob('<h2>一</h2><UL CLASS="x uses">\n  <li><b>這題用到</b>：§1</li></UL>'),
                 page(f"<h2>一</h2>{EG}" + self.DEF.format("怎樣才算：前後平均不同")),
                 page(f'<h2>一</h2>{EG}<div class="def" data-kind="quantity"><p><dfn>指數</dfn></p><p class="how">怎麼算：7 ÷ 10</p></div>'),
                 page(f'<h2>一</h2><div class="yes"><p>是：2, 4, 6 往上</p></div>'),
                 page(f'<h2>一</h2><div class="yes"><p>是:2, 4, 6 往上</p></div>'),
                 page(f'<h2>一</h2><div class="no"><p>不是：2, 6, 4 忽高忽低</p></div>'),
                 page(f'<h2>一</h2><div class="no"><p>不是:2, 6, 4 忽高忽低</p></div>')]
        for src in cases:
            with self.subTest(src=src[-120:]):
                self.assertTrue(has(src, self.REPEAT), build.lint(src))

    def test_label_word_later_in_text_passes(self):
        cases = [prob("<h2>一</h2>" + ans('<div class="trap"><p>把 n 算成 8 是常見錯誤</p></div>')),
                 page("<h2>一</h2><p>為什麼：因為資料少。</p><p>常見錯誤：沒有。</p>"),
                 prob('<h2>一</h2><ul class="uses"><li>F 檢定，這題用到 §1</li></ul>'),
                 prob('<h2>一</h2><ul class="uses"><li>§1 的 F</li><li>這題用到 §1</li></ul>'),
                 page(f"<h2>一</h2>{EG}" + self.DEF.format("前後平均明顯不同，才算有趨勢")),
                 page(f"<h2>一</h2>{EG}" + self.DEF.format("後半比前半高，這是怎樣才算")),
                 page('<h2>一</h2><div class="yes"><p>是的，2, 4, 6 往上</p></div>'),
                 page('<h2>一</h2><div class="no"><p>2, 6, 4 不是：忽高忽低</p></div>'),
                 page('<h2>一</h2><div class="no"><p>不是這樣：2, 6, 4 忽高忽低</p></div>')]
        for src in cases:
            with self.subTest(src=src[-120:]):
                self.assertTrue(ok(src), build.lint(src))


class PanelRule(unittest.TestCase):
    """查表面板：body 底下的 aside.panel，裡面每張圖一個分頁。"""
    TAB = '<figure data-tab="Z 表"><img src="a.png" data-zh="a.zh.png"><figcaption>Tables p.1</figcaption></figure>'

    def panel(self, fig):
        return page(tail=f'<aside class="panel">{fig}</aside>')

    def test_panel_passes(self):
        self.assertTrue(ok(self.panel(self.TAB)), build.lint(self.panel(self.TAB)))
        src = page(head=f"<ASIDE data-label='查表' CLASS='wide panel'>{self.TAB}</ASIDE>")
        self.assertTrue(ok(src), build.lint(src))

    def test_other_aside_under_body_fails(self):
        self.assertFalse(ok(page(tail=f'<aside class="notes">{self.TAB}</aside>')))

    def test_panel_figure_without_tab_fails(self):
        self.assertFalse(ok(self.panel(self.TAB.replace(' data-tab="Z 表"', ""))))

    def test_panel_figure_still_needs_translation_and_page(self):
        self.assertFalse(ok(self.panel(self.TAB.replace(' data-zh="a.zh.png"', ""))))
        self.assertFalse(ok(self.panel(self.TAB.replace("Tables p.1", "Z 表"))))


class WarningRule(unittest.TestCase):
    """整頁太長只提醒、不擋產出。"""
    FIGS = ZH_FIG * (build.FIGURE_WARN + 1)

    def test_long_prose_warns_but_passes(self):
        n = build.PER_SECTION - 100
        src = page("".join(f"<h2>{i}</h2>{prose(n)}" for i in range(build.PROSE_WARN // n + 1)))
        self.assertTrue(ok(src), build.lint(src))
        self.assertTrue(any("正文" in w for w in build.warnings(src)))

    def test_many_open_figures_warn(self):
        self.assertTrue(any("圖" in w for w in build.warnings(page("<h2>一</h2>" + self.FIGS))))

    def test_folded_figures_do_not_count(self):
        self.assertEqual(build.warnings(page(f"<h2>一</h2><details><summary>圖</summary>{self.FIGS}</details>")), [])

    def test_ordinary_page_has_no_warning(self):
        self.assertEqual(build.warnings(page()), [])


class KindRule(unittest.TestCase):
    """data-problems="text"：文科題目欄不用「數字從哪來」；calc（預設）照舊。"""
    SHEET = '<div class="sheet"><p>Answer: the Treaty of 1842.</p></div>'

    def test_unknown_kind_fails(self):
        self.assertFalse(ok(page(kind="essay")))

    def test_text_sheet_without_origin_passes(self):
        src = prob(f"<h2>一</h2>{USES}" + ans(self.SHEET), kind="text")
        self.assertTrue(ok(src), build.lint(src))

    def test_text_sheet_still_needs_uses_with_course_ref(self):
        self.assertTrue(has(prob("<h2>一</h2>" + ans(self.SHEET), kind="text"), "沒有 <ul class=\"uses\">"))
        src = prob('<h2>一</h2><ul class="uses"><li>F</li></ul>' + ans(self.SHEET), kind="text")
        self.assertTrue(has(src, "沒有連到講義"))

    def test_text_sheet_still_folded(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{USES}{self.SHEET}{SUMMARY}", kind="text")))

    def test_both_kinds_allow_folded_check(self):
        for kind in ("text", "calc", ""):
            with self.subTest(kind=kind):
                src = prob(f"<h2>一</h2>{CHECK}", kind=kind)
                self.assertTrue(ok(src), build.lint(src))

    def test_text_still_forbids_inputs(self):
        self.assertFalse(ok(prob('<h2>一</h2><input type="text">', kind="text")))

    def test_calc_kind_explicit_behaves_as_default(self):
        self.assertFalse(ok(prob(f"<h2>一</h2>{USES}" + ans(self.SHEET), kind="calc")))
        src = prob(f"<h2>一</h2>{USES}" + ans(ORIGIN + CALC), kind="calc")
        self.assertTrue(ok(src), build.lint(src))


class ExerciseRule(unittest.TestCase):
    def test_input_fails(self):
        self.assertFalse(ok(prob('<h2>一</h2><input type="text">')))

    def test_plain_details_passes(self):
        self.assertTrue(ok(page("<h2>一</h2><details><summary>延伸</summary><p>可略過</p></details>")))


class Output(unittest.TestCase):
    def built(self, course=COURSE, problems=PROBLEMS, zh=True, **kw):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.png").write_bytes(PNG)
            if zh:
                (Path(d) / "a.zh.png").write_bytes(PNG + b"zh")
            return build.build(page(course, problems, **kw), Path(d))

    @staticmethod
    def rail_of(out):
        return out[out.index('<nav class="rail"'):out.index("</nav>")]

    @staticmethod
    def head_of(out):
        return out[out.index('<div class="head">'):out.index('<div class="page">')]

    def test_inlines_numbers_and_styles(self):
        out = self.built("<h2>甲</h2><h3>乙</h3><h3 id='keep'>丙</h3><h2>丁</h2>" + FIG)
        self.assertIn("data:image/png;base64,", out)
        self.assertNotIn('src="a.png"', out)
        self.assertRegex(out, r'<h2[^>]*\bid="s1"[^>]*><span class="num">§1</span> 甲')
        self.assertIn('id="s1-1"><span class="num">§1.1</span> 乙', out)
        self.assertIn("id='keep'><span class=\"num\">§1.2</span> 丙", out)
        self.assertRegex(out, r'<h2[^>]*><span class="num">§2</span> 丁')
        self.assertRegex(out, r'<h2[^>]*><span class="num">§3</span> 例')
        self.assertIn("<style>", out)
        self.assertIn("<script>", out)

    def test_one_scroll_has_no_per_pane_toc_or_bars(self):
        out = self.built("<h2>甲</h2><h3>乙</h3>", "<h2>例一</h2>")
        for gone in ('<details class="toc">', 'class="here"', '<aside class="panel"'):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, out.split("</style>", 1)[1].split("<script>", 1)[0])

    def test_rail_lists_every_section_and_its_subsections(self):
        out = self.built("<h2>甲（講義 p.3）</h2><h3>乙</h3><h2 id='own'>丁</h2>", "<h2>例一</h2><h2>例二</h2>")
        rail = self.rail_of(out)
        self.assertIn('<a href="#s1"><span class="n">1</span><span class="t">甲</span>', rail)
        self.assertIn('<a href="#own"><span class="n">2</span><span class="t">丁</span>', rail)
        self.assertIn('<a href="#s3"><span class="n">3</span><span class="t">例一</span>', rail)
        self.assertIn('<a href="#s4"><span class="n">4</span><span class="t">例二</span>', rail)
        self.assertIn('<ol class="sub"><li><a href="#s1-1">§1.1 乙</a></li></ol>', rail)
        self.assertIn("<h2>講義<span></span></h2>", rail)
        self.assertIn("<h2>題目<span></span></h2>", rail)

    def test_rail_sits_before_main_and_the_peek_after_it(self):
        out = self.built("<h2>甲</h2><p>內文一</p>")
        order = [out.index(x) for x in ('<nav class="rail"', "<main>", '<div class="head">', '<div class="page">',
                                        '<section class="course">', "內文一", "</div></main>", 'class="scrim"',
                                        'class="peek"', "</body>")]
        self.assertEqual(order, sorted(order))

    def test_head_buttons_only_for_what_exists(self):
        plain = self.built()  # 預設的題目欄有速查卡，沒有名詞和查表
        head, rail = self.head_of(plain), self.rail_of(plain)
        for where in (head, rail):
            self.assertIn('data-act="cheat"', where)
            self.assertNotIn('data-act="terms"', where)
            self.assertNotIn('data-act="panel"', where)
        for act in ("nav", "digest-toggle"):
            self.assertIn(f'data-act="{act}"', head)
        tab = '<figure data-tab="Z 表"><img src="a.png" data-zh="a.zh.png"><figcaption>Tables p.1</figcaption></figure>'
        full = self.built("<h2>甲</h2><p><dfn>趨勢</dfn>是長期方向</p>", tail=f"<aside class='wide panel'>{tab}</aside>")
        for where in (self.head_of(full), self.rail_of(full)):
            for act in ("cheat", "terms", "panel"):
                self.assertIn(f'data-act="{act}"', where)

    def test_page_declares_a_viewport_once(self):
        # 沒有 viewport 時手機用桌面寬度排版再縮小，窄螢幕的排法永遠用不到
        out = self.built()
        self.assertEqual(len(re.findall(r'<meta\s+name="viewport"', out)), 1)
        self.assertLess(out.index('name="viewport"'), out.index("<style>"))
        own = '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        again = build.inject_assets(f"<html><head>{own}</head><body></body></html>")
        self.assertEqual(again.count('name="viewport"'), 1)
        self.assertIn(own, again)

    def test_theme_is_read_before_the_style(self):
        # 樣式之前先套上記住的明暗，打開時才不會先閃一下白底
        for src in ("<html><head><title>x</title></head><body></body></html>",
                    "<HTML><HEAD></HEAD><BODY></BODY></HTML>", "<p>沒有 head</p>"):
            with self.subTest(src=src[:20]):
                out = build.inject_assets(src)
                before = out[:out.index("<style>")]
                self.assertIn('localStorage.getItem("tutor-theme")', before)
                self.assertIn("<script>", before)
        self.assertIn('localStorage.getItem("tutor-theme")', self.built()[:self.built().index("<style>")])

    def test_panel_becomes_a_div_with_the_figures(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.png", "a.zh.png"):
                (Path(d) / name).write_bytes(PNG)
            tab = '<figure data-tab="{}"><img src="a.png" data-zh="a.zh.png"><figcaption>Tables p.1</figcaption></figure>'
            src = page(tail=f"<aside class='wide panel'>{tab.format('Z 表')}{tab.format('t 表')}</aside>")
            self.assertEqual(build.lint(src), [])
            out = build.build(src, Path(d))
        body = out.split("</style>", 1)[1]
        self.assertIn('<div id="panel"><figure data-tab="Z 表">', body)
        self.assertIn('<figure data-tab="t 表">', body)
        self.assertNotIn("<aside id=", body)
        self.assertNotIn("wide panel", body)
        self.assertIn('data-act="panel"', self.head_of(out))

    def test_translated_image_becomes_two_original_first(self):
        out = self.built(f"<h2>甲</h2>{ZH_FIG}")
        zh = base64.b64encode(PNG + b"zh").decode()
        en = base64.b64encode(PNG).decode()
        body = out.split("</style>", 1)[1]
        self.assertIn(f'<img class="zh" src="data:image/png;base64,{zh}" alt="">', body)
        self.assertIn(f'<img class="en" src="data:image/png;base64,{en}" alt="">', body)
        self.assertLess(body.index('<img class="en" src="data:image/png;base64,' + en),
                        body.index('<img class="zh" src="data:image/png;base64,' + zh))
        self.assertNotIn("data-zh", body)
        rail = self.rail_of(out)
        self.assertIn('data-act="lang-en"', rail)
        self.assertIn('data-act="lang-zh"', rail)

    def test_existing_class_is_kept(self):
        out = self.built('<h2>甲</h2><figure><img class="wide" data-zh="a.zh.png" src="a.png"><figcaption>p.1</figcaption></figure>')
        self.assertIn('class="zh wide"', out)
        self.assertIn('class="en wide"', out)
        self.assertLess(out.index('class="en wide"'), out.index('class="zh wide"'))

    def test_no_lang_switch_without_translations_but_always_a_theme_switch(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.png").write_bytes(PNG)
            src = page(f"<h2>甲</h2>{FIG}", cover=COVER.replace(' data-zh="a.png"', ""))
            out = build.build(src, Path(d))
        rail = self.rail_of(out)
        self.assertNotIn("lang-en", rail)
        self.assertNotIn("lang-zh", rail)
        self.assertIn('data-act="theme-light"', rail)
        self.assertIn('data-act="theme-dark"', rail)
        self.assertIn('data-act="answers"', out)  # 速查卡的按鈕不靠翻譯

    def test_missing_translated_image_stops(self):
        with self.assertRaises(SystemExit):
            self.built('<h2>甲</h2><figure><img src="a.png" data-zh="nope.png"><figcaption>p.1</figcaption></figure>')

    def test_refs_become_links_across_panes(self):
        out = self.built("<h2>甲</h2><h3>乙</h3><h3 id='keep'>丙</h3><p>見 §1.1 和 §1.2，沒有 §9</p>"
                         '<p><a href="#x">§1</a></p><h2>丁</h2>', "<h2>例</h2><p>用到 §1.1</p>")
        self.assertIn('見 <a class="ref" href="#s1-1">§1.1</a> 和 <a class="ref" href="#keep">§1.2</a>，沒有 §9', out)
        self.assertIn('用到 <a class="ref" href="#s1-1">§1.1</a>', out)
        self.assertIn('<a href="#x">§1</a>', out)
        self.assertRegex(out, r'<h2[^>]*><span class="num">§1</span> 甲')

    def test_main_refuses_to_write_on_violation(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "guide-src.html"
            src.write_text(page('<h2>一</h2><img src="a.png">'), encoding="utf-8")
            self.assertEqual(build.main([str(src)]), 1)
            self.assertFalse((Path(d) / "guide.html").exists())


class MetaStep(unittest.TestCase):
    """add_meta：每個編號的 h2 帶 data-n、data-min、data-short，後面接一行約幾分鐘；講義段再列出用到它的題目。"""

    def run_meta(self, course, problems="<h2>例</h2><p>題目</p>"):
        src, anchors = numbered(course, problems)
        return build.add_meta(src, anchors)

    def test_minutes_follow_text_units(self):
        out = self.run_meta(f"<h2>甲</h2><p>{'字' * 160}</p><h2>乙</h2><p>{'字' * 400}</p><h2>丙</h2>")
        for n, minutes in ((1, 2), (2, 5), (3, 1), (4, 1)):  # 沒有字也至少 1 分鐘
            with self.subTest(n=n):
                tag = h2_tag(out, f"s{n}")
                self.assertIn(f'data-n="{n}"', tag)
                self.assertIn(f'data-min="{minutes}"', tag)
                self.assertRegex(meta_of(out, f"s{n}"), rf"^約 {minutes} 分鐘")

    def test_minutes_ignore_markup_whitespace_and_heading_text(self):
        plain = self.run_meta(f"<h2>甲</h2><p>{'字' * 240}</p>")
        marked = self.run_meta(f"<H2 class='x'>換個標題</H2>\n<p><b>{'字' * 120}</b>\n  <i>{'字' * 120}</i></p>\n")
        self.assertIn('data-min="3"', h2_tag(plain, "s1"))
        self.assertIn('data-min="3"', h2_tag(marked, "s1"))

    def test_short_title_drops_the_trailing_page_note(self):
        cases = {"甲（講義 p.3）": "甲", "乙 (pp.3-4)": "乙", "丙（Topic 3 p.12）": "丙",
                 "丁（trend）": "丁（trend）", "戊 p.3 的例子": "戊 p.3 的例子"}
        for title, short in cases.items():
            with self.subTest(title=title):
                self.assertIn(f'data-short="{short}"', h2_tag(self.run_meta(f"<h2>{title}</h2>"), "s1"))

    def test_last_course_section_stops_at_the_problems_part(self):
        """講義最後一段的分鐘數只算到講義那部結束：題目那部開頭的速查卡不算它的。"""
        src, anchors = build.number_headings(page("<h2>甲</h2><p>字</p>", close=False, types=f"<p>{'字' * 400}</p>"))
        self.assertIn('data-min="1"', h2_tag(build.add_meta(build.link_refs(src, anchors), anchors), "s1"))

    def test_first_problem_right_after_the_part_opens_still_counts(self):
        """題目那部一開頭就是 h2 時，它連到的講義段照樣列出它。"""
        src, anchors = build.number_headings(page("<h2>甲</h2>", "<h2>例</h2><p>見 §1</p>", close=False, types=""))
        self.assertIn("用到這頁的題目", meta_of(build.add_meta(build.link_refs(src, anchors), anchors), "s1"))

    def test_class_names_match_whole_words(self):
        """class 要整個字相符：cheat-x 不是 cheat。"""
        card = '<div class="cheat-x">卡</div>'
        self.assertEqual(build.add_cheat(card), card)

    def test_author_short_title_is_kept(self):
        tag = h2_tag(self.run_meta('<h2 data-short="自訂">甲（講義 p.3）</h2>'), "s1")
        self.assertEqual(tag.count("data-short"), 1)
        self.assertIn('data-short="自訂"', tag)

    def test_course_section_lists_the_problems_that_link_to_it(self):
        out = self.run_meta("<h2>甲</h2><h3>子</h3><h2>乙</h2><p>回頭看 §1</p><h2>丙</h2>",
                            "<h2>例一</h2><p>用到 §1.1、§1 和 §2</p><p>再看 §1</p><h2>例二</h2><p>見 §1，同 §4</p>")
        a, b = '<a class="ref" href="#s4">§4</a>', '<a class="ref" href="#s5">§5</a>'
        self.assertTrue(meta_of(out, "s1").endswith(f"用到這頁的題目 {a}、{b}"), meta_of(out, "s1"))
        self.assertTrue(meta_of(out, "s2").endswith(f"用到這頁的題目 {a}"), meta_of(out, "s2"))
        self.assertNotIn("用到這頁", meta_of(out, "s3"))  # 沒有題目連到丙
        for anchor in ("s4", "s5"):  # 題目段自己不列，就算有別段連到它（§4）
            self.assertNotIn("用到這頁", meta_of(out, anchor))

    def test_list_does_not_depend_on_markup_around_the_ref(self):
        for body in (f"<h2>例一</h2>{USES}" + ans(ORIGIN + CALC),
                     '<h2>例一</h2><UL CLASS="x  uses">\n<li>見\n§1</li></UL>',
                     "<h2>例一</h2>" + ans("<p>見 <b>§1</b></p>")):
            with self.subTest(body=body[:30]):
                out = self.run_meta("<h2>甲</h2>", body)
                self.assertIn('用到這頁的題目 <a class="ref" href="#s2">§2</a>', meta_of(out, "s1"))

    def test_section_nobody_links_to_has_only_minutes(self):
        out = self.run_meta("<h2>甲</h2><p>見 §1</p>", "<h2>例</h2><p>沒有連結</p>")
        self.assertRegex(meta_of(out, "s1"), r"^約 \d+ 分鐘$")


class CheatStep(unittest.TestCase):
    """add_cheat：速查卡前面加不編號的標題和兩個按鈕。"""
    CARD = '<div class="cheat"><table class="types"></table></div>'

    def test_heading_and_tools_come_right_before_the_card(self):
        out = build.add_cheat(f"<section>{self.CARD}</section>")
        self.assertTrue(out.startswith('<section><h2 class="plain" id="cheat">速查卡</h2><p class="cheat-tools">'), out)
        self.assertTrue(out.endswith(f"{self.CARD}</section>"))
        for act in ("print", "answers"):
            self.assertEqual(out.count(f'data-act="{act}"'), 1)

    def test_formatting_variants_still_get_it(self):
        for card in ('<DIV id="c" CLASS=\'wide cheat\'>x</DIV>', '<div class="cheat" data-x="1">x</div>'):
            with self.subTest(card=card):
                out = build.add_cheat(f"<section>\n{card}</section>")
                self.assertEqual(out.count('id="cheat"'), 1)
                self.assertLess(out.index('id="cheat"'), out.index("x</"))
                self.assertTrue(out.endswith(f"{card}</section>"))

    def test_only_the_first_card_gets_one(self):
        out = build.add_cheat(self.CARD + self.CARD)
        self.assertEqual(out.count('id="cheat"'), 1)

    def test_no_card_changes_nothing(self):
        for src in ("<section><p>沒有</p></section>", '<div class="cheatsheet">x</div>', '<div class="x">cheat</div>'):
            with self.subTest(src=src):
                self.assertEqual(build.add_cheat(src), src)


class TermsStep(unittest.TestCase):
    """add_terms：最後加名詞表，每個 <dfn> 一列，連到它前面最近的編號標題。"""
    ROW = re.compile(r'<li><a class="ref" href="#([^"]+)">(.*?)</a><span>(.*?)</span><span class="where">§([^<]*)</span></li>')

    def terms(self, src):
        src, anchors = build.number_headings(src)
        return build.add_terms(src, anchors)

    def rows(self, out):
        return self.ROW.findall(out)

    def test_one_row_per_dfn_sorted_ignoring_case(self):
        out = self.terms('<section class="course"><p><dfn>前言</dfn></p><h2>甲</h2><p><dfn>banana</dfn>（香蕉）</p>'
                         '<h3>乙</h3><p><dfn>Apple</dfn> (red)</p><p><dfn>cherry</dfn>是水果（不算別名）</p></section>'
                         '<section class="problems"><h2>例</h2><p><dfn>Zed</dfn></p></section>')
        self.assertEqual(self.rows(out), [("s1-1", "Apple", "red", "1.1"), ("s1", "banana", "香蕉", "1"),
                                          ("s1-1", "cherry", "", "1.1"), ("s2", "Zed", "", "2")])

    def test_table_goes_before_the_last_section_end(self):
        out = self.terms('<section class="course"><h2>甲</h2><p><dfn>a</dfn></p></section>'
                         '<section class="problems"><h2>例</h2><p>題</p></section>')
        self.assertTrue(out.endswith('<h2 class="plain" id="terms">名詞表</h2>' + out.split('名詞表</h2>', 1)[1]))
        self.assertRegex(out, r'題</p><h2 class="plain" id="terms">名詞表</h2>.*<ul class="terms">.*</ul></section>$')
        self.assertEqual(out.count('id="terms"'), 1)

    def test_formatting_variants(self):
        out = self.terms('<section><h2 id="own">甲</h2><p><DFN class="x"><b>beta</b></DFN>\n（β）</p>'
                         '<p><dfn> Alpha </dfn>\n\n(a)</p></section>')
        self.assertEqual(self.rows(out), [("own", " Alpha ", "a", "1"), ("own", "<b>beta</b>", "β", "1")])

    def test_no_dfn_changes_nothing(self):
        src = '<section class="course"><h2>甲</h2><p>沒有名詞</p></section>'
        numbered_src, anchors = build.number_headings(src)
        self.assertEqual(build.add_terms(numbered_src, anchors), numbered_src)

    def test_dfn_before_any_heading_is_not_listed(self):
        src, anchors = build.number_headings('<section><p><dfn>前言</dfn></p></section>')
        self.assertEqual(build.add_terms(src, anchors), src)


class PartStep(unittest.TestCase):
    """add_parts：每一部開頭補 p.part，作者寫過的那一部不補。"""

    def parts(self, course, problems):
        return build.add_parts(page(course, problems, close=False, types=""))

    def test_each_pane_gets_its_label_before_the_first_h2(self):
        out = self.parts("<h2>甲</h2><h2>乙</h2>", "<h2>例</h2>")
        self.assertEqual(out.count('class="part"'), 2)
        self.assertIn('<p class="part">講義</p><h2>甲</h2>', out)
        self.assertIn('<p class="part">題目</p><h2>例</h2>', out)

    def test_author_part_is_kept_and_not_doubled(self):
        out = self.parts('<P CLASS="x part">第一部</P>\n<h2>甲</h2>', "<h2>例</h2>")
        self.assertNotIn("講義</p>", out)
        self.assertEqual(out.count("part"), 2)
        self.assertIn("第一部", out)
        self.assertIn('<p class="part">題目</p><h2>例</h2>', out)

    def test_part_in_the_other_pane_does_not_count(self):
        out = self.parts("<h2>甲</h2>", '<p class="part">第二部</p><h2>例</h2>')
        self.assertIn('<p class="part">講義</p><h2>甲</h2>', out)
        self.assertNotIn("題目</p>", out)

    def test_both_authored_changes_nothing(self):
        src = page('<p class="part">一</p><h2>甲</h2>', '<p class="part">二</p><h2>例</h2>', close=False, types="")
        self.assertEqual(build.add_parts(src), src)


class PanelStep(unittest.TestCase):
    """add_panel：aside.panel 換成 div#panel，裡面只留帶 data-tab 的 figure，原樣不動。"""
    T1 = '<figure data-tab="Z 表"><img src="a.png" data-zh="a.zh.png"><figcaption>Tables p.1</figcaption></figure>'
    T2 = '<figure data-tab="t 表"><img src="b.png"><figcaption>Tables p.2</figcaption></figure>'

    def test_aside_becomes_a_div_with_the_same_figures(self):
        out = build.add_panel(f"<body><aside class='wide panel'>{self.T1}\n{self.T2}</aside></body>")
        self.assertEqual(out, f'<body><div id="panel">{self.T1}{self.T2}</div></body>')

    def test_formatting_variants(self):
        for aside in ("<ASIDE data-label='查表' CLASS='panel'>{}</ASIDE>", '<aside class="panel wide">\n{}\n</aside >'):
            with self.subTest(aside=aside[:20]):
                out = build.add_panel("<p>前</p>" + aside.format(self.T1 + self.T2) + "<p>後</p>")
                self.assertEqual(out, f'<p>前</p><div id="panel">{self.T1}{self.T2}</div><p>後</p>')

    def test_no_header_tabs_or_close_button(self):
        out = build.add_panel(f'<aside class="panel">{self.T1}{self.T2}</aside>')
        self.assertNotIn("<button", out)
        self.assertNotIn("<aside", out)

    def test_other_aside_and_no_panel_stay(self):
        for src in (f'<aside class="notes">{self.T1}</aside>', "<p>沒有</p>"):
            with self.subTest(src=src[:20]):
                self.assertEqual(build.add_panel(src), src)


class ShellStep(unittest.TestCase):
    """outline / rail / add_shell：左邊目錄、頁眉、正文、旁邊打開的那一段。"""

    @staticmethod
    def shell(body, head=""):
        return build.add_shell(f"<html><head>{head}</head><body>{body}</body></html>")

    @staticmethod
    def rail_of(out):
        return out[out.index('<nav class="rail"'):out.index("</nav>")]

    @staticmethod
    def head_of(out):
        return out[out.index('<div class="head">'):out.index('<div class="page">')]

    def test_wraps_the_body_in_rail_main_and_peek(self):
        out = self.shell("<p>內文</p>")
        order = [out.index(x) for x in ('<body><nav class="rail"', "</nav><main>", '<div class="head">', '<div class="page"><p>內文</p>',
                                        "</div></main>", 'class="scrim"', 'class="peek"', "</body>")]
        self.assertEqual(order, sorted(order))

    def test_h1_gets_an_id_digest_note_and_a_hidden_resume(self):
        out = self.shell("<h1>書名</h1><p>x</p>")
        self.assertRegex(out, r'<h1 id="top">書名</h1><p class="digest-note">.*?data-act="digest-off".*?</p><p class="resume" hidden>')
        self.assertEqual(out.count('class="digest-note"'), 1)

    def test_h1_with_its_own_id_keeps_it(self):
        for h1 in ('<h1 id="mine">書名</h1>', '<H1 CLASS="x" id = \'mine\'>書名</H1>'):
            with self.subTest(h1=h1):
                out = self.shell(h1)
                self.assertNotIn('id="top"', out)
                self.assertIn('class="digest-note"', out)
                self.assertIn('<a href="#mine">', self.rail_of(out))

    def test_book_name_comes_from_h1_then_title(self):
        self.assertIn('<p class="book">書名</p>', self.rail_of(self.shell("<h1>書<b>名</b></h1>", head="<title>別的</title>")))
        self.assertIn('<p class="book">別的</p>', self.rail_of(self.shell("<p>x</p>", head="<title>別的</title>")))

    def test_tool_buttons_only_for_ids_that_exist(self):
        bodies = {"cheat": '<h2 class="plain" id="cheat">速查卡</h2>', "terms": '<h2 id="terms" class="plain">名詞表</h2>',
                  "panel": '<div id="panel"></div>'}
        for act, body in bodies.items():
            with self.subTest(act=act):
                out = self.shell(body)
                for where in (self.head_of(out), self.rail_of(out)):
                    for other in bodies:
                        self.assertEqual(f'data-act="{other}"' in where, other == act, (other, where))
        none = self.shell("<p>x</p>")
        for act in bodies:
            self.assertNotIn(f'data-act="{act}"', self.head_of(none) + self.rail_of(none))
        for act in ("nav", "digest-toggle"):
            self.assertIn(f'data-act="{act}"', self.head_of(none))

    def test_lang_switch_only_with_a_translated_image(self):
        for img in ('<img src="a.png" data-zh="b.png">', '<IMG SRC=a DATA-ZH = "b">'):
            with self.subTest(img=img):
                rail = self.rail_of(self.shell(f"<figure>{img}</figure>"))
                self.assertIn('data-act="lang-en"', rail)
                self.assertIn('data-act="lang-zh"', rail)
        for body in ('<img src="a.png">', '<p>data-zh</p>', '<img src="a.png" data-zhx="b">'):
            with self.subTest(body=body):
                rail = self.rail_of(self.shell(body))
                self.assertNotIn("lang-en", rail)
                self.assertNotIn("lang-zh", rail)

    def test_theme_switch_is_always_there(self):
        for body in ("<p>x</p>", '<img data-zh="b.png">'):
            rail = self.rail_of(self.shell(body))
            self.assertIn('data-act="theme-light"', rail)
            self.assertIn('data-act="theme-dark"', rail)

    def test_rail_groups_items_and_subsections(self):
        body = ('<h1 id="top">書名</h1><section class="course"><p class="part">講義<span>約 1 小時</span></p>'
                + h2(1, "甲") + '<h3 id="s1-1"><span class="num">§1.1</span> 乙</h3>'
                + '<section class="problems"><p class="part">題目</p>' + h2(2, "例") + h2(3, "總結", "recap"))
        rail = self.rail_of(self.shell(body))
        self.assertEqual(re.findall(r"<h2>(.*?)</h2>", rail),
                         ["開始<span></span>", "講義<span>約 1 小時</span>", "題目<span></span>", "總結<span></span>"])
        self.assertIn('<a href="#s1"><span class="n">1</span><span class="t">甲</span>', rail)
        self.assertIn('<ol class="sub"><li><a href="#s1-1">§1.1 乙</a></li></ol>', rail)
        for sid in ("s1", "s2", "s3"):
            self.assertIn(f'<i data-for="{sid}"></i>', rail)
        self.assertNotIn('data-for="top"', rail)  # 進度條只數編號的段

    def test_outline_groups_and_titles(self):
        src, anchors = numbered("<h2>甲（講義 p.3）</h2><h3>乙</h3><h3>丙</h3><h2 data-short='自訂'>丁</h2>",
                                '<h2>例</h2><h2 class="recap">總結</h2>')
        src = build.add_parts(build.add_meta(src, anchors))
        groups = build.outline(src)
        self.assertEqual([g["label"] for g in groups], ["講義", "題目", "總結"])
        course = groups[0]["items"]
        self.assertEqual([(i["id"], i["n"], i["title"]) for i in course], [("s1", "1", "甲"), ("s2", "2", "自訂")])
        self.assertEqual(course[0]["subs"], [("s1-1", "§1.1 乙"), ("s1-2", "§1.2 丙")])
        self.assertEqual([i["title"] for i in groups[1]["items"]], ["例"])
        self.assertEqual([i["title"] for i in groups[2]["items"]], ["總結"])

    def test_outline_skips_empty_groups_and_names_the_h1_item(self):
        src = '<h1 id="top">書名</h1>' + h2(1, "甲") + '<section><p class="part">空的</p></section>'
        groups = build.outline(src)
        self.assertEqual([g["label"] for g in groups], ["開始"])
        self.assertEqual([(i["id"], i["n"], i["title"]) for i in groups[0]["items"]],
                         [("top", "", "開始之前"), ("s1", "1", "甲")])

    def test_outline_recap_group_ignores_markup_variants(self):
        for h in ('<H2 id="s2" data-n="2" CLASS="x recap">總結</H2>', "<h2 id='s2' data-n='2' class='recap x'>全部總結</h2>"):
            with self.subTest(h=h):
                groups = build.outline(h2(1, "甲") + "\n" + h)
                self.assertEqual([g["label"] for g in groups], ["開始", "總結"])


class AssetStep(unittest.TestCase):
    """組好的頁每一步都順著新的版面：重新跑 build 不會重複加東西。"""

    def test_shell_pieces_appear_once(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.png").write_bytes(PNG)
            src = page("<h2>甲</h2><p><dfn>趨勢</dfn>（trend）是長期方向</p>", "<h2>例</h2>",
                       cover=COVER.replace(' data-zh="a.png"', ""))
            out = build.build(src, Path(d)).split("</style>", 1)[1]
        for piece in ('<nav class="rail"', "<main>", 'id="cheat"', 'id="terms"', 'class="scrim"', 'class="peek"',
                      '<p class="part">講義</p>', '<p class="part">題目</p>'):
            with self.subTest(piece=piece):
                self.assertEqual(out.count(piece), 1)
        self.assertIn('<a class="ref" href="#s1">趨勢</a><span>trend</span><span class="where">§1</span>', out)


def cheat_with(*formulas):
    """速查卡：題型表後面接「要背的公式」。"""
    return TYPES.replace("{n}", "2").replace("</table>", "</table><h4>要背的公式</h4>" + "".join(formulas))


def formula(math):
    return f'<div class="formula"><math display="block">{math}</math></div>'


ONE = "<mi>MAD</mi><mo>=</mo><mfrac><mi>e</mi><mi>n</mi></mfrac>"
# 一條公式就比正文欄寬
WIDE_FORMULA = formula("<mi>U</mi><mo>=</mo>" + "<mi>y</mi><mo>+</mo>" * 120 + "<mn>1</mn>")


class CheatFormulaRule(unittest.TestCase):
    """速查卡的公式一條一行：用寬的 <mspace> 把幾條接在同一行會紅。"""

    def test_formulas_joined_by_a_wide_gap_fail(self):
        for gap in ('<mspace width="2em"/>', "<mspace width='1em'></mspace>", '<MSPACE WIDTH=" 1.5em "/>'):
            with self.subTest(gap=gap):
                probs = build.lint(page(types=cheat_with(formula(ONE + gap + ONE))))
                self.assertTrue(any("一條一行" in p for p in probs), probs)

    def test_one_formula_per_line_passes(self):
        src = page(types=cheat_with(formula(ONE), formula(ONE)))
        self.assertTrue(ok(src), build.lint(src))

    def test_a_small_gap_after_a_label_passes(self):
        for gap in ('<mspace width="0.3em"/>', '<mspace width=".9em"/>', "<mspace/>", '<mspace width="4px"/>'):
            with self.subTest(gap=gap):
                src = page(types=cheat_with(formula("<mtext>加法</mtext>" + gap + ONE)))
                self.assertTrue(ok(src), build.lint(src))

    def test_wide_gap_outside_the_cheat_sheet_passes(self):
        src = page(course=COURSE + formula('<mi>a</mi><mspace width="2em"/><mi>b</mi>'))
        self.assertTrue(ok(src), build.lint(src))


class Clipped(unittest.TestCase):
    """clipped：從量好的 DOM 讀出被自己的捲軸切掉的容器。"""

    def dom(self, found):
        content = build.html.escape(build.json.dumps(found, ensure_ascii=False), quote=True)
        return f'<html><head><meta name="clipped" content="{content}"></head><body></body></html>'

    def test_each_clipped_box_becomes_a_problem(self):
        probs = build.clipped(self.dom([{"el": "div.formula", "over": 58, "text": 'MAD = "x" & <y>'}]), 1440)
        self.assertEqual(len(probs), 1)
        for piece in ("1440px", "<div.formula>", "58px", 'MAD = "x" & <y>', "被切掉"):
            self.assertIn(piece, probs[0])

    def test_nothing_clipped_or_not_measured_gives_nothing(self):
        self.assertEqual(build.clipped(self.dom([]), 1440), [])
        self.assertEqual(build.clipped("<html><head></head></html>", 1440), [])

    def test_the_page_script_writes_the_meta_this_reads(self):
        self.assertIn('meta.name = "clipped"', build.FIND_CLIPPED)


class Overflow(unittest.TestCase):
    def run_main(self, problems=PROBLEMS, types=None, **kw):
        d = Path(tempfile.mkdtemp())
        (d / "a.png").write_bytes(PNG)
        (d / "guide-src.html").write_text(page(problems=problems, types=types), encoding="utf-8")
        return build.main([str(d / "guide-src.html")], **kw), d / "guide.html"

    def test_overflow_writes_nothing(self):
        code, out = self.run_main(measure=lambda out: ["視窗寬 390px：整頁被撐寬 120px"])
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())

    def test_no_overflow_or_no_browser_writes_the_page(self):
        for found in ([], None):
            with self.subTest(found):
                code, out = self.run_main(measure=lambda out, found=found: found)
                self.assertEqual(code, 0)
                self.assertTrue(out.is_file())

    @unittest.skipUnless(build.overflow.find_browser(), "本機沒有 Chrome 或 Edge")
    def test_formula_wider_than_the_column_is_refused(self):
        # 比正文欄寬的公式在自己那一行橫向捲動，不撐寬整頁，但寬螢幕上右邊看起來被切掉：不產出
        err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with contextlib.redirect_stderr(err):
            code, out = self.run_main(types=cheat_with(WIDE_FORMULA))
        err.flush()
        said = err.buffer.getvalue().decode("utf-8")
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())
        self.assertIn("被切掉", said)
        self.assertNotIn("被撐寬", said)  # 它沒有撐寬整頁，只是自己被切

    @unittest.skipUnless(build.overflow.find_browser(), "本機沒有 Chrome 或 Edge")
    def test_formulas_that_fit_are_delivered(self):
        code, out = self.run_main(types=cheat_with(formula(ONE), formula(ONE)))
        self.assertEqual(code, 0)
        self.assertTrue(out.is_file())

    @unittest.skipUnless(build.overflow.find_browser(), "本機沒有 Chrome 或 Edge")
    def test_unbreakable_text_outside_a_scroller_is_refused(self):
        code, out = self.run_main(problems=PROBLEMS + '<p><code style="white-space:nowrap">' + "x = 1; " * 300 + "</code></p>")
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
