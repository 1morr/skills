import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "diff.py")
FILL = os.path.join(HERE, "..", "scripts", "fill.py")
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
            tpl = ('<script type="application/json" id="d">__DATA__</script>'
                   '<img src="a.png"><img src="https://x/y.png"><video src="data:video/mp4;base64,AA"></video>')
            page = fill.fill(tpl, {"t": "</script><b>"}, tmp)
        self.assertNotIn("__DATA__", page)
        self.assertNotIn("</script><b>", page)
        self.assertIn("data:image/png;base64,UE5H", page)
        self.assertIn("https://x/y.png", page)

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
