"""practice.py 的規則閘門與組頁：每條規則都驗兩個方向。

違規要紅（而且是那一條在紅）；只改無關的格式（引號、屬性順序、大小寫、題目代號的命名）不能紅。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import base64
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "practice.py"
spec = importlib.util.spec_from_file_location("practice", SCRIPT)
practice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(practice)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
GUIDE = '<html><body><table class="types"><tr data-type="acf-read"><td>ACF</td></tr></table><h2 id="s1">§1 符號</h2><h3 id="s1-2">§1.2</h3><h2 id="s16">§16 Eg 1</h2><h2 id="s20">§20 A4</h2></body></html>'
BODY = 'data-title="Topic 4 練習" data-key="isom3031-topic4" data-guide="guide.html" data-answers="ans.md"'


FILL = '<p class="fill" data-answer="t|t 分配" data-why="σ 未知，用 t">用哪一個：</p>'


def drill(qid, text="這題用 t 還是 Z？"):
    return (f'<section class="q drill" data-id="{qid}"><h2>基本功</h2><p>{text}</p>'
            f'{FILL}</section>')


DRILLS = drill("which-table") + drill("which-tail") + drill("critical-value")
MODEL = ('<details class="model"><div class="sheet"><p>The series is stationary.</p></div>'
         '<ul class="rubric"><li data-marks="2">說出沒有趨勢</li><li data-marks="1">結論句</li></ul></details>')
ONE = ('<section class="q" data-id="acf-seasonal" data-type="acf-read" data-differs="有季節性沒有趨勢，Eg 1 有趨勢">'
       '<h2>練習 1</h2><p class="ref">對照 Eg 1（導讀頁 §16、§20）</p><p>畫時間序列圖。</p>' + MODEL + '</section>')
TWO = ONE.replace("acf-seasonal", "acf-trend").replace("練習 1", "練習 2")
FULL = ONE + TWO
PANEL = ('<aside class="panel" data-label="查表"><figure data-tab="Z 表"><img src="z.png" data-zh="z.zh.png">'
         '<figcaption>Statistical Tables p.1</figcaption></figure></aside>')
IDS = ["which-table", "which-tail", "critical-value", "acf-seasonal", "acf-trend"]


def src(inner=None, body=BODY):
    inner = DRILLS + FULL if inner is None else inner
    return f'<!DOCTYPE html><html><head><title>x</title></head><body {body}>{PANEL}{inner}</body></html>'


class Case(unittest.TestCase):
    """每個測試一個暫存資料夾：導讀頁、答案檔、圖片都在裡面。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "guide.html").write_text(GUIDE, encoding="utf-8")
        self.answers(IDS)
        for name in ("z.png", "z.zh.png", "q.png", "q.zh.png"):
            (self.dir / name).write_bytes(PNG)

    def tearDown(self):
        self.tmp.cleanup()

    def answers(self, ids):
        (self.dir / "ans.md").write_text("\n".join(f"## {i}\n答案" for i in ids), encoding="utf-8")

    def problems(self, s):
        return practice.lint(s, self.dir, self.dir)

    def assertRed(self, s, key):
        probs = self.problems(s)
        self.assertTrue(any(key in p for p in probs), f"想要有「{key}」，實際：{probs}")

    def assertGreen(self, s):
        self.assertEqual(self.problems(s), [])


class Baseline(Case):
    def test_valid_page_passes(self):
        self.assertGreen(src())

    def test_formatting_variants_pass(self):
        body = BODY.replace('"', "'").replace("data-title='Topic 4 練習' ", "") + " DATA-TITLE='Topic 4 練習'"
        inner = (DRILLS.replace('class="q drill" data-id="which-table"', "data-id='which-table' class='drill q extra'")
                 + FULL.replace('class="q" data-id="acf-seasonal"', "data-id='acf-seasonal'  class='q'"))
        self.assertGreen(src(inner, body))


class BodyRule(Case):
    def test_missing_attr_fails(self):
        for attr in practice.BODY_ATTRS:
            with self.subTest(attr=attr):
                body = re.sub(rf'{attr}="[^"]*"\s*', "", BODY)
                self.assertRed(src(body=body), attr)


