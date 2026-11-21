"""build.py：會讓頁面壞掉的事要擋下來，其餘的寫法不管；組頁的每一步各自驗產出的 HTML。

每條規則驗兩個方向：違規要紅；只改無關的格式（空白、屬性順序、大小寫）不能紅。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import base64
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
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
CHEAT = ('<div class="cheat"><table class="types"><tr><th>考什麼</th><th>怎麼答</th></tr>'
         '<tr data-type="match-country"><td>名詞配國家</td><td>看線索</td></tr></table></div>')
ZH_FIG = '<figure><img src="a.png" data-zh="a.zh.png" alt=""><figcaption>Topic 3 p.4</figcaption></figure>'


def page(body="<h2>一</h2><p>內容</p>", cheat=CHEAT, attrs="", tail=""):
    return f"<!doctype html><html><head><title>x</title></head><body{attrs}><h1>書名</h1>{body}{cheat}{tail}</body></html>"


def slides(*keys):
    """load_slides() 的結果：keys 是 (代號, 頁)，第三項若為 list/True 則帶 HTML 譯文層，第四項 True 為 skip。"""
    out = {}
    for k in keys:
        zh = k[2] if len(k) > 2 else []
        if zh is True:
            zh = ["<b>平穩序列（stationary series）</b>", "資料大致水平。"]
        skip = bool(k[3]) if len(k) > 3 else False
        out[(k[0], k[1])] = {"src": Path(f"/x/slides/{k[0]}-{k[1]}.png"), "zh": zh or [], "w": 1000, "h": 563, "skip": skip}
    return out


DECK = slides(("L20", 1), ("L20", 2, True), ("L20", 3), ("L21", 1))


def ok(src, deck=None):
    return build.lint(src, deck) == []


def has(src, needle, deck=None):
    """lint 的問題裡有沒有哪一條含 needle：確認是這條規則紅，不是別條。"""
    return any(needle in p for p in build.lint(src, deck))


class FreeForm(unittest.TestCase):
    """怎麼分段、用哪些元件不歸 build 管。"""

    def test_plain_page_passes(self):
        self.assertTrue(ok(page()))

    def test_no_teaching_structure_is_required(self):
        for body in ("<p>沒有任何 h2</p>",
                     '<h2>一</h2><table><tr><td>對照表</td></tr></table><img src="a.png">',
                     '<section class="anything"><h2>一</h2><div class="def"><dfn>甲</dfn></div><input></section>',
                     "<h2>一</h2><p>" + "很長的一句話" * 40 + "</p><p>這一頁看懂就好，不考</p>"):
            with self.subTest(body=body[:30]):
                self.assertEqual(build.lint(page(body)), [])


class RemoteRule(unittest.TestCase):
    def test_remote_img_fails(self):
        self.assertTrue(has(page('<img src="https://x.test/a.png">'), "外部資源"))

    def test_remote_translated_img_fails(self):
        self.assertTrue(has(page('<img src="a.png" data-zh="//x.test/a.zh.png">'), "外部資源"))

    def test_remote_script_and_stylesheet_fail(self):
        self.assertTrue(has(page('<script src="http://x.test/a.js"></script>'), "外部資源"))
        self.assertTrue(has(page('<link rel="stylesheet" href="https://x.test/a.css">'), "外部資源"))

    def test_plain_links_pass(self):
        self.assertTrue(ok(page('<p><a href="https://x.test/">出處</a></p><img src="a.png">')))


class RefRule(unittest.TestCase):
    def test_missing_section_fails(self):
        self.assertTrue(has(page("<h2>一</h2><p>見 §2</p>"), "§2"))

    def test_missing_subsection_fails(self):
        self.assertTrue(has(page("<h2>一</h2><h3>甲</h3><p>見 §1.2</p>"), "§1.2"))

    def test_existing_refs_pass(self):
        self.assertTrue(ok(page("<h2>一</h2><h3>甲</h3><h2>二</h2><p>見 §1、§1.1、§2</p>")))

    def test_section_sign_in_script_code_pre_or_comment_is_not_a_ref(self):
        self.assertTrue(ok(page('<h2>一</h2><script>const s = "§9";</script><code>§9</code><pre>§8</pre><!-- §7 -->')))


class CheatRule(unittest.TestCase):
    """速查卡和題型表都可以不寫；寫了題型表，每一列要有不重複的代號，下游才對得回題型。"""

    def test_card_and_table_are_optional(self):
        for cheat in ("", '<div class="cheat"><p>公式</p></div>'):
            with self.subTest(cheat=cheat):
                self.assertEqual(build.lint(page(cheat=cheat)), [])

    def test_table_outside_the_card_is_checked_too(self):
        self.assertEqual(build.lint(page(cheat='<table class="types"><tr data-type="a"><td>x</td></tr></table>')), [])
        self.assertTrue(has(page(cheat='<table class="types"><tr><td>x</td></tr></table>'), "沒有 data-type"))

    def test_table_with_only_a_header_fails(self):
        self.assertTrue(has(page(cheat='<div class="cheat"><table class="types"><tr><th>考什麼</th></tr></table></div>'), "沒有任何一列"))

    def test_row_without_type_fails(self):
        for row in ("<tr><td>x</td></tr>", '<tr data-type=""><td>x</td></tr>', '<tr data-type="Has Space"><td>x</td></tr>'):
            with self.subTest(row=row):
                self.assertTrue(has(page(cheat=f'<div class="cheat"><table class="types">{row}</table></div>'), "沒有 data-type"))

    def test_duplicate_type_fails(self):
        rows = '<tr data-type="a"><td>x</td></tr><tr data-type="a"><td>y</td></tr>'
        self.assertTrue(has(page(cheat=f'<div class="cheat"><table class="types">{rows}</table></div>'), "重複"))

    def test_formatting_variants_pass(self):
        for cheat in ('<DIV id="c" CLASS=\'wide cheat\'><h4>考什麼</h4><TABLE class="types big">'
                      "<thead><tr><th>考什麼</th></tr></thead><tbody><TR DATA-TYPE='a-1'><td>x</td></TR>"
                      '<tr data-type="b"><td>y</td></tr></tbody></TABLE><p>判斷規則</p></DIV>',
                      f'<section class="problems">{CHEAT}</section>'):
            with self.subTest(cheat=cheat[:30]):
                self.assertEqual(build.lint(page(cheat=cheat)), [])


class PanelRule(unittest.TestCase):
    def test_panel_figure_without_tab_fails(self):
        self.assertTrue(has(page(tail='<aside class="panel"><figure><img src="a.png"></figure></aside>'), "data-tab"))

    def test_panel_with_tabs_passes(self):
        self.assertTrue(ok(page(tail='<aside class="panel"><figure data-tab="Z 表"><img src="a.png"></figure></aside>')))

    def test_figure_outside_the_panel_needs_no_tab(self):
        self.assertTrue(ok(page("<h2>一</h2><figure><img src='a.png'></figure>")))


class SlideRule(unittest.TestCase):
    """data-slide 與 data-skip 指到的每一頁都要在課件清單上。"""

    def test_slide_without_a_declared_deck_fails(self):
        self.assertTrue(has(page('<h2 data-slide="L20 p.1">一</h2>'), "沒有 data-slides"))
        self.assertTrue(has(page("<h2>一</h2>", attrs=' data-skip="L20 p.1"'), "沒有 data-slides"))

    def test_page_not_on_the_list_fails(self):
        for ref in ("L20 p.4", "L22 p.1", "L20 p.2-4", "L20 p.1; L21 p.2"):
            with self.subTest(ref=ref):
                self.assertTrue(has(page(f'<h2 data-slide="{ref}">一</h2>'), "課件清單沒有", DECK))
        self.assertTrue(has(page("<h2>一</h2>", attrs=' data-skip="L20 p.9"'), "課件清單沒有", DECK))

    def test_unreadable_ref_fails(self):
        for ref in ("L20", "p.3", "L20 p.3-1", "Lecture 20 第 3 頁", ""):
            with self.subTest(ref=ref):
                self.assertTrue(has(page(f'<h2 data-slide="{ref}">一</h2>'), "看不懂", DECK))

    def test_pages_ranges_lists_and_skip_pass(self):
        for ref in ("L20 p.1", "L20 p.1-3", "L20 p. 2 – 3", "L20 p.3; L21 p.1", " L21  p.1 "):
            with self.subTest(ref=ref):
                self.assertEqual(build.lint(page(f'<p data-slide="{ref}" data-key>x</p>'), DECK), [])
        self.assertEqual(build.lint(page("<h2>一</h2>", attrs=' data-skip="L20 p.1; L20 p.3"'), DECK), [])

    def test_deck_without_any_slide_ref_passes(self):
        self.assertTrue(ok(page(), DECK))


class Slides(unittest.TestCase):
    def test_manifest_resolves_zh_from_zh_json_and_skip_flags(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "slides" / "slides.json"
            path.parent.mkdir()
            (path.parent / "zh.json").write_text(json.dumps({
                "Title": "<b>標題（Title）</b>",
                "Formula y = a + bx": "線性式 y = a + bx",
                "Untranslated": "",
            }, ensure_ascii=False), encoding="utf-8")
            path.write_text(json.dumps({"skip": ["A p.1"], "decks": [
                {"id": "B", "pages": [
                    {"n": 1, "src": "B-01.png", "w": 10, "h": 5, "blocks": ["Untranslated"], "skip": True},
                    {"n": 2, "src": "B-02.jpg", "w": 10, "h": 5, "blocks": ["Title", "Formula y = a + bx"]},
                ]},
                {"id": "A", "pages": [{"n": 1, "src": "A-01.png", "w": 10, "h": 5, "blocks": []}]},
            ]}), encoding="utf-8")
            got = build.load_slides(path)
            self.assertEqual(list(got), [("B", 1), ("B", 2), ("A", 1)])
            self.assertEqual(got[("B", 2)], {
                "src": path.parent / "B-02.jpg",
                "zh": ["<b>標題（Title）</b>", "線性式 y = a + bx"],
                "w": 10, "h": 5, "skip": False,
            })
            self.assertEqual(got[("B", 1)]["zh"], [])
            self.assertTrue(got[("B", 1)]["skip"])
            self.assertTrue(got[("A", 1)]["skip"])

    def test_missing_or_broken_manifest_stops(self):
        with tempfile.TemporaryDirectory() as d:
            for text in (None, "not json", '{"decks": [{"id": "A"}]}'):
                with self.subTest(text=text):
                    path = Path(d) / "slides.json"
                    if text is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_text(text, encoding="utf-8")
                    with self.assertRaises(SystemExit):
                        build.load_slides(path)

    def test_idle_text_groups_runs_by_deck(self):
        idle = [("L20", 1), ("L20", 4), ("L20", 5), ("L20", 6), ("L20", 9), ("L21", 2)]
        self.assertEqual(build.idle_text(idle), "L20 p.1、4–6、9；L21 p.2")


class DeckStep(unittest.TestCase):
    """add_deck：課件欄每頁一張原圖，有譯文時渲染 .deck-zh HTML 譯文層；skip 頁不進 idle。"""

    def deck(self, body, slides_dict=DECK, body_attrs=""):
        src, anchors = build.number_headings(f"<html><body{body_attrs}>{body}</body></html>")
        return build.add_deck(src, slides_dict, anchors, Path("/x"))

    def fig(self, out, key):
        return re.search(rf'<figure id="slide-{key}"[^>]*>.*?</figure>', out, re.S).group(0)

    def test_one_figure_per_listed_page_in_order_with_deck_names(self):
        out, _ = self.deck("<h2>一</h2>")
        aside = out[out.index('<aside class="deck"'):]
        order = [aside.index(x) for x in ('<h3 class="deck-name">L20</h3>', 'id="slide-L20-1"', 'id="slide-L20-2"',
                                          'id="slide-L20-3"', '<h3 class="deck-name">L21</h3>', 'id="slide-L21-1"')]
        self.assertEqual(order, sorted(order))
        self.assertTrue(out.endswith("</aside></body></html>"))

    def test_single_image_plus_html_translation_layer_below(self):
        out, _ = self.deck("<h2>一</h2>")
        self.assertIn('<img src="slides/L20-1.png" width="1000" height="563" alt="" loading="lazy">', self.fig(out, "L20-1"))
        self.assertNotIn("deck-zh", self.fig(out, "L20-1"))
        fig2 = self.fig(out, "L20-2")
        self.assertIn('<img src="slides/L20-2.png" width="1000" height="563" alt="" loading="lazy">', fig2)
        self.assertNotIn(".zh.png", fig2)
        self.assertIn('<div class="deck-zh"><p><b>平穩序列（stationary series）</b></p><p>資料大致水平。</p></div>', fig2)

    def test_slide_attr_becomes_the_figure_ids(self):
        out, _ = self.deck('<h2 class="a" data-slide="L20 p.1-2">一</h2><p data-slide=\'L20 p.3; L21 p.1\' id="p">x</p>')
        self.assertRegex(out, r'<h2 class="a" id="s1" data-at="slide-L20-1 slide-L20-2">')
        self.assertIn('<p id="p" data-at="slide-L20-3 slide-L21-1">x</p>', out)
        self.assertNotIn("data-slide=", out)

    def test_caption_links_to_each_section_that_teaches_the_page(self):
        out, _ = self.deck('<h2 data-slide="L20 p.1-2">一</h2><h3 data-slide="L20 p.2">甲</h3><p data-slide="L20 p.2">同一節再提一次</p>'
                           '<h2>二</h2><p data-slide="L20 p.2">x</p>')
        self.assertIn('<figcaption><b>L20 p.1</b><a class="to" href="#s1">§1</a></figcaption>', self.fig(out, "L20-1"))
        self.assertIn('<b>L20 p.2</b><a class="to" href="#s1">§1</a><a class="to" href="#s1-1">§1.1</a><a class="to" href="#s2">§2</a>',
                      self.fig(out, "L20-2"))

    def test_caption_lists_at_most_a_few_sections(self):
        out, _ = self.deck("".join(f'<h2 data-slide="L20 p.1">{i}</h2>' for i in range(build.MAX_USES + 3)))
        self.assertEqual(self.fig(out, "L20-1").count('class="to"'), build.MAX_USES)

    def test_key_pages_are_marked_and_untaught_pages_are_reported(self):
        out, report = self.deck('<h2>一</h2><p data-slide="L20 p.1" data-key>必記</p><p data-slide="L20 p.2">提到</p>')
        self.assertIn('id="slide-L20-1" class="key"', out)
        self.assertRegex(out, r'<figure id="slide-L20-2">')
        self.assertRegex(out, r'<figure id="slide-L20-3">')
        self.assertEqual(report, {"pages": 4, "used": 2, "key": 1, "idle": [("L20", 3), ("L21", 1)]})

    def test_skipped_slides_in_manifest_or_html_are_excluded_from_idle(self):
        custom = slides(("L20", 1, [], True), ("L20", 2), ("L20", 3), ("L21", 1))
        out, report = self.deck(
            '<h2 data-slide="L20 p.2">一</h2><span data-slide="L21 p.1" data-skip></span>',
            slides_dict=custom,
            body_attrs=' data-skip="L20 p.3"',
        )
        self.assertEqual(report, {"pages": 4, "used": 1, "key": 0, "idle": []})
        self.assertIn('id="slide-L20-1" class="skip"', out)
        self.assertNotIn("data-skip", out)
        self.assertNotIn("slide-L21-1\"", out.split('<aside class="deck"')[0])

    def test_key_mark_stays_on_the_element_for_the_highlights_view(self):
        out, _ = self.deck('<p data-slide="L20 p.1" data-key>x</p>')
        self.assertIn('<p data-key data-at="slide-L20-1">x</p>', out)
        self.assertIn('data-act="follow" aria-pressed="true"', out)

    def test_slide_before_any_heading_still_marks_the_page_used(self):
        out, report = self.deck('<p data-slide="L21 p.1">前言</p><h2>一</h2>')
        self.assertIn("<figcaption><b>L21 p.1</b></figcaption>", self.fig(out, "L21-1"))
        self.assertNotIn(("L21", 1), report["idle"])

    def test_self_closing_tag_keeps_its_slash(self):
        out, _ = self.deck('<h2>一</h2><hr data-slide="L20 p.1" />')
        self.assertIn('<hr data-at="slide-L20-1" />', out)


class Numbering(unittest.TestCase):
    def test_headings_get_numbers_and_anchors(self):
        out, anchors = build.number_headings("<h2>甲</h2><h3>乙</h3><h3 id='keep'>丙</h3><h2>丁</h2>")
        self.assertIn('<h2 id="s1"><span class="num">§1</span> 甲</h2>', out)
        self.assertIn('<h3 id="s1-1"><span class="num">§1.1</span> 乙</h3>', out)
        self.assertIn("<h3 id='keep'><span class=\"num\">§1.2</span> 丙</h3>", out)
        self.assertEqual(anchors, {"1": "s1", "1.1": "s1-1", "1.2": "keep", "2": "s2"})

    def test_refs_become_links_but_not_inside_links_numbers_code_pre_script_or_comments(self):
        src, anchors = build.number_headings(
            "<h2>甲</h2><h3>乙</h3>"
            "<p title='§1'>見 §1.1，沒有 §9，程式碼 <code>§1 與 §1.1</code></p>"
            "<pre>def f():\n    return '§1'</pre>"
            "<!-- 註解裡的 §1 -->"
            "<script>const r = '§1';</script>"
            "<p><a href='#x'>§1</a></p>"
        )
        out = build.link_refs(src, anchors)
        self.assertIn('見 <a class="ref" href="#s1-1">§1.1</a>，沒有 §9', out)
        self.assertIn("<code>§1 與 §1.1</code>", out)
        self.assertIn("<pre>def f():\n    return '§1'</pre>", out)
        self.assertIn("<!-- 註解裡的 §1 -->", out)
        self.assertIn("<script>const r = '§1';</script>", out)
        self.assertIn("<p title='§1'>", out)
        self.assertIn("<a href='#x'>§1</a>", out)
        self.assertIn('<span class="num">§1</span> 甲', out)


class MetaStep(unittest.TestCase):
    """add_meta：每個編號的 h2 帶 data-n 和目錄用的短標題；total_minutes 以 UNITS_PER_MIN=110 與動手權重估算。"""

    def run_meta(self, body):
        src, _ = build.number_headings(body)
        return build.add_meta(src)

    @staticmethod
    def h2_tag(out, anchor):
        return re.search(rf'<h2[^>]*\bid="{anchor}"[^>]*>', out).group(0)

    def test_heading_gets_its_number_and_no_reading_time(self):
        out = self.run_meta(f"<h2>短</h2><p>{'字' * 10}</p><h2>長</h2><p>{'字' * 900}</p>")
        self.assertIn('data-n="2"', self.h2_tag(out, "s2"))
        self.assertNotIn("data-min", out)
        self.assertNotIn("分鐘", out)
        self.assertNotIn('class="meta"', out)

    def test_short_title_drops_the_trailing_page_note(self):
        out = self.run_meta("<h2>今天和昨天有沒有關係？（講義 p.3）</h2><p>x</p>")
        self.assertIn('data-short="今天和昨天有沒有關係？"', self.h2_tag(out, "s1"))

    def test_author_short_title_is_kept(self):
        out = self.run_meta('<h2 data-short="自相關">今天和昨天有沒有關係？</h2><p>x</p>')
        self.assertEqual(self.h2_tag(out, "s1").count("data-short"), 1)
        self.assertIn('data-short="自相關"', out)

    def test_units_per_min_is_lowered_for_zero_prereq_readers(self):
        self.assertEqual(build.UNITS_PER_MIN, 110)
        self.assertGreater(build.WORK_MIN, 0.5)

    def test_minutes_follow_text_units_section_by_section(self):
        src = f"<h2>短</h2><p>{'字' * 10}</p><h2>長</h2><p>{'字' * build.UNITS_PER_MIN * 3}</p>"
        self.assertEqual(build.total_minutes(src), 1 + 3)

    def test_minutes_ignore_markup_and_count_english_by_word(self):
        words = " ".join(["word"] * build.UNITS_PER_MIN * 2)
        self.assertEqual(build.total_minutes(f'<h2>甲</h2><p class="{"x" * 2000}">{words}</p>'), 2)

    def test_each_calculation_and_self_check_adds_working_time(self):
        work = ('<div class="calc"><p>x</p></div><details class="check big"><summary>問</summary></details>'
                '<div class="quiz"><p>問</p></div><details class="answer"><summary>獨立題</summary></details>')
        expected = round(4 * build.WORK_MIN)
        self.assertEqual(build.total_minutes(f"<h2>甲</h2>{work}<details><summary>不是自測</summary></details>"), expected)


class CheatStep(unittest.TestCase):
    """add_cheat：速查卡前面加不編號的標題和按鈕。"""
    CARD = '<div class="cheat"><table class="types"></table></div>'

    def test_heading_and_print_button_come_right_before_the_card(self):
        out = build.add_cheat(f"<section>{self.CARD}</section>")
        self.assertTrue(out.startswith('<section><h2 class="plain" id="cheat">速查卡</h2><p class="cheat-tools">'), out)
        self.assertTrue(out.endswith(f"{self.CARD}</section>"))
        self.assertEqual(out.count('data-act="print"'), 1)

    def test_open_all_answers_only_when_there_are_folded_answers(self):
        self.assertNotIn('data-act="answers"', build.add_cheat(self.CARD))
        self.assertIn('data-act="answers"', build.add_cheat(self.CARD + '<details class="answer"><summary>做法</summary></details>'))

    def test_formatting_variants_still_get_it(self):
        for card in ('<DIV id="c" CLASS=\'wide cheat\'>x</DIV>', '<div class="cheat" data-x="1">x</div>'):
            with self.subTest(card=card):
                out = build.add_cheat(f"<section>\n{card}</section>")
                self.assertEqual(out.count('id="cheat"'), 1)
                self.assertLess(out.index('id="cheat"'), out.index("x</"))

    def test_only_the_first_card_gets_one_and_no_card_changes_nothing(self):
        self.assertEqual(build.add_cheat(self.CARD + self.CARD).count('id="cheat"'), 1)
        for src in ("<p>沒有</p>", '<div class="cheatsheet">x</div>', '<div class="x">cheat</div>'):
            with self.subTest(src=src):
                self.assertEqual(build.add_cheat(src), src)


class TermsStep(unittest.TestCase):
    """add_terms：正文最後加名詞表，每個 <dfn> 一列，連到它前面最近的編號標題。"""
    ROW = re.compile(r'<li><a class="ref" href="#([^"]+)">(.*?)</a><span>(.*?)</span><span class="where">§([^<]*)</span></li>')

    def terms(self, src):
        src, anchors = build.number_headings(src)
        return build.add_terms(src, anchors)

    def test_one_row_per_dfn_sorted_ignoring_case(self):
        out = self.terms("<body><p><dfn>前言</dfn></p><h2>甲</h2><p><dfn>香蕉（banana）</dfn></p>"
                         "<h3>乙</h3><p><dfn>紅蘋果 (Apple)</dfn></p><p><dfn>cherry</dfn>是水果（括號在外面的不算）</p>"
                         "<h2>例</h2><p><dfn>Zed</dfn></p></body>")
        self.assertEqual(self.ROW.findall(out), [("s1-1", "Apple", "紅蘋果", "1.1"), ("s1", "banana", "香蕉", "1"),
                                                 ("s1-1", "cherry", "", "1.1"), ("s2", "Zed", "", "2")])

    def test_table_goes_at_the_end_of_the_body(self):
        out = self.terms("<body><h2>甲</h2><p><dfn>a</dfn></p><p>最後一段</p></body>")
        self.assertRegex(out, r'最後一段</p><h2 class="plain" id="terms">名詞表</h2>.*<ul class="terms">.*</ul></body>$')
        self.assertEqual(out.count('id="terms"'), 1)

    def test_term_does_not_need_a_definition_box(self):
        out = self.terms('<body><h2 id="own">甲</h2><table><tr><td><DFN class="x">貝塔\n（<b>beta</b>）</DFN></td></tr></table></body>')
        self.assertEqual(self.ROW.findall(out), [("own", "<b>beta</b>", "貝塔", "1")])

    def test_no_dfn_or_only_before_any_heading_changes_nothing(self):
        for src in ("<body><h2>甲</h2><p>沒有名詞</p></body>", "<body><p><dfn>前言</dfn></p></body>"):
            with self.subTest(src=src):
                numbered, anchors = build.number_headings(src)
                self.assertEqual(build.add_terms(numbered, anchors), numbered)


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

    def test_other_aside_and_no_panel_stay(self):
        for src in (f'<aside class="notes">{self.T1}</aside>', "<p>沒有</p>"):
            with self.subTest(src=src[:20]):
                self.assertEqual(build.add_panel(src), src)


class ShellStep(unittest.TestCase):
    """outline / rail / add_shell：左邊目錄、頁眉、正文、課件欄、旁邊打開的那一段。"""
    ASIDE = '<aside class="deck" aria-label="課件"><div class="deck-body"><figure id="slide-L20-1"><img src="a.png"><div class="deck-zh"><p>譯文</p></div></figure></div></aside>'

    @staticmethod
    def shell(body, head="", attrs=""):
        return build.add_shell(f"<html><head>{head}</head><body{attrs}>{body}</body></html>")

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
        self.assertNotIn("has-deck", out)
        self.assertNotIn('data-act="deck"', out)

    def test_deck_moves_out_of_the_text_between_main_and_peek(self):
        out = self.shell(f"<p>內文</p>{self.ASIDE}")
        self.assertIn(f'<div class="page"><p>內文</p></div></main>{self.ASIDE}<button type="button" class="scrim"', out)
        self.assertEqual(out.count('<aside class="deck"'), 1)
        self.assertIn('<body class="has-deck">', out)
        self.assertIn('data-act="deck" aria-pressed="false">課件</button>', self.head_of(out))

    def test_deck_class_joins_an_existing_body_class(self):
        out = self.shell(self.ASIDE, attrs=' data-x="1" class="mine"')
        self.assertIn('<body data-x="1" class="has-deck mine">', out)

    def test_html_translation_layer_brings_the_language_switch(self):
        self.assertIn('data-act="lang-zh"', self.rail_of(self.shell(f"<p>x</p>{self.ASIDE}")))
        self.assertNotIn("lang-zh", self.rail_of(self.shell("<p>x</p>")))

    def test_quiz_in_body_adds_quiz_wrong_copy_tool_in_rail(self):
        with_quiz = self.rail_of(self.shell('<div class="quiz"><p>問</p><ul><li data-ok>對</li><li>錯</li></ul></div>'))
        self.assertIn('data-act="quiz-report"', with_quiz)
        self.assertNotIn('data-act="quiz-report"', self.rail_of(self.shell("<p>無點選題</p>")))

    def test_h1_gets_an_id_digest_note_and_a_hidden_resume(self):
        out = self.shell("<h1>書名</h1><p>x</p>")
        self.assertRegex(out, r'<h1 id="top">書名</h1><p class="digest-note">.*?data-act="digest-off".*?</p><p class="resume" hidden>')
        self.assertIn('<h1 id="mine">', self.shell('<h1 id="mine">書名</h1>'))

    def test_book_name_comes_from_h1_then_title(self):
        self.assertIn('<p class="book">書名</p>', self.shell("<h1><b>書</b>名</h1>", head="<title>頁標題</title>"))
        self.assertIn('<p class="book">頁標題</p>', self.shell("<p>x</p>", head="<title>頁標題</title>"))

    def test_tool_buttons_only_for_ids_that_exist(self):
        bare = self.shell("<p>x</p>")
        full = self.shell('<h2 id="cheat">速查卡</h2><h2 id="terms">名詞表</h2><div id="panel"></div>')
        for where in (self.head_of, self.rail_of):
            for act in ("cheat", "terms", "panel"):
                self.assertNotIn(f'data-act="{act}"', where(bare))
                self.assertIn(f'data-act="{act}"', where(full))
        self.assertNotIn("split", bare)

    def test_theme_switch_is_always_there(self):
        rail = self.rail_of(self.shell("<p>x</p>"))
        self.assertIn('data-act="theme-light"', rail)
        self.assertIn('data-act="theme-dark"', rail)

    def test_rail_groups_sections_under_parts_and_lists_subsections(self):
        src, _ = build.number_headings('<h1>書</h1><p class="part">第一講<span>Lecture 20</span></p><h2>甲（講義 p.3）</h2><h3>乙</h3>'
                                       '<p class="part">考前</p><h2 id="own">丁</h2>')
        rail = self.rail_of(self.shell(build.add_meta(src)))
        self.assertIn("<h2>開始<span></span></h2>", rail)
        self.assertIn("<h2>第一講<span>Lecture 20</span></h2>", rail)
        self.assertIn('<a href="#s1"><span class="n">1</span><span class="t">甲</span>', rail)
        self.assertIn('<ol class="sub"><li><a href="#s1-1">§1.1 乙</a></li></ol>', rail)
        self.assertLess(rail.index("<h2>考前<span></span></h2>"), rail.index('<a href="#own"><span class="n">2</span><span class="t">丁</span>'))

    def test_page_without_parts_is_one_group(self):
        src, _ = build.number_headings("<h2>甲</h2><h2>乙</h2>")
        rail = self.rail_of(self.shell(build.add_meta(src)))
        self.assertEqual(rail.count("<h2>"), 1)
        self.assertEqual(rail.count('<span class="n">'), 2)


class Output(unittest.TestCase):
    def built(self, body="<h2>一</h2><p>內容</p>", deck=None, **kw):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.png", "a.zh.png", "slides/L20-1.png", "slides/L20-2.png"):
                (Path(d) / name).parent.mkdir(exist_ok=True)
                (Path(d) / name).write_bytes(PNG + (b"zh" if ".zh." in name else b""))
            if deck:
                deck = {k: {**v, "src": Path(d) / "slides" / v["src"].name} for k, v in deck.items()}
            return build.build(page(body, **kw), Path(d), deck)

    def test_inlines_numbers_and_styles(self):
        out, report = self.built("<h2>甲</h2><h3>乙</h3><figure><img src=\"a.png\" alt=\"\"></figure>")
        self.assertIsNone(report)
        self.assertIn("data:image/png;base64,", out)
        self.assertNotIn('src="a.png"', out)
        self.assertRegex(out, r'<h2[^>]*\bid="s1"[^>]*><span class="num">§1</span> 甲')
        self.assertIn("<style>", out)
        self.assertIn("<script>", out)

    def test_translated_image_becomes_two_original_first(self):
        out, _ = self.built(f"<h2>甲</h2>{ZH_FIG}")
        zh, en = base64.b64encode(PNG + b"zh").decode(), base64.b64encode(PNG).decode()
        body = out.split("</style>", 1)[1]
        self.assertIn(f'<img class="zh" src="data:image/png;base64,{zh}" alt="">', body)
        self.assertLess(body.index(f'<img class="en" src="data:image/png;base64,{en}"'), body.index('<img class="zh"'))
        self.assertNotIn("data-zh", body)

    def test_existing_class_is_kept(self):
        out, _ = self.built('<h2>甲</h2><figure><img class="wide" data-zh="a.zh.png" src="a.png"></figure>')
        self.assertLess(out.index('class="en wide"'), out.index('class="zh wide"'))

    def test_missing_image_stops(self):
        for img in ('<img src="nope.png">', '<img src="a.png" data-zh="nope.png">'):
            with self.subTest(img=img), self.assertRaises(SystemExit):
                self.built(f"<h2>甲</h2><figure>{img}</figure>")

    def test_deck_pictures_inlined_once_with_html_zh_layer(self):
        out, report = self.built('<h2 data-slide="L20 p.2" data-key>甲</h2>', deck=slides(("L20", 1), ("L20", 2, True)))
        body = out.split("</style>", 1)[1]
        self.assertEqual(report["idle"], [("L20", 1)])
        self.assertIn('<body class="has-deck">', body)
        self.assertRegex(body, r'<figure id="slide-L20-2" class="key"><img src="data:image/png;base64,[^"]+" width="1000" '
                               r'height="563" alt="" loading="lazy"><figcaption>.*?</figcaption><div class="deck-zh"><p><b>平穩序列')
        self.assertLess(body.index("</main>"), body.index('<aside class="deck"'))
        self.assertIn('data-act="lang-zh"', body)

    def test_skills_root_env_resolves_pages_scripts(self):
        repo_root = Path(__file__).resolve().parents[3]
        env = {**os.environ, "SKILLS_ROOT": str(repo_root)}
        r = subprocess.run([sys.executable, "-c", f'import runpy; m = runpy.run_path({str(SCRIPT)!r}); assert hasattr(m["overflow"], "measure")'],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_page_declares_a_viewport_once_and_reads_the_theme_before_the_style(self):
        out, _ = self.built()
        self.assertEqual(len(re.findall(r'<meta\s+name="viewport"', out)), 1)
        self.assertIn('localStorage.getItem("tutor-theme")', out[:out.index("<style>")])
        own = '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        again = build.inject_assets(f"<html><head>{own}</head><body></body></html>")
        self.assertEqual(again.count('name="viewport"'), 1)


class Main(unittest.TestCase):
    def run_main(self, body="<h2>一</h2><p>內容</p>", attrs="", manifest=None, measure=lambda out: [], **kw):
        d = Path(tempfile.mkdtemp())
        for name in ("a.png", "slides/L20-01.png"):
            (d / name).parent.mkdir(exist_ok=True)
            (d / name).write_bytes(PNG)
        if manifest is not None:
            (d / "slides" / "slides.json").write_text(json.dumps(manifest), encoding="utf-8")
        (d / "guide-src.html").write_text(page(body, attrs=attrs, **kw), encoding="utf-8")
        out, err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8"), io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build.main([str(d / "guide-src.html")], measure=measure)
        out.flush(), err.flush()
        return code, d / "guide.html", out.buffer.getvalue().decode("utf-8"), err.buffer.getvalue().decode("utf-8")

    def test_violation_writes_nothing_and_says_why(self):
        code, out, _, err = self.run_main("<h2>一</h2><p>見 §7</p>")
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())
        self.assertIn("§7", err)

    def test_success_prints_the_page_and_how_long_it_takes_to_read(self):
        code, out, said, _ = self.run_main(f"<h2>一</h2><p>{'字' * build.UNITS_PER_MIN * 5}</p>")
        self.assertEqual(code, 0)
        self.assertTrue(out.is_file())
        self.assertIn(str(out), said)
        self.assertIn("讀完大約 5 分鐘", said)
        self.assertNotIn("課件欄", said)

    def test_deck_report_names_the_pages_the_text_never_reaches_excluding_skip(self):
        manifest = {"decks": [{"id": "L20", "pages": [
            {"n": 1, "src": "L20-01.png", "w": 10, "h": 5, "skip": True},
            {"n": 2, "src": "L20-01.png", "w": 10, "h": 5},
            {"n": 3, "src": "L20-01.png", "w": 10, "h": 5},
        ]}]}
        code, _, said, _ = self.run_main('<h2 data-slide="L20 p.2" data-key>一</h2>', attrs=' data-slides="slides/slides.json"',
                                         manifest=manifest)
        self.assertEqual(code, 0)
        self.assertIn("課件欄 3 頁：正文講到 1 頁，必記 1 頁；沒講到：L20 p.3", said)

    def test_slide_ref_off_the_manifest_writes_nothing(self):
        manifest = {"decks": [{"id": "L20", "pages": [{"n": 1, "src": "L20-01.png", "w": 10, "h": 5}]}]}
        code, out, _, err = self.run_main('<h2 data-slide="L20 p.2">一</h2>', attrs=' data-slides="slides/slides.json"', manifest=manifest)
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())
        self.assertIn("課件清單沒有 L20 p.2", err)

    def test_declared_manifest_that_is_missing_stops(self):
        with self.assertRaises(SystemExit):
            self.run_main(attrs=' data-slides="slides/slides.json"')

    def test_overflow_writes_nothing(self):
        code, out, _, _ = self.run_main(measure=lambda out: ["視窗寬 390px：整頁被撐寬 120px"])
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())

    def test_no_browser_still_writes_the_page(self):
        code, out, _, _ = self.run_main(measure=lambda out: None)
        self.assertEqual(code, 0)
        self.assertTrue(out.is_file())

    @unittest.skipUnless(build.overflow.find_browser(), "本機沒有 Chrome 或 Edge")
    def test_formula_wider_than_the_column_is_refused(self):
        wide = '<div class="formula" style="white-space:nowrap">' + "MAD = Σ|e| ÷ n；" * 40 + "</div>"
        code, out, _, err = self.run_main(f"<h2>一</h2>{wide}", measure=build.measure)
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())
        self.assertIn("被切掉", err)
        self.assertNotIn("被撐寬", err)

    @unittest.skipUnless(build.overflow.find_browser(), "本機沒有 Chrome 或 Edge")
    def test_ordinary_page_with_a_deck_is_delivered(self):
        manifest = {"decks": [{"id": "L20", "pages": [{"n": 1, "src": "L20-01.png", "zh": ["譯文"], "w": 1000, "h": 563}]}]}
        code, out, _, err = self.run_main('<h2 data-slide="L20 p.1">一</h2><div class="formula">MAD = Σ|e| ÷ n</div>',
                                          attrs=' data-slides="slides/slides.json"', manifest=manifest, measure=build.measure)
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.is_file())

    @unittest.skipUnless(build.overflow.find_browser(), "本機沒有 Chrome 或 Edge")
    def test_unbreakable_text_outside_a_scroller_is_refused(self):
        code, out, _, _ = self.run_main('<h2>一</h2><p><code style="white-space:nowrap">' + "x = 1; " * 300 + "</code></p>",
                                        measure=build.measure)
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())


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


if __name__ == "__main__":
    unittest.main()
