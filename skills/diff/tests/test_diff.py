import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCRIPT = os.path.join(HERE, "..", "scripts", "diff.py")
FILL = os.path.join(HERE, "..", "scripts", "fill.py")
DIFF_CSS = os.path.join(HERE, "..", "scripts", "diff.css")
DOCUMENT = os.path.join(HERE, "..", "scripts", "document.html")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import diff as d  # noqa: E402
import fill  # noqa: E402


def p(*texts):
    return [("p", t) for t in texts]


class WordOps(unittest.TestCase):
    def test_marks_only_the_changed_word(self):
        ops = d.word_ops("the trend has been removed", "most of the trend has been removed")
        self.assertEqual(ops, [["+", "most of "], ["=", "the trend has been removed"]])

    def test_identical_text_is_one_equal_op(self):
        self.assertEqual(d.word_ops("r12 = −0.386", "r12 = −0.386"), [["=", "r12 = −0.386"]])

    def test_ops_rebuild_both_sides(self):
        a, b = "a < b and c", "a <b> b or c"
        ops = d.word_ops(a, b)
        self.assertEqual("".join(t for o, t in ops if o != "+"), a)
        self.assertEqual("".join(t for o, t in ops if o != "-"), b)


class Align(unittest.TestCase):
    def test_unchanged_document_is_all_same(self):
        rows = d.align(p("A one.", "B two."), p("A one.", "B two."))
        self.assertEqual([r[0] for r in rows], ["same", "same"])

    def test_edited_paragraph_pairs_as_changed(self):
        rows = d.align(p("Intro.", "The values are listed below.", "End."),
                       p("Intro.", "The values are all listed below.", "End."))
        self.assertEqual([r[0] for r in rows], ["same", "changed", "same"])

    def test_unrelated_replacement_is_removed_plus_added(self):
        rows = d.align(p("Intro.", "Completely different sentence about lags.", "End."),
                       p("Intro.", "Zzz qqq.", "End."))
        self.assertEqual(sorted(r[0] for r in rows if r[0] != "same"), ["added", "removed"])

    def test_inserted_paragraph(self):
        rows = d.align(p("A.", "C."), p("A.", "B new.", "C."))
        self.assertEqual([r[0] for r in rows], ["same", "added", "same"])


class Tables(unittest.TestCase):
    def test_counts_changed_cells_only(self):
        before = [["t", "Yt"], ["1", "-681"], ["2", "299"]]
        after = [["t", "Yt"], ["1", "−681"], ["2", "299"]]
        t = d.table_diff(before, after)
        self.assertEqual(t["changed_cells"], 1)
        self.assertEqual([r["status"] for r in t["rows"]], ["same", "changed", "same"])
        self.assertEqual(t["rows"][1]["cells"][1]["before"], "-681")
        self.assertEqual(d.table_diff(before, before)["changed_cells"], 0)

    def test_inserted_column_aligns_by_header(self):
        before = [["t", "Yt", "Ŷt", "|e|"], ["2", "3828", "4509", "681"]]
        after = [["t", "Yt", "Ŷt", "Yt − Ŷt", "|e|"], ["2", "3828", "4509", "−681", "681"]]
        t = d.table_diff(before, after)
        self.assertEqual(t["changed_cells"], 0)
        self.assertIn([None, 3], t["columns"])
        after[1][4] = "680"
        self.assertEqual(d.table_diff(before, after)["changed_cells"], 1)

    def test_added_row_is_marked(self):
        t = d.table_diff([["a"]], [["a"], ["b"]])
        self.assertEqual([r["status"] for r in t["rows"]], ["same", "added"])