class IdRule(Case):
    def test_ordinal_ids_fail(self):
        for bad in ("q1", "Q-3", "drill2", "practice-4", "7", "ex12b"):
            with self.subTest(bad=bad):
                self.answers(IDS + [bad])
                self.assertRed(src(DRILLS + FULL.replace("acf-seasonal", bad)), "不能只是編號")

    def test_missing_id_fails(self):
        self.assertRed(src(DRILLS + FULL.replace(' data-id="acf-seasonal"', "")), "沒有 data-id")

    def test_duplicate_id_fails(self):
        self.assertRed(src(DRILLS + drill("which-tail") + FULL), "重複")

    def test_renamed_slug_passes(self):
        for good in ("eg1-acf", "seasonal-acf-99", "t-or-z"):
            with self.subTest(good=good):
                self.answers(IDS + [good])
                self.assertGreen(src(DRILLS + FULL.replace("acf-seasonal", good)))


class DrillRule(Case):
    def test_too_few_drills_fail(self):
        self.assertRed(src(drill("which-table") + drill("which-tail") + FULL), "基本功小題")

    def test_drill_after_full_fails(self):
        self.assertRed(src(drill("which-table") + drill("which-tail") + FULL + drill("critical-value")), "排在完整題目前面")

    def test_no_full_problem_fails(self):
        self.assertRed(src(DRILLS), "沒有完整題目")

    def test_drills_need_no_ref_or_differs(self):
        self.assertGreen(src(DRILLS.replace("<p>", '<p class="ref">對照 §1.2</p><p>', 1) + FULL))


class FillRule(Case):
    def test_drill_without_fill_fails(self):
        self.assertRed(src(DRILLS.replace(FILL, "", 1) + FULL), "沒有填答格")

    def test_fill_without_answer_fails(self):
        for bad in ('data-answer=""', 'data-answer=" | "'):
            with self.subTest(bad=bad):
                self.assertRed(src(DRILLS.replace('data-answer="t|t 分配"', bad, 1) + FULL), "沒有 data-answer")

    def test_drill_fill_without_why_fails(self):
        self.assertRed(src(DRILLS.replace(' data-why="σ 未知，用 t"', "", 1) + FULL), "沒有 data-why")

    def test_fill_outside_question_fails(self):
        self.assertRed(src(FILL + DRILLS + FULL), "不在題目裡")

    def test_bad_tolerance_fails(self):
        self.assertRed(src(DRILLS.replace('class="fill"', 'class="fill" data-tol="-1"', 1) + FULL), "data-tol")

    def test_full_problem_fill_needs_no_why(self):
        fill = "<span data-tol='0.005' class='final fill' data-answer='2.26'>t =</span>"
        self.assertGreen(src(DRILLS + FULL.replace("<p>畫時間序列圖。</p>", f"<p>算 t。</p>{fill}")))

    def test_full_problem_needs_no_fill(self):
        self.assertGreen(src(DRILLS + FULL))


class RefRule(Case):
    def test_full_without_ref_fails(self):
        self.assertRed(src(DRILLS + FULL.replace('<p class="ref">對照 Eg 1（導讀頁 §16、§20）</p>', "")), ".ref")

    def test_section_mark_outside_ref_does_not_count(self):
        no_ref = FULL.replace('<p class="ref">對照 Eg 1（導讀頁 §16、§20）</p>', "<p>見 §16</p>")
        self.assertRed(src(DRILLS + no_ref), ".ref")

    def test_missing_anchor_fails(self):
        self.assertRed(src(DRILLS + FULL.replace("§20", "§21")), "§21")

    def test_missing_guide_fails(self):
        (self.dir / "guide.html").unlink()
        self.assertRed(src(), "找不到導讀頁")

    def test_ref_variants_pass(self):
        for ref in ('<span class="note ref">§16</span>', '<div class="ref">對照 §1.2 和 §16</div>'):
            with self.subTest(ref=ref):
                self.assertGreen(src(DRILLS + FULL.replace('<p class="ref">對照 Eg 1（導讀頁 §16、§20）</p>', ref)))


class DiffersRule(Case):
    def test_missing_differs_fails(self):
        self.assertRed(src(DRILLS + re.sub(r' data-differs="[^"]*"', "", FULL)), "data-differs")

    def test_blank_differs_fails(self):
        self.assertRed(src(DRILLS + re.sub(r'data-differs="[^"]*"', 'data-differs="  "', FULL)), "data-differs")


