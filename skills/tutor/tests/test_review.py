"""review.py：從組好的導讀頁取出速查卡、讀筆記、把筆記接到題型下面。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "review.py"
spec = importlib.util.spec_from_file_location("review", SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)

CHEAT = ('<div class="cheat"><h4>題型</h4><table class="types"><tr><th>看到什麼</th><th>用什麼</th><th>示範</th></tr>'
         '<tr data-type="seasonal-index"><td>季資料</td><td><div class="formula">S = Y / CMA</div></td>'
         '<td><a class="ref" href="#s11">§11</a></td></tr>'
         '<tr data-type="deseason" data-reads="figure"><td>去季節化</td><td>Y ÷ S</td><td><a class="ref" href="#s12">§12</a></td></tr>'
         '</table><div class="rules"><div>門檻</div></div></div>')
GUIDE = ('<!DOCTYPE html><html lang="zh-Hant"><head><title>g</title></head><body><main><div class="page">'
         '<h1 id="top">Topic 5：<i>時間</i>序列分解</h1><h2 id="s11">§11 Eg</h2><h2 id="s12">§12 Eg</h2><h3 id="s4-6">§4.6</h3>'
         f'<h2 class="plain" id="cheat">速查卡</h2>{CHEAT}<p>後面的正文</p></div></main>'
         '<script>const x = "<div class=\\"peek\\"></div>";</script></body></html>')
NOTES = """# 筆記

## topic5-guide.html

### seasonal-index
- 錯過（11/16 練習 1）：四個全部平均 → 先劃掉最高 <0.86>、最低 0.78，見 §4.6 和 §99
- 懂了：像評審給分
  去掉最高分和最低分

