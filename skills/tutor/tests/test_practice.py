"""practice.py 的規則閘門與組頁：會讓頁面壞掉的事要擋，題目放幾題、怎麼排不管。每條規則都驗兩個方向。

違規要紅（而且是那一條在紅）；只改無關的格式（引號、屬性順序、大小寫、題目代號的命名）不能紅。

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
# 提示和逐步詳解：題型第一次出現的那一題兩個提示加詳解，之後的題一個提示
HINT = '<ol class="hints"><li>這是讀 ACF 的題型，做法在導讀頁 §16。</li></ol>'
HINTS = HINT.replace("</ol>", "<li>第一步：看 r₁ 有沒有超出紅線。</li></ol>")
STEPS = '<details class="steps"><p>r₁ 沒有超出紅線，所以沒有趨勢。</p></details>'
ONE = ('<section class="q" data-id="acf-seasonal" data-type="acf-read" data-differs="有季節性沒有趨勢，Eg 1 有趨勢">'
       '<h2>練習 1</h2><p class="ref">對照 Eg 1（導讀頁 §16、§20）</p><p>畫時間序列圖。</p>' + HINTS + STEPS + MODEL + '</section>')
TWO = ONE.replace("acf-seasonal", "acf-trend").replace("練習 1", "練習 2").replace(HINTS + STEPS, HINT)
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


class ShapeRule(Case):
    """放幾題小題、幾題整題、怎麼排，由出題的人照考試的形式決定。"""

    def test_any_mix_and_order_passes(self):
        for inner in (DRILLS, FULL, drill("which-table") + FULL + drill("which-tail"), ONE):
            with self.subTest(inner=inner[:60]):
                self.assertGreen(src(inner))

    def test_page_without_questions_fails(self):
        self.assertRed(src("<p>還沒出題</p>"), "頁面沒有題目")

    def test_full_question_needs_no_ref_hints_steps_or_note(self):
        bare = (ONE.replace('<p class="ref">對照 Eg 1（導讀頁 §16、§20）</p>', "").replace(HINTS + STEPS, "")
                .replace(' data-differs="有季節性沒有趨勢，Eg 1 有趨勢"', ""))
        self.assertGreen(src(bare))

    def test_section_mark_in_a_ref_must_still_exist_in_the_guide(self):
        self.assertRed(src(DRILLS + FULL.replace("§20", "§21")), "§21")


class FillRule(Case):
    def test_drill_without_fill_fails(self):
        self.assertRed(src(DRILLS.replace(FILL, "", 1) + FULL), "沒有填答格")

    def test_fill_without_answer_fails(self):
        for bad in ('data-answer=""', 'data-answer=" | "'):
            with self.subTest(bad=bad):
                self.assertRed(src(DRILLS.replace('data-answer="t|t 分配"', bad, 1) + FULL), "沒有 data-answer")

    def test_reason_is_optional(self):
        self.assertGreen(src(DRILLS.replace(' data-why="σ 未知，用 t"', "") + FULL))

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
    def test_missing_anchor_fails(self):
        self.assertRed(src(DRILLS + FULL.replace("§20", "§21")), "§21")

    def test_missing_guide_fails(self):
        (self.dir / "guide.html").unlink()
        self.assertRed(src(), "找不到導讀頁")

    def test_ref_variants_pass(self):
        for ref in ('<span class="note ref">§16</span>', '<div class="ref">對照 §1.2 和 §16</div>'):
            with self.subTest(ref=ref):
                self.assertGreen(src(DRILLS + FULL.replace('<p class="ref">對照 Eg 1（導讀頁 §16、§20）</p>', ref)))


class HintRule(Case):
    """提示和逐步詳解放不放由出題的人決定；裡面的 § 要連得到導讀頁；模擬卷都不放。"""

    def test_how_much_help_a_question_gets_is_up_to_the_author(self):
        for q in (ONE.replace(HINTS, HINT), ONE.replace(STEPS, ""), ONE.replace(HINTS + STEPS, ""), ONE.replace(HINTS, "")):
            with self.subTest(q=q[-200:-120]):
                self.assertGreen(src(DRILLS + q + TWO))

    def test_steps_may_hold_answer_blocks(self):
        rich = STEPS.replace("<p>", '<div class="calc">r = 0.4</div><p class="trap">別用 1.96</p><p>')
        self.assertGreen(src(DRILLS + FULL.replace(STEPS, rich)))

    def test_missing_anchor_in_a_hint_fails(self):
        self.assertRed(src(DRILLS + FULL.replace("做法在導讀頁 §16。</li><li>", "做法在導讀頁 §21。</li><li>")), "§21")

    def test_formatting_variants_pass(self):
        inner = (FULL.replace('<ol class="hints">', "<OL CLASS='x hints'>", 1)
                 .replace('<details class="steps">', "<details open class='steps wide'>"))
        self.assertGreen(src(DRILLS + inner))

    def test_hints_in_mock_fail(self):
        for extra in (HINT, STEPS):
            with self.subTest(extra=extra[:30]):
                self.assertRed(src(MQ.replace(MODEL, extra + MODEL), MOCK_BODY), "不放提示和逐步詳解")


class TypeRule(Case):
    """每題整題寫明練的是題型表的哪一列；還沒有題目的題型只提醒，不擋。"""
    TYPES2 = GUIDE.replace("</table>", '<tr data-type="mad"><td>MAD</td></tr></table>')

    def test_missing_type_fails(self):
        self.assertRed(src(DRILLS + ONE.replace(' data-type="acf-read"', "") + TWO), "沒有 data-type")

    def test_unknown_type_fails(self):
        self.assertRed(src(DRILLS + ONE.replace("acf-read", "acf-raed") + TWO), "不在導讀頁的題型表裡")

    def notes(self, s):
        got = []
        self.assertEqual(practice.lint(s, self.dir, self.dir, got), [])
        return got

    def test_type_without_a_question_is_a_note_not_a_failure(self):
        (self.dir / "guide.html").write_text(self.TYPES2, encoding="utf-8")
        got = self.notes(src())
        self.assertEqual(len(got), 1)
        self.assertIn("mad", got[0])
        self.assertNotIn("acf-read", got[0])

    def test_every_type_covered_gives_no_note(self):
        self.assertEqual(self.notes(src(ONE)), [])

    def test_a_typed_drill_covers_its_type(self):
        (self.dir / "guide.html").write_text(self.TYPES2, encoding="utf-8")
        typed = drill("mad-pick").replace('class="q drill"', 'class="q drill" data-type="mad"')
        self.answers(IDS + ["mad-pick"])
        self.assertEqual(self.notes(src(typed + FULL)), [])

    def test_one_question_can_cover_several_types(self):
        (self.dir / "guide.html").write_text(self.TYPES2, encoding="utf-8")
        self.assertGreen(src(DRILLS + FULL.replace('data-type="acf-read"', "data-type='mad  acf-read'")))

    def test_guide_without_a_types_table_needs_no_types(self):
        (self.dir / "guide.html").write_text(GUIDE.replace(' data-type="acf-read"', ""), encoding="utf-8")
        self.assertGreen(src())
        self.assertGreen(src(DRILLS + FULL.replace(' data-type="acf-read"', "")))

    def test_drills_need_no_type(self):
        self.assertGreen(src())


MOCK_BODY = BODY + ' data-mode="mock" data-minutes="45"'
MQ = (ONE.replace('<p class="ref">對照 Eg 1（導讀頁 §16、§20）</p>', "").replace(' data-differs="有季節性沒有趨勢，Eg 1 有趨勢"', "")
      .replace(HINTS + STEPS, ""))


class MockRule(Case):
    """模擬卷：只有整題、沒有提示，在紙上做。"""

    def test_valid_mock_passes(self):
        self.assertGreen(src(MQ, MOCK_BODY))

    def test_formatting_variants_pass(self):
        body = BODY + " DATA-MINUTES=' 90 ' data-mode='mock'"
        self.assertGreen(src(MQ.replace('class="q"', "class='q hard'"), body))

    def test_unknown_mode_fails(self):
        self.assertRed(src(body=BODY + ' data-mode="exam"'), "看不懂")

    def test_minutes_are_optional(self):
        self.assertGreen(src(MQ, BODY + ' data-mode="mock"'))

    def test_bad_minutes_fail(self):
        for bad in (' data-minutes=""', ' data-minutes="0"', ' data-minutes="一小時"', ' data-minutes="1.5"'):
            with self.subTest(bad=bad):
                self.assertRed(src(MQ, BODY + ' data-mode="mock"' + bad), "data-minutes")

    def test_drill_in_mock_fails(self):
        self.assertRed(src(drill("which-table") + MQ, MOCK_BODY), "不放小題")

    def test_ref_in_mock_fails(self):
        self.assertRed(src(ONE, MOCK_BODY), "不寫對照的 §")

    def test_mock_still_needs_a_way_to_check_and_a_type(self):
        self.assertRed(src(MQ.replace(MODEL, ""), MOCK_BODY), "對不了答案")
        self.assertRed(src(MQ.replace(' data-type="acf-read"', ""), MOCK_BODY), "沒有 data-type")

    def test_mock_with_only_short_questions_has_no_questions(self):
        self.assertRed(src(DRILLS, MOCK_BODY), "頁面沒有題目")

    def test_short_answer_question_takes_no_answer_page(self):
        match = ('<section class="q" data-id="match-country" data-type="acf-read" data-space="none"><h2>第 1 題</h2>'
                 '<p class="fill" data-answer="B">NEP →</p><p class="fill" data-answer="C">Rama VI →</p></section>')
        self.answers(["match-country", "acf-seasonal"])
        out = self.mock_page(match + MQ)
        self.assertNotIn('<div class="space" data-id="match-country">', out)
        self.assertIn('<div class="space" data-id="acf-seasonal"></div>', out)
        cover = re.search(r'<div class="cover">.*?</div>', out, re.S).group(0)
        self.assertIn("<tr><td>第 1 題</td><td>2</td><td></td></tr>", cover)  # 沒有給分點：一個填答格一分
        self.assertIn("作答頁", cover)
        alone = re.search(r'<div class="cover">.*?</div>', self.mock_page(match), re.S).group(0)
        self.assertIn("答案直接寫在題目裡的底線上", alone)
        self.assertNotIn("作答頁", alone)

    def test_unknown_space_fails(self):
        self.assertRed(src(MQ.replace('class="q"', 'class="q" data-space="half"'), MOCK_BODY), "data-space")

    def test_cumulative_mock_draws_types_from_all_guides(self):
        (self.dir / "g5.html").write_text(GUIDE.replace("acf-read", "decompose"), encoding="utf-8")
        body = MOCK_BODY.replace('data-guide="guide.html"', 'data-guide="guide.html; g5.html"')
        self.assertGreen(src(MQ.replace('data-type="acf-read"', 'data-type="decompose"'), body))
        self.assertRed(src(MQ.replace('data-type="acf-read"', 'data-type="arima"'), body), "不在導讀頁的題型表裡")

    def test_several_guides_only_in_mock(self):
        (self.dir / "g5.html").write_text(GUIDE, encoding="utf-8")
        self.assertRed(src(body=BODY.replace('data-guide="guide.html"', 'data-guide="guide.html;g5.html"')), "只能寫一份導讀頁")

    def mock_page(self, inner=MQ, body=MOCK_BODY):
        """組好的模擬卷，只留 <body> 裡的 HTML（不含內嵌的樣式和腳本）。"""
        out = practice.build(src(inner, body), self.dir)
        self.assertIn('data-mode="mock"', out)
        return out.split("</style>")[1].split("<script>")[0]

    def test_mock_page_has_no_guide_links(self):
        self.assertNotIn('href="guide.html', self.mock_page())

    def test_cover_lists_time_total_and_each_question(self):
        two = MQ + MQ.replace("acf-seasonal", "acf-trend").replace("練習 1", "練習 2").replace('data-marks="2"', 'data-marks="5"')
        self.answers(["acf-seasonal", "acf-trend"])
        cover = re.search(r'<div class="cover">.*?</div>', self.mock_page(two), re.S).group(0)
        self.assertIn("建議時間 45 分鐘", cover)
        self.assertIn("滿分 9 分", cover)
        self.assertIn("<tr><td>練習 1</td><td>3</td><td></td></tr><tr><td>練習 2</td><td>6</td><td></td></tr>", cover)
        self.assertIn('<tr class="total"><td>合計</td><td>9</td><td></td></tr>', cover)

    def test_cover_mentions_the_tables_only_when_some_are_attached(self):
        self.assertIn("只用卷末附的表", self.mock_page())
        bare = practice.build(src(MQ, MOCK_BODY).replace(PANEL, ""), self.dir).split("</style>")[1].split("<script>")[0]
        self.assertIn("照考試做", bare)
        self.assertNotIn("卷末", bare)

    def test_cover_without_minutes_gives_no_time(self):
        cover = re.search(r'<div class="cover">.*?</div>', self.mock_page(body=BODY + ' data-mode="mock"'), re.S).group(0)
        self.assertNotIn("建議時間", cover)
        self.assertIn("滿分 3 分", cover)

    def test_answer_pages_replace_the_pad(self):
        out = self.mock_page()
        self.assertNotIn('class="pad"', out)
        self.assertLess(out.index('<div class="space" data-id="acf-seasonal"></div>'), out.index("<details"))

    def test_each_question_gets_one_answer_page_whatever_its_height(self):
        for h in (None, 300, 2200):
            with self.subTest(h=h):
                q = MQ if h is None else MQ.replace('class="q"', f'class="q" data-h="{h}"')
                self.assertEqual(self.mock_page(q).count('<div class="space" data-id="acf-seasonal"></div>'), 1)

    def test_mock_page_has_print_and_done_buttons_and_no_clock(self):
        out = self.mock_page()
        for act in ("print", "print-key", "done"):
            self.assertIn(f'data-act="{act}"', out)
        self.assertNotIn('class="clock"', out)

    def test_practice_page_has_no_cover_or_answer_space(self):
        out = practice.build(src(), self.dir).split("</style>")[1].split("<script>")[0]
        for cls in ("cover", "mockbar", "space"):
            self.assertNotIn(f'class="{cls}"', out)

    def test_panel_tables_keep_their_names_for_the_printed_paper(self):
        self.assertIn('<figure data-tab="t0" data-name="Z 表">', self.mock_page())


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
    """整題要有範本答案或填答格，讀者才對得了答案；給分點可以不寫；讀圖題型的題目要有圖或軟體輸出。"""
    READS = GUIDE.replace('data-type="acf-read"', 'data-reads="figure" data-type="acf-read"')
    FIG = '<figure data-tr="none"><img src="q.png"><figcaption>gen.py 畫的 ACF</figcaption></figure>'

    def test_nothing_to_check_against_fails(self):
        self.assertRed(src(DRILLS + ONE.replace(MODEL, "") + TWO), "對不了答案")

    def test_fills_alone_are_enough(self):
        self.assertGreen(src(DRILLS + ONE.replace(MODEL, '<p class="fill" data-answer="0.62">r4 =</p>') + TWO))

    def test_two_models_fail(self):
        self.assertRed(src(DRILLS + ONE.replace(MODEL, MODEL + MODEL) + TWO), "有 2 個")

    def test_model_without_rubric_passes(self):
        self.assertGreen(src(DRILLS + ONE.replace('<li data-marks="2">說出沒有趨勢</li><li data-marks="1">結論句</li>', "") + TWO))

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

    def test_plain_pictures_pass(self):
        for fig in ('<figure><img src="q.png"><figcaption>Eg p.2</figcaption></figure>',
                    '<figure><img src="q.png" data-zh="q.zh.png"></figure>', '<img src="q.png">'):
            with self.subTest(fig=fig):
                self.assertGreen(self.put(fig))

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
        self.assertEqual([p[0] for p in pads], IDS[3:])  # 基本功只填一格，沒有畫布
        self.assertEqual([p[1] for p in pads], ["900", "900"])

    def test_pad_comes_before_the_model_answer(self):
        out = self.page()
        sec = out[out.index('id="q-acf-seasonal"'):out.index('id="q-acf-trend"')]
        self.assertLess(sec.index('class="pad"'), sec.index("<details"))

    def test_drill_with_height_gets_a_pad(self):
        out = practice.build(src(DRILLS.replace('data-id="which-tail"', 'data-id="which-tail" data-h="300"') + FULL), self.dir)
        self.assertEqual(re.findall(r'<div class="pad" data-id="([^"]+)" data-h="(\d+)">', out)[0], ("which-tail", "300"))

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

    def test_hints_and_steps_link_to_guide(self):
        out = self.page(src(DRILLS + FULL.replace(STEPS, STEPS.replace("所以", "見 §20，所以"))))
        sec = out[out.index('id="q-acf-seasonal"'):out.index('id="q-acf-trend"')]
        self.assertIn('做法在導讀頁 <a href="guide.html#s16" target="_blank">§16</a>', sec)
        self.assertIn('見 <a href="guide.html#s20" target="_blank">§20</a>', sec)

    def test_pad_comes_before_hints_steps_and_model(self):
        out = self.page()
        sec = out[out.index('id="q-acf-seasonal"'):out.index('id="q-acf-trend"')]
        order = [sec.index(x) for x in ('class="pad"', 'class="hints"', 'class="steps"', 'class="model"')]
        self.assertEqual(order, sorted(order))

    def test_steps_get_a_summary_and_start_closed(self):
        out = self.page(src(DRILLS + FULL.replace('<details class="steps">', '<details class="steps" open>')))
        self.assertIn(f'<details class="steps"><summary>{practice.STEPS_SUMMARY}</summary>', out)

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

    def test_images_inlined_original_first(self):
        """翻譯過的圖預設顯示原圖：src 和 data-en 是同一張，data-zh 是另一張。"""
        for name in ("z.zh.png", "q.zh.png"):  # 翻譯圖和原圖內容不同，才分得出哪一張排在前面
            (self.dir / name).write_bytes(PNG + b"zh")
        out = self.page()
        img = re.search(r"<img [^>]*data-zh[^>]*>", out).group(0)
        shown = re.search(r'\bsrc="([^"]+)"', img).group(1)
        self.assertTrue(shown.startswith("data:image/png;base64,"))
        self.assertEqual(shown, re.search(r'data-en="([^"]+)"', img).group(1))
        self.assertNotEqual(shown, re.search(r'data-zh="([^"]+)"', img).group(1))
        self.assertNotIn("z.png", out)

    def test_theme_is_manual(self):
        """深淺色不跟系統：樣式裡沒有 prefers-color-scheme，頁首有切換鈕，樣式之前先讀 tutor-theme。"""
        out = self.page()
        self.assertNotIn("prefers-color-scheme", out)
        self.assertIn('id="theme"', out)
        self.assertLess(out.index("tutor-theme"), out.index("<style>"))

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
        (self.dir / "p-src.html").write_text(src("<p>還沒出題</p>"), encoding="utf-8")
        out = self.dir / "p.html"
        self.assertEqual(practice.main([str(self.dir / "p-src.html"), "-o", str(out)]), 1)
        self.assertFalse(out.exists())

    def test_how_to_only_mentions_what_the_page_has(self):
        def howto(inner):
            return practice.build(src(inner), self.dir).split('<details class="howto">')[1].split("</details>")[0]

        full = howto(DRILLS + FULL)
        for word in ("小題", "看提示", "逐步詳解", "畫布", "範本答案", "複製填答結果"):
            self.assertIn(word, full)
        drills = howto(DRILLS)
        for word in ("看提示", "逐步詳解", "畫布", "範本答案"):
            self.assertNotIn(word, drills)
        plain = howto(ONE.replace(HINTS + STEPS, "").replace('<p class="ref">對照 Eg 1（導讀頁 §16、§20）</p>', ""))
        for word in ("小題", "看提示", "逐步詳解", "§"):
            self.assertNotIn(word, plain)
        self.assertIn("畫布", plain)

    def test_page_opens_with_the_authors_own_words_only(self):
        self.assertNotIn('class="lead"', self.page())
        self.assertIn('<p class="lead">照 Quiz 3 的形式出的。</p>', self.page(src('<p class="lead">照 Quiz 3 的形式出的。</p>' + FULL)))

    def test_cli_names_the_types_without_a_question(self):
        (self.dir / "guide.html").write_text(TypeRule.TYPES2, encoding="utf-8")
        (self.dir / "p-src.html").write_text(src(), encoding="utf-8")
        err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.TextIOWrapper(io.BytesIO(), encoding="utf-8")):
            code = practice.main([str(self.dir / "p-src.html")], measure=lambda out, **kw: [])
        err.flush()
        self.assertEqual(code, 0)
        self.assertIn("提醒：題型表上這幾個題型沒有題目：mad", err.buffer.getvalue().decode("utf-8"))

    def test_cli_writes_page(self):
        (self.dir / "p-src.html").write_text(src(), encoding="utf-8")
        self.assertEqual(practice.main([str(self.dir / "p-src.html")]), 0)
        self.assertTrue((self.dir / "p.html").is_file())

    def test_cli_writes_nothing_when_the_page_overflows(self):
        (self.dir / "p-src.html").write_text(src(), encoding="utf-8")
        seen = {}

        def measure(out, prepare=""):
            seen["prepare"] = prepare
            return ["視窗寬 390px：整頁被撐寬 120px"]
        self.assertEqual(practice.main([str(self.dir / "p-src.html")], measure=measure), 1)
        self.assertFalse((self.dir / "p.html").exists())
        # 模擬卷的範本答案要先出現再量
        self.assertIn("submitted", seen["prepare"])

    def test_cli_writes_page_without_a_browser(self):
        (self.dir / "p-src.html").write_text(src(), encoding="utf-8")
        self.assertEqual(practice.main([str(self.dir / "p-src.html")], measure=lambda out, prepare="": None), 0)
        self.assertTrue((self.dir / "p.html").is_file())

    def run_cli(self, source, printer):
        """跑一次 CLI（不量溢出），回傳退出碼和 stdout、stderr。"""
        (self.dir / "p-src.html").write_text(source, encoding="utf-8")
        # main 會對 stdout、stderr 呼叫 reconfigure，StringIO 沒有這個方法
        out, err = (io.TextIOWrapper(io.BytesIO(), encoding="utf-8") for _ in range(2))
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = practice.main([str(self.dir / "p-src.html")], measure=lambda page, prepare="": [], printer=printer)
        for stream in (out, err):
            stream.flush()
        return code, out.buffer.getvalue().decode("utf-8"), err.buffer.getvalue().decode("utf-8")

    def test_cli_prints_the_mock_as_two_pdfs(self):
        asked = []

        def printer(page):
            asked.append(page)
            return [page.with_name("p.pdf"), page.with_name("p-answers.pdf")]
        code, out, _ = self.run_cli(src(MQ, MOCK_BODY), printer)
        self.assertEqual(code, 0)
        self.assertEqual(asked, [self.dir / "p.html"])
        self.assertEqual(out.split(), [str(self.dir / n) for n in ("p.html", "p.pdf", "p-answers.pdf")])

    def test_cli_delivers_the_mock_without_a_browser_and_says_so(self):
        code, out, err = self.run_cli(src(MQ, MOCK_BODY), lambda page: None)
        self.assertEqual(code, 0)
        self.assertTrue((self.dir / "p.html").is_file())
        self.assertIn("沒有印 PDF", err)

    def test_cli_does_not_print_a_practice_page(self):
        code, out, _ = self.run_cli(src(), lambda page: self.fail("練習頁不印 PDF"))
        self.assertEqual(code, 0)
        self.assertEqual(out.split(), [str(self.dir / "p.html")])

    def test_pdf_names_and_urls(self):
        """考卷和答案各一份：答案版的網址結尾是頁面 JS 認的 #answers。"""
        self.assertEqual(practice.PDFS, (("", ""), ("-answers", "#answers")))
        self.assertIn('location.hash === "#answers"', practice.JS.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