class TypeRule(Case):
    """每題寫明練的是題型表的哪一列；每個題型至少兩題變式。"""
    TYPES2 = GUIDE.replace("</table>", '<tr data-type="mad"><td>MAD</td></tr></table>')

    def test_missing_type_fails(self):
        self.assertRed(src(DRILLS + ONE.replace(' data-type="acf-read"', "") + TWO), "沒有 data-type")

    def test_unknown_type_fails(self):
        self.assertRed(src(DRILLS + ONE.replace("acf-read", "acf-raed") + TWO), "不在導讀頁的題型表裡")

    def test_too_few_per_type_fails(self):
        self.answers(IDS[:-1])
        self.assertRed(src(DRILLS + ONE), "只有 1 題變式")

    def test_originals_do_not_count(self):
        self.assertRed(src(DRILLS + ONE + TWO.replace("有季節性沒有趨勢，Eg 1 有趨勢", "老師原題")), "只有 1 題變式")

    def test_uncovered_type_fails(self):
        (self.dir / "guide.html").write_text(self.TYPES2, encoding="utf-8")
        self.assertRed(src(), "'mad' 只有 0 題")

    def test_one_question_can_cover_several_types(self):
        (self.dir / "guide.html").write_text(self.TYPES2, encoding="utf-8")
        self.assertGreen(src(DRILLS + FULL.replace('data-type="acf-read"', "data-type='mad  acf-read'")))

    def test_guide_without_types_fails(self):
        (self.dir / "guide.html").write_text(GUIDE.replace(' data-type="acf-read"', ""), encoding="utf-8")
        self.assertRed(src(), "題型表沒有 data-type")

    def test_drills_need_no_type(self):
        self.assertGreen(src())


class NoAnswerRule(Case):
    def test_answer_blocks_fail(self):
        for leak in ('<details><summary>答案</summary>r4 顯著</details>', '<div class="calc">r = 0.4</div>',
                     '<div class="sheet">Since …</div>', '<p class="trap">別用 1.96</p>', '<div class="answer">x</div>'):
            with self.subTest(leak=leak):
                self.assertRed(src(DRILLS + FULL.replace("<p>畫時間序列圖。</p>", leak)), "做法和答案放進")

    def test_question_markup_passes(self):
        q = ('<div class="en">Plot it.<ol><li>a</li></ol></div><div class="zh note">畫圖。</div>'
             '<table><tr><th>t</th><td>1</td></tr></table><pre class="mtb">Lag ACF</pre>'
             '<figure><img src="q.png" data-zh="q.zh.png"><figcaption>Eg p.2</figcaption></figure>')
        self.assertGreen(src(DRILLS + FULL.replace("<p>畫時間序列圖。</p>", q)))

    def test_model_may_hold_answer_blocks(self):
        rich = MODEL.replace('<ul class="rubric">', '<div class="calc">r = 0.4</div><p class="trap">別用 1.96</p><ul class="rubric">')
        self.assertGreen(src(DRILLS + FULL.replace(MODEL, rich)))

    def test_own_pad_fails(self):
        self.assertRed(src(DRILLS + FULL.replace("<p>畫時間序列圖。</p>", '<div class="pad"></div>')), "不用自己放 .pad")