### deseason
"""


class CheatCard(unittest.TestCase):
    def test_takes_the_whole_card_with_nested_divs(self):
        self.assertEqual(review.cheat_of(GUIDE), CHEAT)

    def test_class_order_and_case_do_not_matter(self):
        page = GUIDE.replace('<div class="cheat">', "<DIV id='c' class='x cheat y'>")
        self.assertTrue(review.cheat_of(page).startswith("<DIV id='c'"))
        self.assertTrue(review.cheat_of(page).endswith("門檻</div></div></div>"))

    def test_page_without_a_card_gives_none(self):
        self.assertIsNone(review.cheat_of(GUIDE.replace('class="cheat"', 'class="cheats"')))


class Notes(unittest.TestCase):
    def test_reads_notes_by_guide_and_type(self):
        notes, problems = review.parse_notes(NOTES)
        self.assertEqual(problems, [])
        self.assertEqual(list(notes), ["topic5-guide.html"])
        got = notes["topic5-guide.html"]
        self.assertEqual(len(got["seasonal-index"]), 2)
        self.assertEqual(got["seasonal-index"][1], "懂了：像評審給分 去掉最高分和最低分")  # 沒有「- 」的下一行接在上一條後面
        self.assertEqual(got["deseason"], [])

    def test_other_headings_are_the_readers_own_and_skipped(self):
        text = "## Topic 1：信賴區間\n\n### 1. 符號\n- σ 是母體標準差\n\n### which-table\n- 自己的筆記\n" + NOTES
        notes, problems = review.parse_notes(text)
        self.assertEqual(problems, [])
        self.assertEqual(list(notes), ["topic5-guide.html"])
        self.assertEqual(len(notes["topic5-guide.html"]["seasonal-index"]), 2)

    def test_a_new_top_heading_ends_the_guide_section(self):
        notes, _ = review.parse_notes(NOTES + "\n# 別的\n- 不算\n")
        self.assertEqual(notes["topic5-guide.html"]["deseason"], [])

    def test_fenced_examples_are_not_notes(self):
        notes, problems = review.parse_notes("```markdown\n## topic9-guide.html\n### x\n- 範例\n```\n" + NOTES)
        self.assertEqual(problems, [])
        self.assertEqual(list(notes), ["topic5-guide.html"])

    def test_type_heading_before_any_guide_fails(self):
        _, problems = review.parse_notes("### seasonal-index\n- 錯過：x\n")
        self.assertTrue(any("前面沒有導讀頁的 ## 標題" in p for p in problems), problems)

    def test_bullet_before_a_type_heading_fails(self):
        _, problems = review.parse_notes("## topic5-guide.html\n- 錯過：x\n")
        self.assertTrue(any("前面沒有題型的 ### 標題" in p for p in problems), problems)

    def test_marker_and_backticks_vary(self):
        notes, problems = review.parse_notes("## `Topic5-Guide.HTML`\n### `seasonal-index`\n* 懂了: ok\n")
        self.assertEqual(problems, [])
        self.assertEqual(notes["Topic5-Guide.HTML"]["seasonal-index"], ["懂了: ok"])


class Page(unittest.TestCase):
    def build(self, notes=NOTES, guides=None):
        parsed, _ = review.parse_notes(notes)
        return review.assemble(guides or [("topic5-guide.html", "lessons/topic5-guide.html", GUIDE)], parsed, "ISOM3031 考前速查")

    def test_notes_sit_under_their_type_row(self):
        page, problems, warns = self.build()
        self.assertEqual((problems, warns), ([], []))
        row = page.index('data-type="seasonal-index"')
        mine = page.index('<tr class="mine"><td colspan="3">')
        self.assertLess(row, mine)
        self.assertLess(mine, page.index('data-type="deseason"'))
        self.assertEqual(page.count('class="mine"'), 1)  # 沒有筆記的題型不加空列

    def test_note_text_is_escaped_and_labelled(self):
        page, _, _ = self.build()
        self.assertIn('<b class="mk mk-pink">錯過（11/16 練習 1）</b>', page)
        self.assertIn("<b>懂了</b> 像評審給分 去掉最高分和最低分", page)
        self.assertIn("&lt;0.86&gt;", page)

    def test_section_marks_link_to_the_guide_only_when_it_has_them(self):
        page, _, _ = self.build()
        self.assertIn('<a class="ref" href="lessons/topic5-guide.html#s4-6" target="_blank">§4.6</a>', page)
        self.assertIn("和 §99", page)

    def test_card_links_point_into_the_guide(self):
        page, _, _ = self.build()
        self.assertIn('<a class="ref" href="lessons/topic5-guide.html#s11" target="_blank">§11</a>', page)
        self.assertNotIn('href="#s1', page)

    def test_each_guide_gets_a_titled_section_in_order(self):
        four = GUIDE.replace("Topic 5：<i>時間</i>序列分解", "Topic 4")
        page, problems, _ = self.build(guides=[("topic4-guide.html", "topic4-guide.html", four),
                                               ("topic5-guide.html", "topic5-guide.html", GUIDE)])
        self.assertEqual(problems, [])
        self.assertLess(page.index('<h2 class="plain">Topic 4</h2>'), page.index('<h2 class="plain">Topic 5：時間序列分解</h2>'))
        self.assertEqual(page.count('<tr class="mine">'), 1)  # Topic 5 的筆記只接到 Topic 5

    BARE = "<html><body><h1>Topic 6</h1><h2 id=\"s3\">§3 四型</h2></body></html>"

    def test_guide_without_a_card_shows_only_its_notes(self):
        notes = "## topic6-guide.html\n### §3 四型\n- 錯過：把 Burma 選成 ethnic\n"
        page, problems, warns = self.build(notes, guides=[("topic6-guide.html", "topic6-guide.html", self.BARE)])
        self.assertEqual((problems, warns), ([], []))
        self.assertIn('<h2 class="plain">Topic 6</h2>', page)
        self.assertIn('<h4><a class="ref" href="topic6-guide.html#s3" target="_blank">§3</a> 四型</h4>'
                      '<ul class="mine"><li><b class="mk mk-pink">錯過</b> 把 Burma 選成 ethnic</li></ul>', page)

    def test_guide_with_neither_card_nor_notes_is_left_out(self):
        page, problems, warns = self.build(guides=[("topic5-guide.html", "topic5-guide.html", GUIDE),
                                                   ("topic6-guide.html", "topic6-guide.html", self.BARE)])
        self.assertEqual(problems, [])
        self.assertTrue(any("topic6-guide.html" in w for w in warns), warns)
        self.assertNotIn("Topic 6", page)

    def test_nothing_to_show_fails(self):
        _, problems, _ = self.build("", guides=[("topic6-guide.html", "topic6-guide.html", self.BARE)])
        self.assertTrue(any("沒有東西可放" in p for p in problems), problems)

    def test_unknown_type_is_kept_at_the_end_with_a_warning(self):
        page, problems, warns = self.build(NOTES.replace("### deseason", "### seasonal-indx\n- 懂了：打錯代號的筆記"))
        self.assertEqual(problems, [])
        self.assertTrue(any("seasonal-indx" in w for w in warns), warns)
        self.assertIn("打錯代號的筆記", page)
        self.assertGreater(page.index("打錯代號的筆記"), page.index("門檻"))

    def test_notes_for_a_guide_not_given_warn(self):
        _, problems, warns = self.build(NOTES.replace("topic5-guide.html", "topic4-guide.html"))
        self.assertEqual(problems, [])
        self.assertTrue(any("topic4-guide.html" in w for w in warns), warns)

    def test_page_is_one_file_without_the_guide_script(self):
        page, _, _ = self.build(notes="")
        self.assertIn('<body class="review">', page)
        self.assertIn("body.review", page)
        self.assertNotIn("後面的正文", page)
        self.assertNotIn('class=\\"peek\\"', page)


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "lessons").mkdir()
        (self.dir / "lessons" / "topic5-guide.html").write_text(GUIDE, encoding="utf-8")
        (self.dir / "notes.md").write_text(NOTES, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, measure=lambda page: []):
        out, err = (io.TextIOWrapper(io.BytesIO(), encoding="utf-8") for _ in range(2))  # main 會 reconfigure 這兩個串流
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = review.main([str(a) for a in args], measure=measure)
        err.flush()
        return code, err.buffer.getvalue().decode("utf-8")

    def test_writes_the_page_with_links_relative_to_it(self):
        out = self.dir / "lessons" / "review.html"
        code, _ = self.run_cli(self.dir / "lessons" / "topic5-guide.html", "--notes", self.dir / "notes.md", "-o", out)
        self.assertEqual(code, 0)
        self.assertIn('href="topic5-guide.html#s11"', out.read_text(encoding="utf-8"))

    def test_works_without_notes(self):
        out = self.dir / "review.html"
        code, _ = self.run_cli(self.dir / "lessons" / "topic5-guide.html", "-o", out)
        self.assertEqual(code, 0)
        self.assertIn('href="lessons/topic5-guide.html#s11"', out.read_text(encoding="utf-8"))

    def test_writes_nothing_when_red(self):
        out = self.dir / "review.html"
        for args in ((self.dir / "missing.html", "-o", out),
                     (self.dir / "lessons" / "topic5-guide.html", "--notes", self.dir / "none.md", "-o", out)):
            code, err = self.run_cli(*args)
            self.assertEqual(code, 1)
            self.assertIn("找不到", err)
            self.assertFalse(out.exists())

    def test_writes_nothing_when_the_page_overflows(self):
        out = self.dir / "review.html"
        code, _ = self.run_cli(self.dir / "lessons" / "topic5-guide.html", "-o", out, measure=lambda page: ["視窗寬 390px：撐寬"])
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
