"""skill 必須保持與 repo 無關：不能出現開發時拿來試的 repo 的名稱、路徑或指令，
也不能有特定機器的路徑。

DEV_SET 列出開發用的 repo。開始拿某個 repo 試 skill 時把它加進來，
它的詞彙就漏不進指示裡。
"""

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DEV_SET = ["MediaServer", "Berth", "FMP", "fmp-test", "verify-on-device", "verify-legacy-on-device", "trellis", "orca"]
PATTERNS = [
    # 邊界只看 ASCII：中文字緊貼著名稱（「用FMP的」）時也要抓到
    re.compile(r"(?<![A-Za-z0-9_-])(" + "|".join(map(re.escape, DEV_SET)) + r")(?![A-Za-z0-9_-])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_.])/(home|Users)/[\w.-]+"),
]


def violations(text):
    return [m.group(0) for p in PATTERNS for m in p.finditer(text)]


def skill_files():
    """agent 會讀或執行的每個檔案，不含這些測試。"""
    return [p for p in SKILL_DIR.rglob("*")
            if p.is_file() and "tests" not in p.relative_to(SKILL_DIR).parts
            and "__pycache__" not in p.parts and p.suffix in {".md", ".py", ".json", ".yaml", ".yml", ".html", ".css", ".js"}]


class GenericTest(unittest.TestCase):
    def test_skill_files_are_repo_agnostic(self):
        files = skill_files()
        self.assertTrue(any(p.name == "SKILL.md" for p in files))
        for p in files:
            with self.subTest(file=str(p.relative_to(SKILL_DIR))):
                self.assertEqual(violations(p.read_text(encoding="utf-8")), [])

    def test_detects_injected_repo_vocabulary(self):
        sample = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for injected in ("Run `berth bench` first.", "See verify-on-device.", "cd C:\\Users\\dev\\proj",
                         "open /home/alice/repo", "Use the FMP dev flavor.", "先跑berth bench再截圖",
                         "用FMP的dev flavor", "路徑在C:\\Users\\dev下"):
            with self.subTest(injected=injected):
                self.assertNotEqual(violations(sample + "\n" + injected), [])

    def test_unrelated_rewording_stays_clean(self):
        sample = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        reworded = re.sub(r"\s+", " ", sample).replace("## ", "### ").upper()
        self.assertEqual(violations(reworded), [])
        # 只是包含開發集名稱的字不算違規。
        self.assertEqual(violations("orchestrate the berths; fmpeg-like; trellised; /usr/local/bin"), [])


if __name__ == "__main__":
    unittest.main()
