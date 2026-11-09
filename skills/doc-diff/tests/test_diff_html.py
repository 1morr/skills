import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "diff_html.py")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import diff_html as d  # noqa: E402


def p(*texts):
    return [("p", t) for t in texts]


class WordDiff(unittest.TestCase):
    def test_marks_only_the_changed_word(self):
        left, right, merged = d.word_diff("the trend has been removed", "most of the trend has been removed")
        self.assertNotIn("<del>", left)
        self.assertIn("<ins>most of </ins>", right)
        self.assertIn("removed", merged)

    def test_identical_text_has_no_marks(self):
        left, right, merged = d.word_diff("r12 = −0.386 is negative", "r12 = −0.386 is negative")
        for s in (left, right, merged):
            self.assertNotIn("<del>", s)
            self.assertNotIn("<ins>", s)

    def test_escapes_html(self):
        _, right, _ = d.word_diff("a < b", "a <b> b")
        self.assertNotIn("<b>", right)
        self.assertIn("&lt;", right)
        self.assertIn("&gt;", right)


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
        self.assertEqual(d.table_changed_cells(before, after), 1)
        self.assertEqual(d.table_changed_cells(before, before), 0)

    def test_inserted_column_aligns_by_header(self):
        before = [["t", "Yt", "Ŷt", "|e|"], ["2", "3828", "4509", "681"]]
        after = [["t", "Yt", "Ŷt", "Yt − Ŷt", "|e|"], ["2", "3828", "4509", "−681", "681"]]
        self.assertEqual(d.table_changed_cells(before, after), 0)
        self.assertIn("col-added", d.table_html(before, after))
        after[1][4] = "680"
        self.assertEqual(d.table_changed_cells(before, after), 1)

    def test_added_row_is_marked(self):
        html = d.table_html([["a"]], [["a"], ["b"]])
        self.assertIn("class='added'", html)


class Html(unittest.TestCase):
    def test_skips_script_and_style_and_splits_blocks(self):
        blocks = d.extract_html("<html><head><style>p{}</style></head><body><h1>Title</h1>"
                                "<p>One <b>bold</b> line.</p><script>var x = 1;</script><div>Two</div></body></html>")
        self.assertEqual(blocks, p("Title", "One bold line.", "Two"))

    def test_svg_text_is_a_block(self):
        blocks = d.extract_html("<svg><text>51 : 49</text><text>99.99%</text></svg>")
        self.assertEqual(blocks, p("51 : 49", "99.99%"))


class Words(unittest.TestCase):
    def test_english_by_word_chinese_by_char(self):
        self.assertEqual(d.words(p("The trend is removed.", "諾貝爾獎")), 4 + 4)

    def test_table_cells_count(self):
        self.assertEqual(d.words([("table", [["a b", "c"]])]), 3)


class Notes(unittest.TestCase):
    def test_note_attaches_to_changed_row_and_unmatched_is_reported(self):
        notes = {"notes": [{"match": "listed below", "note": "填充句", "tag": "可精簡"},
                           {"match": "not in the document", "note": "x"}]}
        page, unmatched = d.build(p("Intro.", "The values are listed below."), p("Intro."), notes)
        self.assertIn("填充句", page)
        self.assertEqual([u["match"] for u in unmatched], ["not in the document"])
        self.assertIn("沒對上段落的說明", page)

    def test_note_on_unchanged_row_does_not_attach(self):
        notes = {"notes": [{"match": "Intro", "note": "x"}]}
        _, unmatched = d.build(p("Intro.", "A."), p("Intro.", "B."), notes)
        self.assertEqual(len(unmatched), 1)


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
            a, b, out, n = (os.path.join(tmp, x) for x in ("a.docx", "b.docx", "o.html", "n.json"))
            self.make(a, ["Intro.", "The trend has been removed."], [["e", "MAD"], ["-681", "437.61"]])
            self.make(b, ["Intro.", "Most of the trend has been removed."], [["e", "MAD"], ["−681", "437.61"]])
            with open(n, "w", encoding="utf-8") as f:
                json.dump({"notes": [{"match": "Most of the trend", "note": "說過頭"}]}, f)
            r = subprocess.run([sys.executable, SCRIPT, a, b, "-o", out, "--notes", n],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("UNMATCHED", r.stderr)
            with open(out, encoding="utf-8") as f:
                page = f.read()
        self.assertIn("改動 2 處，表格改了 1 格", page)
        self.assertIn("說過頭", page)
        self.assertIn("<ins>Most of the</ins>", page.replace("<ins>Most</ins><ins>", "<ins>Most"))


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
