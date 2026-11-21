"""crop.py：尋找文字座標、列出行級、畫座標格線、局部裁切加紅框與淡黃標色（不做原圖塗底嵌字）。

要 PyMuPDF 和 Pillow：uv run --no-project --with pymupdf --with pillow python -m unittest discover -s skills/tutor/tests
"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "crop.py"
spec = importlib.util.spec_from_file_location("crop", SCRIPT)
crop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crop)


class CropTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pdf = self.dir / "table.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=200)
        page.draw_rect(pymupdf.Rect(0, 0, 400, 200), color=None, fill=(1, 1, 1))
        page.insert_text((50, 80), "Decision rule: t = 2.262", fontsize=12)
        doc.save(self.pdf)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            crop.main(list(argv))
        return out.getvalue(), err.getvalue()

    def test_lines_lists_text_with_position_and_size(self):
        out, _ = self.run_cmd("lines", str(self.pdf), "1")
        line = [ln for ln in out.splitlines() if "Decision rule" in ln][0]
        x0, y0, x1, y1 = (int(v) for v in line.split()[0].split(","))
        self.assertTrue(48 <= x0 <= 52 and y0 < 80 < y1 and x1 > x0, line)
        self.assertIn("12.0pt", line)

    def test_find_locates_matching_text(self):
        out, _ = self.run_cmd("find", str(self.pdf), "1", "2.262")
        coords = [ln for ln in out.splitlines() if "," in ln]
        self.assertEqual(len(coords), 1)
        self.assertEqual(len(coords[0].split(",")), 4)

    def test_grid_writes_overlay_image(self):
        dest = self.dir / "grid.png"
        out, _ = self.run_cmd("grid", str(self.pdf), "1", str(dest))
        self.assertTrue(dest.is_file())
        self.assertIn("400 x 200 pt", out)

    def test_cut_clips_and_draws_red_box_and_yellow_mark(self):
        dest = self.dir / "cut.png"
        self.run_cmd(
            "cut", str(self.pdf), "1", str(dest),
            "--dpi", "72",
            "--clip", "40,50,240,120",
            "--box", "45,60,220,100",
            "--mark", "100,65,180,95",
        )
        with Image.open(dest) as raw:
            im = raw.convert("RGB")
        self.assertEqual(im.size, (200, 70))
        # 紅框左邊線 (x=45-40=5, y=80-50=30)
        r, g, b = im.getpixel((5, 30))
        self.assertTrue(r > 150 and g < 80 and b < 80, (r, g, b))
        # 淡黃標色空白處 (x=175-40=135, y=90-50=40)
        mr, mg, mb = im.getpixel((135, 40))
        self.assertTrue(mr > 230 and mg > 220 and mb < 210, (mr, mg, mb))

    def test_cut_supports_rotation(self):
        dest = self.dir / "rot.png"
        self.run_cmd("cut", str(self.pdf), "1", str(dest), "--dpi", "72", "--rotate", "90")
        with Image.open(dest) as im:
            self.assertEqual(im.size, (200, 400))

    def test_out_of_range_page_stops(self):
        with self.assertRaises(SystemExit):
            self.run_cmd("lines", str(self.pdf), "5")

    def test_pixel_translation_flag_removed(self):
        self.assertFalse(hasattr(crop, "translate"))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            crop.main(["cut", str(self.pdf), "1", str(self.dir / "x.png"), "--zh", "zh.json"])


if __name__ == "__main__":
    unittest.main()