class ModelRule(Case):
    """每題完整題目一個範本答案，裡面有帶分數的給分點；讀圖題型的題目要有圖或軟體輸出。"""
    READS = GUIDE.replace('data-type="acf-read"', 'data-reads="figure" data-type="acf-read"')
    FIG = '<figure data-tr="none"><img src="q.png"><figcaption>gen.py 畫的 ACF</figcaption></figure>'

    def test_missing_model_fails(self):
        self.assertRed(src(DRILLS + ONE.replace(MODEL, "") + TWO), "要有一個 <details class=\"model\">")

    def test_two_models_fail(self):
        self.assertRed(src(DRILLS + ONE.replace(MODEL, MODEL + MODEL) + TWO), "現在 2 個")

    def test_model_without_rubric_fails(self):
        self.assertRed(src(DRILLS + ONE.replace('<li data-marks="2">說出沒有趨勢</li><li data-marks="1">結論句</li>', "") + TWO),
                       "沒有給分點")

    def test_rubric_item_without_marks_fails(self):
        for bad in ("<li>結論句</li>", '<li data-marks="0">結論句</li>', '<li data-marks="一">結論句</li>'):
            with self.subTest(bad=bad):
                self.assertRed(src(DRILLS + ONE.replace('<li data-marks="1">結論句</li>', bad) + TWO), "沒有 data-marks")

    def test_model_formatting_variants_pass(self):
        m = MODEL.replace('<details class="model">', "<DETAILS open class='model wide'>").replace('data-marks="2"', "data-marks=' 3 '")
        self.assertGreen(src(DRILLS + ONE.replace(MODEL, m) + TWO))

    def test_drills_need_no_model(self):
        self.assertGreen(src())

    def test_figure_type_without_figure_fails(self):
        (self.dir / "guide.html").write_text(self.READS, encoding="utf-8")
        self.assertRed(src(), "卻沒有圖")

    def test_figure_inside_model_does_not_count(self):
        (self.dir / "guide.html").write_text(self.READS, encoding="utf-8")
        inner = FULL.replace('<ul class="rubric">', self.FIG + '<ul class="rubric">')
        self.assertRed(src(DRILLS + inner), "卻沒有圖")

    def test_figure_or_output_in_question_passes(self):
        (self.dir / "guide.html").write_text(self.READS, encoding="utf-8")
        for shown in (self.FIG, '<pre class="mtb">Lag  ACF  T  LBQ</pre>'):
            with self.subTest(shown=shown[:20]):
                self.assertGreen(src(DRILLS + FULL.replace("<p>畫時間序列圖。</p>", shown)))


class FigureRule(Case):
    def put(self, fig):
        return src(DRILLS + FULL.replace("<p>畫時間序列圖。</p>", fig))

    def test_untranslated_fails(self):
        self.assertRed(self.put('<figure><img src="q.png"><figcaption>Eg p.2</figcaption></figure>'), "沒有翻譯")

    def test_no_caption_fails(self):
        self.assertRed(self.put('<figure><img src="q.png" data-zh="q.zh.png"></figure>'), "figcaption")

    def test_bare_img_fails(self):
        self.assertRed(self.put('<img src="q.png">'), "不在 <figure> 裡")

    def test_remote_fails(self):
        self.assertRed(self.put('<figure><img src="https://x.org/q.png" data-zh="q.zh.png"><figcaption>p.1</figcaption></figure>'),
                       "外部資源")

    def test_no_text_figure_passes(self):
        self.assertGreen(self.put('<FIGURE data-tr="none"><img alt="" src="q.png"/><figcaption>圖</figcaption></FIGURE>'))

    def test_panel_figure_without_tab_fails(self):
        s = src().replace(' data-tab="Z 表"', "")
        self.assertRed(s, "data-tab")


class PlaceholderRule(Case):
    def test_placeholder_in_text_fails(self):
        self.assertRed(src(DRILLS + FULL.replace("畫時間序列圖。", "n = {{p1_n}}")), "佔位")

    def test_placeholder_in_attr_fails(self):
        self.assertRed(src(DRILLS + FULL.replace('class="ref"', 'class="ref" title="{{x}}"')), "佔位")

    def test_braces_in_math_pass(self):
        self.assertGreen(src(DRILLS + FULL.replace("畫時間序列圖。", "集合 {1, 2} 和 f(x) = {x}")))


class AnswersRule(Case):
    def test_missing_file_fails(self):
        (self.dir / "ans.md").unlink()
        self.assertRed(src(), "找不到答案檔")

    def test_question_missing_from_answers_fails(self):
        self.answers(IDS[:-1])
        self.assertRed(src(), "acf-trend")

    def test_answer_format_free(self):
        (self.dir / "ans.md").write_text("# 答案\n" + "\n".join(f"### 練習（`{i}`）\n- a." for i in IDS), encoding="utf-8")
        self.assertGreen(src())


class HeightRule(Case):
    def test_bad_height_fails(self):
        self.assertRed(src(DRILLS + FULL.replace('class="q"', 'class="q" data-h="tall"')), "data-h")

    def test_height_passes(self):
        self.assertGreen(src(DRILLS + FULL.replace('class="q"', 'class="q" data-h=" 1300 "')))


