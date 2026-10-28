"""crop.py 的翻譯圖（cut --zh）：原文換成中文，其他地方和原圖一樣。

要 PyMuPDF 和 Pillow：uv run --no-project --with pymupdf --with pillow python -m unittest discover -s tests
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "crop.py"
spec = importlib.util.spec_from_file_location("crop", SCRIPT)
crop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crop)

TEXT_RECT = [70, 85, 420, 125]  # 英文段落所在的範圍
CLIP = "60,20,440,170"
DPI = 72  # 1pt = 1px，座標好對


class ZhCut(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.pdf = self.dir / "slides.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=500, height=200)
        page.draw_rect(pymupdf.Rect(0, 0, 500, 200), color=None, fill=(1, 1, 0.8))  # 淡黃底
        page.draw_rect(pymupdf.Rect(70, 30, 200, 60), color=(0, 0, 1), fill=(0, 0, 1))  # 段落上面的藍色方塊
        page.insert_text((72, 100), "Stationary series is a time series without trend.", fontsize=12)
        page.insert_text((72, 118), "The data must be roughly horizontal.", fontsize=12)
        doc.save(self.pdf)

    def zh(self, data, name="zh.json"):
        path = self.dir / name
        path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def cut(self, *extra):
        out = self.dir / "c.png"
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            crop.main(["cut", str(self.pdf), "1", str(out), "--clip", CLIP, "--dpi", str(DPI), *extra])
        return out, self.dir / "c.zh.png", err.getvalue()

    def pixels(self, path):
        return Image.open(path).convert("RGB")

    @staticmethod
    def max_diff(a, b, box):
        """兩張圖在 box 裡最大的色差。存檔時各自縮成 64 色，沒動到的地方也會差幾個色階。"""
        return max(hi for _, hi in ImageChops.difference(a.crop(box), b.crop(box)).getextrema())

    def test_text_replaced_and_rest_unchanged(self):
        en, zh, _ = self.cut("--zh", self.zh({"1": [{"rect": TEXT_RECT, "zh": "平穩序列是沒有趨勢的時間序列。"}]}))
        a, b = self.pixels(en), self.pixels(zh)
        self.assertEqual(a.size, b.size)
        x0, y0 = 60, 20  # CLIP 的左上角
        inside = (TEXT_RECT[0] - x0, TEXT_RECT[1] - y0, TEXT_RECT[2] - x0, TEXT_RECT[3] - y0)
        self.assertGreater(self.max_diff(a, b, inside), 100)
        above = (0, 0, a.size[0], TEXT_RECT[1] - y0 - 2)  # 藍色方塊那一帶不能被動到
        self.assertLess(self.max_diff(a, b, above), 12)

    def test_cover_uses_background_color(self):
        _, zh, _ = self.cut("--zh", self.zh({"1": [{"rect": TEXT_RECT, "zh": "短"}]}))
        corner = self.pixels(zh).getpixel((TEXT_RECT[2] - 60 - 3, TEXT_RECT[3] - 20 - 3))
        self.assertGreater(corner[0], 200)
        self.assertLess(corner[2], 235)  # 淡黃，不是白

    def test_red_box_on_both(self):
        en, zh, _ = self.cut("--box", "65,80,425,130", "--zh", self.zh({"1": [{"rect": TEXT_RECT, "zh": "譯文"}]}))
        for path in (en, zh):
            r, g, b = self.pixels(path).getpixel((65 - 60, 100 - 20))
            self.assertTrue(r > 150 and g < 100 and b < 100, (path.name, r, g, b))

    def test_too_long_warns(self):
        _, _, err = self.cut("--zh", self.zh({"1": [{"rect": TEXT_RECT, "zh": "很長的譯文" * 80}]}))
        self.assertIn("放不下", err)

    def test_short_text_does_not_warn(self):
        _, _, err = self.cut("--zh", self.zh({"1": [{"rect": TEXT_RECT, "zh": "平穩序列"}]}))
        self.assertNotIn("放不下", err)

    def test_missing_page_stops(self):
        with self.assertRaises(SystemExit):
            self.cut("--zh", self.zh({"2": [{"rect": TEXT_RECT, "zh": "別頁"}]}))

    def test_item_without_zh_stops(self):
        with self.assertRaises(SystemExit):
            self.cut("--zh", self.zh({"1": [{"rect": TEXT_RECT, "zh": " "}]}))

    def test_rotate_with_zh_stops(self):
        with self.assertRaises(SystemExit):
            self.cut("--rotate", "90", "--zh", self.zh({"1": [{"rect": TEXT_RECT, "zh": "譯文"}]}))

    def test_without_zh_writes_one_image(self):
        en, zh, _ = self.cut()
        self.assertTrue(en.exists())
        self.assertFalse(zh.exists())

    def test_formatting_variants_pass(self):
        variants = [
            '{\n  "1": [\n    {"zh": "平穩序列", "rect": [70.0, 85.0, 420.0, 125.0]}\n  ]\n}\n',
            json.dumps({"1": [{"rect": TEXT_RECT, "zh": "<b>平穩</b>序列", "size": 11, "css": "b {color: red}"}],
                        "3": [{"rect": [0, 0, 1, 1], "zh": "別頁"}]}, ensure_ascii=False),
        ]
        for i, data in enumerate(variants):
            with self.subTest(i=i):
                _, zh, err = self.cut("--zh", self.zh(data, f"v{i}.json"))
                self.assertTrue(zh.exists())
                self.assertNotIn("放不下", err)


class Lines(unittest.TestCase):
    def test_lists_text_with_position(self):
        with tempfile.TemporaryDirectory() as d:
            pdf = Path(d) / "a.pdf"
            doc = pymupdf.open()
            doc.new_page(width=300, height=200).insert_text((50, 80), "Decision rule", fontsize=12)
            doc.save(pdf)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                crop.main(["lines", str(pdf), "1"])
        line = [ln for ln in out.getvalue().splitlines() if "Decision rule" in ln][0]
        x0, y0, x1, y1 = (int(v) for v in line.split()[0].split(","))
        self.assertTrue(48 <= x0 <= 52 and y0 < 80 < y1, line)
        self.assertIn("12.0pt", line)


if __name__ == "__main__":
    unittest.main()
