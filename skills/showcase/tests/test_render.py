"""對一個用完即丟的 git repo 驗證渲染器的行為。

在 skill 目錄執行：python -m unittest discover -s tests
"""

import base64
import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "showcase.py"
spec = importlib.util.spec_from_file_location("showcase", SCRIPT)
showcase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(showcase)

# 1x1 透明 PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def run(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=repo, check=True, capture_output=True)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        run(self.repo, "init", "-q", "-b", "main")
        (self.repo / "app.js").write_text("function greet() {\n  return 'hi';\n}\n", encoding="utf-8")
        (self.repo / "old.txt").write_text("legacy\n", encoding="utf-8")
        run(self.repo, "add", ".")
        run(self.repo, "commit", "-q", "-m", "base")
        (self.repo / "app.js").write_text(
            "function greet(name) {\n  return '<script>alert(1)</script>' + name;\n}\n", encoding="utf-8")
        (self.repo / "old.txt").unlink()
        (self.repo / "gen").mkdir()
        (self.repo / "gen" / "a.g.js").write_text("a\n", encoding="utf-8")
        (self.repo / "gen" / "b.g.js").write_text("b\n", encoding="utf-8")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-q", "-m", "change")
        # 報告預設放在 repo 外
        self.outside = tempfile.TemporaryDirectory()
        self.out = Path(self.outside.name) / "t"
        self.out.mkdir()
        (self.out / "before.png").write_bytes(PNG)
        (self.out / "after.png").write_bytes(PNG)

    def tearDown(self):
        self.tmp.cleanup()
        self.outside.cleanup()

    def report(self, **over):
        r = {
            "title": "Greet by name",
            "lang": "en",
            "range": {"base": "HEAD~1", "head": "HEAD", "base_ref": "main"},
            "summary": "Greeting now uses the `name`.",
            "why": {"text": "Users asked.", "sources": ["#1"]},
            "files": {"app.js": "Takes a name.", "old.txt": "Unused.", "gen/*.g.js": "Generated."},
            "hunks": [{"file": "app.js", "match": "name", "note": "Adds the parameter."}],
            "evidence": {
                "level": "after",
                "why_not_higher": "base build broken",
                "items": [
                    {"kind": "compare", "caption": "Greeting", "before": "before.png", "after": "after.png"},
                    {"kind": "output", "caption": "CLI", "command": "node app.js", "before": "hi", "after": "hi bob"},
                ],
            },
            "try_it": ["Run `node app.js`"],
        }
        r.update(over)
        (self.out / "report.json").write_text(json.dumps(r), encoding="utf-8")
        return self.out / "report.json"

    def render(self, **over):
        return showcase.render(self.report(**over), self.repo, pr_md=True)

    def test_pr_markdown_only_when_asked(self):
        html_path, md_path, _ = showcase.render(self.report(), self.repo)
        self.assertTrue(html_path.exists())
        self.assertIsNone(md_path)
        self.assertFalse((self.out / "pr.md").exists())

    def test_report_outside_repo_writes_nothing_into_the_repo(self):
        self.render()
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo,
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(status, "")

    def test_renders_self_contained_html_with_escaped_diff(self):
        html_path, md_path, _ = self.render()
        page = html_path.read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", page)
        self.assertNotIn("<script>alert(1)", page)
        self.assertIn("&lt;script&gt;alert(1)", page)
        self.assertIsNone(re.search(r'(src|href)="(https?:)?//', page.replace('href="#', "")),
                          "page must not load external resources")
        self.assertIn('class="add"', page)

    def test_pr_markdown_has_no_images_but_keeps_text_evidence(self):
        _, md_path, _ = self.render()
        md = md_path.read_text(encoding="utf-8")
        self.assertNotIn("![", md)
        self.assertNotIn("<img", md)
        self.assertIn("hi bob", md)
        self.assertIn("```diff", md)

    def test_every_changed_file_needs_a_note(self):
        with self.assertRaisesRegex(showcase.ReportError, "no note in `files`: old.txt"):
            self.render(files={"app.js": "x", "gen/*.g.js": "y"})

    def test_note_for_unchanged_file_is_rejected(self):
        files = {"app.js": "x", "old.txt": "y", "gen/*.g.js": "z", "README.md": "never changed"}
        with self.assertRaisesRegex(showcase.ReportError, "matches no changed file: README.md"):
            self.render(files=files)

    def test_glob_note_groups_files(self):
        html_path, md_path, _ = self.render()
        self.assertIn("`gen/*.g.js` (2 files)", md_path.read_text(encoding="utf-8"))

    def test_hunk_selector_must_match(self):
        with self.assertRaisesRegex(showcase.ReportError, "matched nothing"):
            self.render(hunks=[{"file": "app.js", "match": "nonexistent", "note": ""}])

    def test_match_trims_to_matching_lines_with_context(self):
        lines = [f"line{i:02d}" for i in range(60)]
        lines[30] = "needle()"
        (self.repo / "big.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
        files = {"app.js": "a", "old.txt": "b", "gen/*.g.js": "c", "big.py": "New file."}
        _, md_path, _ = self.render(range={"base": "HEAD~1", "head": None}, files=files,
                                    hunks=[{"file": "big.py", "match": "needle", "context": 2, "note": "x"}])
        md = md_path.read_text(encoding="utf-8")
        for kept in ("+line28", "+needle()", "+line32"):
            self.assertIn(kept, md)
        for dropped in ("+line27", "+line33", "+line00"):
            self.assertNotIn(dropped, md)
        self.assertEqual(md.count(showcase.GAP), 2)

    def test_two_entries_selecting_one_hunk_warn(self):
        _, _, warnings = self.render(hunks=[{"file": "app.js", "match": "name", "note": "a"},
                                            {"file": "app.js", "match": "script", "note": "b"}])
        self.assertTrue(any("select the same hunk" in w for w in warnings), warnings)

    def test_figures_and_hunks_have_ids(self):
        html_path, _, _ = self.render()
        page = html_path.read_text(encoding="utf-8")
        for anchor in ('id="ev-1"', 'id="ev-2"', 'id="hunk-1"'):
            self.assertIn(anchor, page)

    def test_level_below_before_after_needs_reason(self):
        ev = {"level": "tests", "items": []}
        with self.assertRaisesRegex(showcase.ReportError, "why_not_higher"):
            self.render(evidence=ev)

    def test_missing_evidence_image_is_rejected(self):
        ev = {"level": "before-after", "items": [{"kind": "image", "caption": "x", "after": "nope.png"}]}
        with self.assertRaisesRegex(showcase.ReportError, "image not found"):
            self.render(evidence=ev)

    def test_working_tree_includes_untracked_files_but_not_the_report(self):
        # 使用者把報告放進 repo 時，報告本身不能被當成改動
        inside = self.repo / "reports" / "t"
        inside.mkdir(parents=True)
        for f in self.out.iterdir():
            (inside / f.name).write_bytes(f.read_bytes())
        self.out = inside
        (self.repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        files = {"app.js": "a", "old.txt": "b", "gen/*.g.js": "c", "new.py": "New script."}
        html_path, _, _ = self.render(
            range={"base": "HEAD~1", "head": None}, files=files,
            hunks=[{"file": "new.py", "note": "Whole file."}])
        page = html_path.read_text(encoding="utf-8")
        self.assertIn("print(&#x27;new&#x27;)", page)
        self.assertNotIn("report.json", page)
        self.assertNotIn("before.png", page)

    def test_missing_motivation_is_flagged_not_invented(self):
        _, md_path, _ = self.render(why={"text": "", "sources": []})
        self.assertIn(showcase.LABELS["en"]["awaiting"], md_path.read_text(encoding="utf-8"))

    def test_branch_name_shown_only_when_it_points_at_the_commit(self):
        _, md_path, warnings = self.render(range={"base": "HEAD~1", "head": "HEAD", "base_ref": "main", "head_ref": "main"})
        md = md_path.read_text(encoding="utf-8")
        self.assertIn("→ main @", md)
        self.assertNotIn("`main @", md)
        self.assertTrue(any("base_ref `main` does not point" in w for w in warnings))

    def test_personal_paths_and_secrets_warn(self):
        for leaked in ("C:\\Users\\alice\\proj\\x.log", "/home/alice/x", "api_key=abcd1234efgh5678",
                       "Authorization: Bearer abcdefghijklmnop1234"):
            with self.subTest(leaked=leaked):
                ev = {"level": "tests", "why_not_higher": "n/a",
                      "items": [{"kind": "output", "caption": "run", "after": f"ok\n{leaked}\n"}]}
                _, _, warnings = self.render(evidence=ev)
                self.assertTrue(any("scrub" in w for w in warnings), warnings)

    def test_placeholders_and_plain_text_do_not_warn(self):
        ev = {"level": "tests", "why_not_higher": "n/a",
              "items": [{"kind": "output", "caption": "run",
                         "after": "token=REDACTED password: ******** /usr/local/bin users/home ok"}]}
        _, _, warnings = self.render(evidence=ev)
        self.assertFalse(any("scrub" in w for w in warnings), warnings)

    def test_zh_hant_labels(self):
        html_path, _, _ = self.render(lang="zh-Hant")
        self.assertIn("關鍵改動", html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