class Html(unittest.TestCase):
    def test_skips_script_and_style_and_splits_blocks(self):
        blocks = d.extract_html("<html><head><style>p{}</style></head><body><h1>Title</h1>"
                                "<p>One <b>bold</b> line.</p><script>var x = 1;</script><div>Two</div></body></html>")
        self.assertEqual(blocks, p("Title", "One bold line.", "Two"))

    def test_svg_text_is_a_block(self):
        blocks = d.extract_html("<svg><text>51 : 49</text><text>99.99%</text></svg>")
        self.assertEqual(blocks, p("51 : 49", "99.99%"))

    def test_extracts_structured_table_in_document_order(self):
        src = (
            "<h1>Summary</h1>"
            "<table><caption>表一</caption>"
            "<thead><tr><th>品項</th><th>備註</th><th>數量</th></tr></thead>"
            "<tbody><tr><td>紙箱<br>大號</td><td></td><td>1,200</td></tr></tbody>"
            "</table>"
            "<p>結尾</p>"
        )
        self.assertEqual(
            d.extract_html(src),
            [
                ("p", "Summary"),
                ("p", "表一"),
                ("table", [["品項", "備註", "數量"], ["紙箱 大號", "", "1,200"]]),
                ("p", "結尾"),
            ],
        )

    def test_html_files_produce_structured_table_diff_for_columns_and_cells(self):
        before_html = (
            "<!doctype html><html><body>"
            "<h1>盤點表</h1>"
            "<table>"
            "<tr><th>品項</th><th>帳面</th><th>備註</th></tr>"
            "<tr><td>紙箱</td><td>1,200</td><td>待查</td></tr>"
            "<tr><td>膠帶</td><td>80</td><td>正常</td></tr>"
            "</table>"
            "<table>"
            "<tr><th>倉庫</th><th>舊編號</th><th>負責人</th></tr>"
            "<tr><td>北區</td><td>N-01</td><td>王小明</td></tr>"
            "</table>"
            "</body></html>"
        )
        after_html = (
            "<!doctype html><html><body>"
            "<h1>盤點表</h1>"
            "<table>"
            "<tr><th>品項</th><th>單位</th><th>帳面</th><th>備註</th></tr>"
            "<tr><td>紙箱</td><td>個</td><td>1,030</td><td>待查</td></tr>"
            "<tr><td>膠帶</td><td>捲</td><td>80</td><td>正常</td></tr>"
            "</table>"
            "<table>"
            "<tr><th>倉庫</th><th>負責人</th></tr>"
            "<tr><td>北區</td><td>王小明</td></tr>"
            "</table>"
            "</body></html>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "before.html")
            b = os.path.join(tmp, "after.html")
            out = os.path.join(tmp, "diff.json")
            with open(a, "w", encoding="utf-8") as f:
                f.write(before_html)
            with open(b, "w", encoding="utf-8") as f:
                f.write(after_html)
            r = subprocess.run([sys.executable, SCRIPT, a, b, "-o", out, "--json-only"],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, encoding="utf-8") as f:
                data = json.load(f)

        self.assertEqual([blk["kind"] for blk in data["blocks"]], ["p", "table", "table"])
        tbl_add_col, tbl_del_col = data["blocks"][1], data["blocks"][2]
        self.assertEqual(tbl_add_col["status"], "changed")
        self.assertEqual(tbl_add_col["changed_cells"], 1)
        self.assertIn([None, 1], tbl_add_col["columns"])
        self.assertEqual(tbl_add_col["rows"][1]["status"], "changed")
        self.assertEqual(tbl_add_col["rows"][1]["cells"][2]["before"], "1,200")
        self.assertEqual(tbl_add_col["rows"][1]["cells"][2]["after"], "1,030")

        self.assertEqual(tbl_del_col["status"], "changed")
        self.assertEqual(tbl_del_col["changed_cells"], 0)
        self.assertIn([1, None], tbl_del_col["columns"])
        self.assertEqual(data["counts"]["table_cells"], 1)


class Words(unittest.TestCase):
    def test_english_by_word_chinese_by_char(self):
        self.assertEqual(d.words(p("The trend is removed.", "諾貝爾獎")), 4 + 4)

    def test_table_cells_count(self):
        self.assertEqual(d.words([("table", [["a b", "c"]])]), 3)


class Notes(unittest.TestCase):
    def test_note_attaches_to_changed_block_and_unmatched_is_returned(self):
        notes = [{"match": "listed below", "note": "填充句", "tag": "可精簡"}, {"match": "not in the document", "note": "x"}]
        blocks, counts, unmatched = d.diff(p("Intro.", "The values are listed below."), p("Intro."), notes)
        self.assertEqual(blocks[1]["notes"], [{"note": "填充句", "tag": "可精簡"}])
        self.assertEqual(counts["removed"], 1)
        self.assertEqual(counts["groups"], 1)
        self.assertEqual([u["match"] for u in unmatched], ["not in the document"])

    def test_groups_count_runs_of_changes(self):
        _, counts, _ = d.diff(p("A.", "B.", "C.", "D.", "E."), p("A.", "X.", "Y.", "C.", "D.", "Z."))
        self.assertEqual(counts["groups"], 2)

    def test_note_on_unchanged_block_does_not_attach(self):
        _, _, unmatched = d.diff(p("Intro.", "A."), p("Intro.", "B."), [{"match": "Intro", "note": "x"}])
        self.assertEqual(len(unmatched), 1)


class Fill(unittest.TestCase):
    def test_inlines_data_and_relative_media_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.png"), "wb") as f:
                f.write(b"PNG")
            tpl = ('<a href="https://example.com/doc">ref</a>'
                   '<script type="application/json" id="d">__DATA__</script>'
                   '<img src="a.png"><video src="data:video/mp4;base64,AA"></video>')
            page = fill.fill(tpl, {"t": "</script><b><img src='https://x/in-json.png'>"}, tmp)
        self.assertNotIn("__DATA__", page)
        self.assertNotIn("</script><b>", page)
        self.assertIn("data:image/png;base64,UE5H", page)
        self.assertIn('href="https://example.com/doc"', page)

    def test_rejects_external_media_urls(self):
        bad_snippets = (
            '<img src="https://x/y.png">',
            "<img src='http://x/y.png'>",
            '<video src="//cdn.example.com/demo.mp4"></video>',
            '<source src="https://x/a.webm">',
            '<video poster="https://x/poster.jpg"></video>',
        )
        for snippet in bad_snippets:
            with self.subTest(snippet=snippet):
                with self.assertRaises(SystemExit):
                    fill.fill(snippet, {}, ".")
                code, page, err = self.run_fill(snippet)
                self.assertEqual((code, page), (1, None))
                self.assertIn("外部網址", err)

    def test_skills_root_env_resolves_pages_scripts(self):
        with tempfile.TemporaryDirectory() as fake_root:
            self.assertEqual(
                fill.pages_scripts_dir({"SKILLS_ROOT": fake_root}),
                fill.Path(fake_root).resolve() / "pages" / "scripts",
            )
        self.assertEqual(
            fill.pages_scripts_dir({}),
            fill.Path(REPO_ROOT).resolve() / "pages" / "scripts",
        )
        # 把 fill.py 與 diff.css 放到脫離 repo 結構的獨立暫存目錄，靠 SKILLS_ROOT 找到 pages/scripts
        with tempfile.TemporaryDirectory() as isolated:
            scripts_dir = os.path.join(isolated, "standalone", "scripts")
            os.makedirs(scripts_dir)
            copied_fill = os.path.join(scripts_dir, "fill.py")
            shutil.copy2(FILL, copied_fill)
            shutil.copy2(DIFF_CSS, os.path.join(scripts_dir, "diff.css"))
            src = os.path.join(isolated, "page-src.html")
            out = os.path.join(isolated, "page.html")
            with open(src, "w", encoding="utf-8") as f:
                f.write("<!doctype html><html><head><title>t</title></head><body><p>ok</p></body></html>")
            env = {**os.environ, "SKILLS_ROOT": REPO_ROOT, "PATH": ""}
            r = subprocess.run([sys.executable, copied_fill, src, "-o", out],
                               env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, encoding="utf-8") as f:
                html_out = f.read()
            self.assertIn("--paper:", html_out)

    def test_missing_placeholder_fails_only_when_there_is_data(self):
        with self.assertRaises(SystemExit):
            fill.fill("<p>no data</p>", {"x": 1}, ".")
        self.assertEqual(fill.fill("<p>no data</p>", {}, "."), "<p>no data</p>")

    def test_cli_json_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out, j, t = (os.path.join(tmp, x) for x in ("p.html", "o.html", "d.json", "h.diff"))
            with open(src, "w", encoding="utf-8") as f:
                f.write("<script>const D = __DATA__;</script>")
            with open(j, "w", encoding="utf-8") as f:
                json.dump({"counts": {"groups": 1}}, f)
            with open(t, "w", encoding="utf-8") as f:
                f.write("+added line\n")
            r = subprocess.run([sys.executable, FILL, src, "-o", out, "--json", f"diff={j}", "--text", f"hunk={t}"],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, encoding="utf-8") as f:
                page = f.read()
        self.assertIn('"diff": {"counts": {"groups": 1}}', page)
        self.assertIn('"hunk": "+added line\\n"', page)

    def run_fill(self, body, head="", measure=lambda out: []):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = os.path.join(tmp, "p.html"), os.path.join(tmp, "o.html")
            with open(src, "w", encoding="utf-8") as f:
                f.write(f"<!DOCTYPE html><html><head><title>t</title>{head}</head><body>{body}</body></html>")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = fill.main([src, "-o", out], measure=measure)
            page = fill.Path(out).read_text(encoding="utf-8") if os.path.exists(out) else None
        return code, page, err.getvalue()

    def test_shared_styles_go_first_in_head(self):
        code, page, _ = self.run_fill("<p><del>a</del></p>", "<style>.mine{color:var(--ink);--my-gap:1rem}</style>")
        self.assertEqual(code, 0)
        order = [page.index(x) for x in ("--paper:", ".run-del", ".mine{")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(page.count("--paper: oklch(0.985"), 1)
        self.assertLess(page.index("<head>"), page.index("--paper:"))

    def test_page_redefining_a_token_is_refused(self):
        for css in (":root{--paper:#fff}", ":root{ --del-bg : red }", "@media print{:root{--font-doc:serif}}"):
            code, page, err = self.run_fill("<p>x</p>", f"<style>{css}</style>")
            self.assertEqual((code, page), (1, None), css)
            self.assertIn("tokens.css", err)
        # 用變數、定義自己的變數、在正文裡提到變數名都不算
        code, page, _ = self.run_fill("<p>顏色取 <code>--paper: …</code></p>", "<style>.x{background:var(--del-bg);--my-ink:red}</style>")
        self.assertEqual(code, 0)

    def test_overflowing_page_is_not_delivered(self):
        code, page, err = self.run_fill("<p>x</p>", measure=lambda out: ["視窗寬 390px：整頁被撐寬 40px"])
        self.assertEqual((code, page), (1, None))
        self.assertIn("視窗寬 390px", err)
        # 找不到瀏覽器（None）照樣產出，並提醒
        code, page, err = self.run_fill("<p>x</p>", measure=lambda out: None)
        self.assertEqual(code, 0)
        self.assertIsNotNone(page)
        self.assertIn("沒有量水平溢出", err)

    def test_every_colour_in_diff_css_comes_from_a_token(self):
        css = fill.Path(DIFF_CSS).read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b|\boklch\((?!\s*,)[0-9. ]+\)|\bhsl\(", css), [])
        tokens = set(re.findall(r"--([a-z0-9-]+)\s*:", fill.STYLES[0].read_text(encoding="utf-8")))
        used = set(re.findall(r"var\(--([a-z0-9-]+)", css))
        self.assertEqual(used - tokens - {"at", "bar-h"}, set())


class DocumentPage(unittest.TestCase):
    """出貨的文件頁 document.html 把 diff.json 畫成整頁。用本機的 Chrome 或 Edge 跑頁面的 JS，找不到就跳過。"""

    BEFORE = (p("Nothing changes here.", "The second paragraph has a typo.", "Nor here.")
              + [("table", [["項目", "金額"], ["甲", "1,204"], ["乙", "30"]])] + p("結尾。"))
    AFTER = (p("Nothing changes here.", "The second paragraph had a typo.", "Nor here.")
             + [("table", [["項目", "金額"], ["甲", "1,240"], ["乙", "30"]])] + p("結尾。", "新加的一段。"))
    MERGED = "document.querySelector('.seg [data-view=merged]').click();"

    def write(self, tmp, before, after, notes=None):
        blocks, counts, _ = d.diff(before, after, notes)
        data = {"before": {"label": "一稿", "path": "a.docx"}, "after": {"label": "二稿", "path": "b.docx"},
                "counts": counts, "blocks": blocks}
        with open(DOCUMENT, encoding="utf-8") as f:
            tpl = f.read()
        page = os.path.join(tmp, "page.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(fill.with_styles(fill.fill(tpl, {"diff": data}, tmp)))
        return fill.Path(page), counts

    def draw(self, before, after, notes=None, prepare="", width=1440):
        """回傳 (畫出來的文件那一段 HTML，含後面的上一處／下一處；頁首那一行計數；counts)。prepare 是畫完之後先跑的 JS。"""
        with tempfile.TemporaryDirectory() as tmp:
            page, counts = self.write(tmp, before, after, notes)
            dom = fill.overflow.render(page, width, prepare)
        if dom is None:
            self.skipTest("找不到 Chrome 或 Edge")
        doc = dom[dom.index('<div id="doc">'):dom.index('<script type="application/json"')]
        return doc, re.search(r'id="meta">([^<]*)<', dom).group(1), counts

    def test_side_by_side_draws_each_version_in_its_own_column(self):
        doc, meta, counts = self.draw(self.BEFORE, self.AFTER)
        self.assertEqual(counts["groups"], 3)
        self.assertEqual(doc.count('class="row g'), counts["groups"])
        self.assertEqual(meta, "一稿 → 二稿 · 3 處改動 · 表格改了 1 格")
        # 前版那一欄只有刪掉的字，後版那一欄只有加上的字
        self.assertRegex(doc, r'<p class="chg">[^<]*<del>[^<]*has[^<]*</del>[^<]*</p>')
        self.assertRegex(doc, r'<p class="chg">[^<]*<ins>[^<]*had[^<]*</ins>[^<]*</p>')
        self.assertEqual(doc.count('class="cell-chg"'), 2 * counts["table_cells"])
        # 整段新增只畫在後版；前版那一欄是空的，連標籤都不放
        self.assertRegex(doc, r'<div></div><div><div class="side-label">後 · 二稿</div><div class="run run-ins">')
        self.assertIn('<div class="row g cur" data-k="1">', doc)
        self.assertIn("第 1 / 3 處", doc)

    def test_merged_view_marks_both_versions_in_one_paragraph(self):
        doc, _, counts = self.draw(self.BEFORE, self.AFTER, prepare=self.MERGED)
        self.assertRegex(doc, r'<p class="chg">[^<]*<del>[^<]*has[^<]*</del>[^<]*<ins>[^<]*had[^<]*</ins>')
        self.assertEqual(doc.count('class="cell-chg"'), counts["table_cells"])
        self.assertNotIn("side-label", doc)
        # 短格子整格替換，不拆成「1,」加上改掉的三位數
        self.assertIn("<del>1,204</del> <ins>1,240</ins>", doc)

    def test_changes_only_folds_unchanged_runs_and_a_fold_reopens(self):
        same = ["a1", "a2", "a3", "a4"], ["b1", "b2", "b3"]
        before, after = p(*same[0], "old words here", *same[1]), p(*same[0], "new words here", *same[1])
        doc, _, _ = self.draw(before, after, prepare="document.getElementById('only').click();")
        # 改動的前後各留一段（a4、b1），其餘收起來
        self.assertEqual(re.findall(r'class="gap"[^>]*>([^<]*)<', doc), ["⋯ 3 段沒有改動", "⋯ 2 段沒有改動"])
        self.assertNotIn("<p>a1</p>", doc)
        self.assertIn("<p>a4</p>", doc)
        self.assertIn("<p>b1</p>", doc)
        doc, _, _ = self.draw(before, after, prepare="document.getElementById('only').click(); document.querySelector('.gap').click();")
        self.assertEqual(re.findall(r'class="gap"[^>]*>([^<]*)<', doc), ["⋯ 2 段沒有改動"])
        self.assertIn("<p>a1</p>", doc)

    def test_notes_sit_under_their_change_and_next_moves_the_cursor(self):
        notes = [{"match": "had a typo", "note": "審查第 2 輪指出", "tag": "必須修"}, {"match": "新加的一段", "note": "補上結論", "tag": "推斷"}]
        doc, _, _ = self.draw(self.BEFORE, self.AFTER, notes, prepare="document.querySelector('[data-go=\"1\"]').click();")
        self.assertIn('<div class="note"><span class="tag">必須修</span>審查第 2 輪指出</div>', doc)
        self.assertIn('<div class="note"><span class="tag guess">推斷</span>補上結論</div>', doc)
        self.assertIn('<div class="row g cur" data-k="3">', doc)
        self.assertNotIn('<div class="row g cur" data-k="1">', doc)
        self.assertIn("第 2 / 3 處", doc)

    def test_added_column_and_row_are_marked_and_left_out_of_the_old_version(self):
        before = p("表一") + [("table", [["項目", "金額"], ["甲", "10"]])]
        after = p("表一") + [("table", [["項目", "單位", "金額"], ["甲", "元", "10"], ["乙", "元", "20"]])]
        doc, _, _ = self.draw(before, after)
        old, new = re.findall(r"<table>.*?</table>", doc)
        self.assertNotIn("單位", old)
        self.assertNotIn("乙", old)
        self.assertIn('<td class="col-add"><span class="tag">新欄</span>單位</td>', new)
        self.assertRegex(new, r'<tr class="row-add"><td class="mark">\+</td><td>乙</td>')

    def test_page_does_not_overflow_with_a_wide_table(self):
        wide = [[f"欄位{i}" for i in range(14)], [f"一段比較長的內容 {i}" for i in range(14)]]
        changed = [wide[0], [c + "改" for c in wide[1]]]
        with tempfile.TemporaryDirectory() as tmp:
            page, _ = self.write(tmp, p("x " * 80) + [("table", wide)], p("y " * 80) + [("table", changed)])
            found = fill.overflow.measure(page)
        if found is None:
            self.skipTest("找不到 Chrome 或 Edge")
        self.assertEqual(found, [])


class Docx(unittest.TestCase):
    def setUp(self):
        try:
            import docx  # noqa: F401
        except ImportError:
            self.skipTest("python-docx not installed")

    def make(self, path, paras, table):
        import docx
        doc = docx.Document()
        doc.add_paragraph(paras[0])
        t = doc.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, v in enumerate(row):
                t.cell(r, c).text = v
        for x in paras[1:]:
            doc.add_paragraph(x)
        doc.save(path)

    def test_paragraphs_and_table_in_document_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "a.docx")
            self.make(f, ["Before table.", "After table."], [["h1", "h2"], ["1", "2"]])
            blocks = d.extract_docx(f)
        self.assertEqual(blocks, [("p", "Before table."), ("table", [["h1", "h2"], ["1", "2"]]), ("p", "After table.")])

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, out, n = (os.path.join(tmp, x) for x in ("a.docx", "b.docx", "o.json", "n.json"))
            self.make(a, ["Intro.", "The trend has been removed."], [["e", "MAD"], ["-681", "437.61"]])
            self.make(b, ["Intro.", "Most of the trend has been removed."], [["e", "MAD"], ["−681", "437.61"]])
            with open(n, "w", encoding="utf-8") as f:
                json.dump([{"match": "Most of the trend", "note": "說過頭"}], f)
            r = subprocess.run([sys.executable, SCRIPT, a, b, "-o", out, "--notes", n],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("UNMATCHED", r.stderr)
            self.assertIn("groups=1 changed=2 added=0 removed=0 table_cells=1", r.stderr)
            with open(out, encoding="utf-8") as f:
                data = json.load(f)
        changed = [b for b in data["blocks"] if b["status"] == "changed"]
        self.assertEqual(changed[0]["kind"], "table")
        self.assertEqual(changed[1]["notes"][0]["note"], "說過頭")
        self.assertEqual(changed[1]["ops"][0], ["-", "The"])


class Pdf(unittest.TestCase):
    def test_pdf_text_blocks(self):
        try:
            import pymupdf
        except ImportError:
            self.skipTest("pymupdf not installed")
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "a.pdf")
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Poster title")
            page.insert_text((72, 300), "Second block")
            doc.save(f)
            doc.close()
            blocks = d.extract_pdf(f)
        self.assertEqual(blocks, p("Poster title", "Second block"))


if __name__ == "__main__":
    unittest.main()
