"""deck.py：整份課件變成課件欄的圖、翻譯圖和清單。

要 PyMuPDF 和 Pillow：uv run --no-project --with pymupdf --with pillow python -m unittest discover -s tests
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
from PIL import Image, ImageChops

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deck.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("deck", SCRIPT)
deck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deck)

TITLE = "Stationary series"
BODY = "The data must be roughly horizontal."


class Deck(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
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

    def test_first_run_writes_a_picture_per_page_and_the_text_to_translate(self):
        self.run_deck()
        self.assertEqual(self.read("zh.json"), {TITLE: "", BODY: ""})
        self.assertEqual(self.read("slides.json"), {"decks": [{"id": "L1", "pages": [
            {"n": 1, "src": "L1-01.png", "zh": None, "w": 1000, "h": 400},
            {"n": 2, "src": "L1-02.png", "zh": None, "w": 1000, "h": 400}]}]})
        with Image.open(self.out / "L1-01.png") as im:
            self.assertEqual(im.size, (1000, 400))

    def test_filled_text_gives_a_translated_picture_for_that_page_only(self):
        self.run_deck()
        self.fill(**{TITLE: "平穩序列"})
        self.run_deck()
        pages = self.read("slides.json")["decks"][0]["pages"]
        self.assertEqual([p["zh"] for p in pages], ["L1-01.zh.png", None])
        en, zh = (Image.open(self.out / n).convert("RGB") for n in ("L1-01.png", "L1-01.zh.png"))
        diff = ImageChops.difference(en, zh)

        def most(box):  # 存檔時各自縮成 64 色，沒動到的地方也會差幾個色階
            return max(hi for _, hi in diff.crop(box).getextrema())

        self.assertGreater(most((100, 60, 600, 140)), 150)  # 標題換掉了
        self.assertLess(most((100, 200, 900, 260)), 60)  # 沒填譯文的那一塊原樣

    def test_rerun_keeps_what_was_filled(self):
        self.run_deck()
        self.fill(**{TITLE: "平穩序列", "old slide text": "舊的"})
        self.run_deck()
        self.assertEqual(self.read("zh.json"), {TITLE: "平穩序列", BODY: "", "old slide text": "舊的"})

    def test_summary_counts_pages_and_empty_entries(self):
        out, _ = self.run_deck()
        self.assertIn("L1：2 頁，0 頁有翻譯圖", out)
        self.assertIn("2 塊原文，2 塊沒有譯文", out)

    def blocked_page(self):
        """一頁三塊字：Beside 的右邊緊貼著一張小圖，Alone 的右邊是空的，Far 離左邊界很遠。"""
        photo = self.dir / "p.png"
        Image.new("RGB", (40, 40), (200, 30, 30)).save(photo)
        page = pymupdf.open().new_page(width=500, height=200)
        page.insert_text((40, 60), "Beside", fontsize=12)
        page.insert_image(pymupdf.Rect(200, 45, 225, 70), filename=str(photo))
        page.insert_text((40, 120), "Alone", fontsize=12)
        page.insert_text((300, 170), "Far", fontsize=12)
        return page

    def test_long_translation_runs_into_the_empty_space_on_its_right(self):
        self.run_deck()
        self.fill(**{TITLE: "平穩序列（stationary series）是沒有趨勢的時間序列"})
        out, _ = self.run_deck()
        en, zh = (Image.open(self.out / n).convert("L") for n in ("L1-01.png", "L1-01.zh.png"))
        beyond = (540, 90, 740, 125)  # 原文標題右邊的空白：原圖沒有字，翻譯圖寫到這裡
        self.assertGreater(en.crop(beyond).getextrema()[0], 200)
        self.assertLess(zh.crop(beyond).getextrema()[0], 120)
        self.assertNotIn("字縮到", out)

    def test_text_stops_before_whatever_sits_on_its_right(self):
        page = self.blocked_page()
        boxes = deck.obstacles(page)
        beside, alone, far = (pymupdf.Rect(b["rect"]) for b in deck.blocks(page))
        self.assertAlmostEqual(deck.right_edge(page, boxes, beside), 200 - 6)  # 右邊那張圖的前面
        self.assertEqual(deck.right_edge(page, boxes, alone), 500 - 40)  # 右邊留的邊和左邊一樣寬
        self.assertEqual(deck.right_edge(page, boxes, far), 500 - 50)  # 左邊界離得遠的，右邊最多留頁寬的一成

    def test_pages_whose_text_shrank_a_lot_are_named(self):
        self.blocked_page().parent.save(self.dir / "tight.pdf")
        self.run_deck(f"T={self.dir / 'tight.pdf'}")
        self.fill(Beside="這一塊的譯文比原來的位置長很多很多很多很多很多很多很多很多很多，右邊又有一張圖擋著")
        out, _ = self.run_deck(f"T={self.dir / 'tight.pdf'}")
        self.assertRegex(out, r"T p\.1：字縮到 \d+%")

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
