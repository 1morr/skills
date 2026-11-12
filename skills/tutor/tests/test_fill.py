"""fill.py：值填進 {{名稱}}，答案紙的段落放進 {{sheet:a}}；有一個沒填到就不產出。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fill.py"
spec = importlib.util.spec_from_file_location("fill", SCRIPT)
fill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fill)

SHEET = ('<div class="part" data-part="a"><p>t = 2.262</p></div><!--/part-->\n'
         "<div data-part='b' class='part'>\n<p>Reject <i>H</i><sub>0</sub>.</p>\n</div>\n<!--/part-->")


class Fill(unittest.TestCase):
    def ok(self, template, values, sheet=None):
        out, problems = fill.fill(template, values, sheet)
        self.assertEqual(problems, [])
        return out

    def red(self, key, template, values, sheet=None):
        problems = fill.fill(template, values, sheet)[1]
        self.assertTrue(any(key in p for p in problems), f"想要有「{key}」，實際：{problems}")

    def test_values_fill_in(self):
        self.assertEqual(self.ok("t = {{t}}, so {{ decision }}; t = {{t}}", {"t": "2.262", "decision": "reject <i>H</i>"}),
                         "t = 2.262, so reject <i>H</i>; t = 2.262")

    def test_unused_values_are_fine(self):
        self.assertEqual(self.ok("t = {{t}}", {"t": "1", "f": "9"}), "t = 1")

    def test_single_braces_stay(self):
        self.assertEqual(self.ok("x_{t} and { a }", {}), "x_{t} and { a }")

    def test_missing_value_fails_and_names_each_once(self):
        problems = fill.fill("{{t}} {{f}} {{t}}", {})[1]
        self.assertEqual(problems, ["values.json 沒有這幾個值：t、f"])

    def test_non_string_value_fails(self):
        for bad in (2.262, 3, True, None, ["a"]):
            with self.subTest(bad=bad):
                self.red("要是字串", "{{t}}", {"t": bad})

    def test_values_must_be_an_object(self):
        self.red("最外層", "{{t}}", ["t"])

    def test_sheet_part_copied_verbatim(self):
        out = self.ok('<div class="sheet">{{sheet:a}}</div><div class="sheet">{{sheet:b}}</div>', {}, SHEET)
        self.assertEqual(out, '<div class="sheet"><p>t = 2.262</p></div>'
                              '<div class="sheet"><p>Reject <i>H</i><sub>0</sub>.</p></div>')

    def test_sheet_placeholder_without_sheet_fails(self):
        self.red("沒給 --sheet", "{{sheet:a}}", {})

    def test_unknown_part_fails(self):
        self.red('data-part="c"', "{{sheet:c}}", {}, SHEET)

    def test_unfilled_sheet_fails(self):
        self.red("填好的答案紙", "{{sheet:a}}", {}, SHEET.replace("2.262", "{{t}}"))


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "v.json").write_text(json.dumps({"t": "2.262"}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, template, *extra):
        (self.dir / "tpl.html").write_text(template, encoding="utf-8")
        return fill.main([str(self.dir / "v.json"), str(self.dir / "tpl.html"), "-o", str(self.dir / "out.html"), *extra])

    def test_writes_filled_page(self):
        self.assertEqual(self.run_cli("t = {{t}}"), 0)
        self.assertEqual((self.dir / "out.html").read_text(encoding="utf-8"), "t = 2.262")

    def test_writes_nothing_when_red(self):
        self.assertEqual(self.run_cli("F = {{f}}"), 1)
        self.assertFalse((self.dir / "out.html").exists())

    def test_sheet_option(self):
        (self.dir / "answer.html").write_text(SHEET, encoding="utf-8")
        self.assertEqual(self.run_cli("{{sheet:a}}", "--sheet", str(self.dir / "answer.html")), 0)
        self.assertEqual((self.dir / "out.html").read_text(encoding="utf-8"), "<p>t = 2.262</p>")


if __name__ == "__main__":
    unittest.main()
