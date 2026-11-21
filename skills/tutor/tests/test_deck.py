"""deck.py：整份課件切成單套課件原圖，抽出文字塊寫進 slides.json 與去重的 zh.json（不產生第二套修圖檔）。

要 PyMuPDF 和 Pillow：uv run --no-project --with pymupdf --with pillow python -m unittest discover -s skills/tutor/tests
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deck.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("deck", SCRIPT)
deck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deck)

TITLE = "Stationary series"
BODY = "The data must be roughly horizontal."


class Deck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pdf = self.dir / "slides.pdf"
        self.out = self.dir / "slides"
        doc = pymupdf.open()
        page = doc.new_page(width=500, height=200)
        page.insert_text((72, 60), TITLE, fontsize=20)
        page.insert_text((72, 120), BODY, fontsize=12)
        page.insert_text((450, 190), "12", fontsize=9)  # 頁碼：沒有字母
        page.insert_text((400, 40), "Week 3", fontsize=9, morph=(pymupdf.Point(400, 40), pymupdf.Matrix(30)))  # 斜放的緞帶
        page = doc.new_page(width=500, height=200)
        page.insert_text((72, 60), "1868 – 1910", fontsize=20)
        doc.save(self.pdf)

    def tearDown(self):
        self.tmp.cleanup()

    def run_deck(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            deck.main([str(self.out), *(args or (f"L1={self.pdf}",))])
        return out.getvalue(), err.getvalue()

    def read(self, name):
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def fill(self, **zh):
        todo = self.read("zh.json")
        todo.update(zh)
        (self.out / "zh.json").write_text(json.dumps(todo, ensure_ascii=False), encoding="utf-8")

    def test_single_run_writes_one_original_image_per_page_and_text_blocks(self):
        out, _ = self.run_deck()
        self.assertEqual(self.read("zh.json"), {TITLE: "", BODY: ""})
        self.assertEqual(self.read("slides.json"), {"decks": [{"id": "L1", "pages": [
            {"n": 1, "src": "L1-01.png", "w": 1000, "h": 400, "blocks": [TITLE, BODY]},
            {"n": 2, "src": "L1-02.png", "w": 1000, "h": 400, "blocks": []},
        ]}]})
        with Image.open(self.out / "L1-01.png") as im:
            self.assertEqual(im.size, (1000, 400))
        self.assertIn("L1：2 頁，0 頁有譯文", out)
        self.assertIn("2 塊原文，2 塊沒有譯文", out)

    def test_filled_zh_never_creates_duplicate_translated_raster_images(self):
        self.run_deck()
        self.fill(**{TITLE: "平穩序列（stationary series）"})
        out, _ = self.run_deck()
        self.assertFalse((self.out / "L1-01.zh.png").exists())
        self.assertEqual(self.read("zh.json"), {TITLE: "平穩序列（stationary series）", BODY: ""})
        self.assertIn("L1：2 頁，1 頁有譯文", out)

    def test_rerun_keeps_existing_translations_and_skip_flags(self):
        self.run_deck()
        manifest = self.read("slides.json")
        manifest["decks"][0]["pages"][1]["skip"] = True
        manifest["skip"] = ["L1 p.2"]
        (self.out / "slides.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        self.fill(**{TITLE: "平穩序列", "old slide text": "舊的"})
        self.run_deck()
        self.assertEqual(self.read("zh.json"), {TITLE: "平穩序列", BODY: "", "old slide text": "舊的"})
        rebuilt = self.read("slides.json")
        self.assertTrue(rebuilt["decks"][0]["pages"][1].get("skip"))
        self.assertEqual(rebuilt.get("skip"), ["L1 p.2"])

    def test_page_with_a_photo_is_saved_as_jpeg(self):
        photo = self.dir / "p.png"
        Image.new("RGB", (40, 40), (200, 30, 30)).save(photo)
        doc = pymupdf.open()
        doc.new_page(width=500, height=200).insert_image(pymupdf.Rect(10, 10, 110, 110), filename=str(photo))
        doc.save(self.dir / "photo.pdf")
        self.run_deck(f"P={self.dir / 'photo.pdf'}")
        self.assertEqual(self.read("slides.json")["decks"][0]["pages"][0]["src"], "P-01.jpg")

    def test_two_decks_share_one_translation_file(self):
        self.run_deck(f"A={self.pdf}", f"B={self.pdf}")
        self.assertEqual([d["id"] for d in self.read("slides.json")["decks"]], ["A", "B"])
        self.assertEqual(len(self.read("zh.json")), 2)

    def test_bad_arguments_stop(self):
        for args in ((f"L 1={self.pdf}",), ("L1=missing.pdf",), (f"L1={self.pdf}", f"L1={self.pdf}"), ("L1",)):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                self.run_deck(*args)


if __name__ == "__main__":
    unittest.main()
