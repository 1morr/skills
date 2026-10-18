"""The skill must stay repo-agnostic: no names, paths or commands from the
repos it was developed against, and no machine-specific paths.

DEV_SET lists the development repos. Add a repo here when you start testing
the skill against it, so its vocabulary cannot leak into the instructions.
"""

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DEV_SET = ["MediaServer", "Berth", "FMP", "fmp-test", "verify-on-device", "verify-legacy-on-device", "trellis", "orca"]
PATTERNS = [
    re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, DEV_SET)) + r")(?![\w-])", re.IGNORECASE),
    re.compile(r"\b[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
    re.compile(r"(?<![\w.])/(home|Users)/[\w.-]+"),
]


def violations(text):
    return [m.group(0) for p in PATTERNS for m in p.finditer(text)]


def skill_files():
    """Everything an agent reads or runs, excluding these tests."""
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
                         "open /home/alice/repo", "Use the FMP dev flavor."):
            with self.subTest(injected=injected):
                self.assertNotEqual(violations(sample + "\n" + injected), [])

    def test_unrelated_rewording_stays_clean(self):
        sample = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        reworded = re.sub(r"\s+", " ", sample).replace("## ", "### ").upper()
        self.assertEqual(violations(reworded), [])
        # Words that merely contain a dev-set name are not violations.
        self.assertEqual(violations("orchestrate the berths; fmpeg-like; trellised; /usr/local/bin"), [])


if __name__ == "__main__":
    unittest.main()