class Build(Case):
    """組出來的頁面：每題一張畫布、§ 連到導讀頁、出題備註拿掉、圖片內嵌。"""

    def page(self, s=None):
        s = src() if s is None else s
        self.assertEqual(self.problems(s), [])
        return practice.build(s, self.dir)

    def test_every_question_gets_a_pad(self):
        out = self.page()
        pads = re.findall(r'<div class="pad" data-id="([^"]+)" data-h="(\d+)">', out)
        self.assertEqual([p[0] for p in pads], IDS)
        self.assertEqual([p[1] for p in pads], ["280", "280", "280", "900", "900"])

    def test_pad_sits_inside_its_section(self):
        out = self.page()
        sec = re.search(r'<section[^>]*id="q-acf-seasonal"[^>]*>(.*?)</section>', out, re.S).group(1)
        self.assertIn('data-id="acf-seasonal"', sec)

    def test_height_override(self):
        out = self.page(src(DRILLS + FULL.replace('class="q"', "class='q' data-h='1300'")))
        self.assertIn('data-id="acf-seasonal" data-h="1300"', out)

    def test_refs_link_to_guide(self):
        out = self.page(src(DRILLS.replace("<p>", '<p class="ref">§1.2</p><p>', 1) + FULL))
        self.assertIn('<a href="guide.html#s16" target="_blank">§16</a>', out)
        self.assertIn('<a href="guide.html#s20" target="_blank">§20</a>', out)
        self.assertIn('<a href="guide.html#s1-2" target="_blank">§1.2</a>', out)

    def test_section_marks_outside_ref_stay_plain(self):
        out = self.page(src(DRILLS + FULL.replace("畫時間序列圖。", "就是 §16 那題")))
        self.assertIn("就是 §16 那題", out)

    def test_differs_removed(self):
        self.assertNotIn("data-differs", self.page())
        self.assertNotIn("Eg 1 有趨勢", self.page())

    def test_nav_lists_questions_in_order(self):
        out = self.page()
        nav = re.search(r'<nav class="jump".*?</nav>', out, re.S).group(0)
        self.assertEqual(re.findall(r'href="#q-([^"]+)"', nav), IDS)

    def test_images_inlined_zh_first(self):
        out = self.page()
        img = re.search(r"<img [^>]*>", out).group(0)
        self.assertIn('src="data:image/png;base64,', img)
        self.assertIn('data-en="data:image/png;base64,', img)
        self.assertNotIn("z.png", out)

    def test_panel_becomes_tabs(self):
        out = self.page()
        self.assertIn('id="panel-btn"', out)
        self.assertIn('<button type="button" data-tab="t0" aria-pressed="true">Z 表</button>', out)
        self.assertNotIn('class="panel"', out)

    def test_assets_inlined_and_body_keyed(self):
        out = self.page()
        self.assertIn('<body data-key="isom3031-topic4" data-title="Topic 4 練習">', out)
        self.assertIn(practice.JS.read_text(encoding="utf-8")[:200], out)
        self.assertNotIn("data-answers", out)

    def test_fills_and_report_button_reach_the_page(self):
        out = self.page()
        self.assertEqual(out.count('class="fill" data-answer="t|t 分配"'), 3)
        self.assertEqual(out.count('<button id="report"'), 1)

    def test_model_gets_summary_and_starts_closed(self):
        out = practice.build(src(DRILLS + FULL.replace('<details class="model">', '<details open class="model">')), self.dir)
        self.assertEqual(out.count(f"<summary>{practice.MODEL_SUMMARY}</summary>"), 2)
        self.assertNotIn("<details open", out)

    def test_cli_writes_nothing_when_red(self):
        (self.dir / "p-src.html").write_text(src(DRILLS), encoding="utf-8")
        out = self.dir / "p.html"
        self.assertEqual(practice.main([str(self.dir / "p-src.html"), "-o", str(out)]), 1)
        self.assertFalse(out.exists())

    def test_cli_writes_page(self):
        (self.dir / "p-src.html").write_text(src(), encoding="utf-8")
        self.assertEqual(practice.main([str(self.dir / "p-src.html")]), 0)
        self.assertTrue((self.dir / "p.html").is_file())


if __name__ == "__main__":
    unittest.main()
