"""write_agent_docs.py 的測試。只在 plugin 裡跑，不複製進專案。

    python -m unittest discover -s skills/project-init/tests
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "write_agent_docs.py"
spec = importlib.util.spec_from_file_location("write_agent_docs", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SEED_TRACKER = """# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## Wayfinding operations

- **Map**: `.scratch/<effort>/map.md`
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-docs-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "project"
        self.project.mkdir()

    def seed(self, where: Path, tracker=SEED_TRACKER, skip=()):
        where.mkdir(parents=True, exist_ok=True)
        files = {"issue-tracker-local.md": tracker, "triage-labels.md": "# Triage Labels\n", "domain.md": "# Domain Docs\n"}
        for name, text in files.items():
            if name not in skip:
                (where / name).write_text(text, encoding="utf-8")
        return where

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = m.main([str(a) for a in argv])
        return rc, out.getvalue(), err.getvalue()

    def agents(self, name):
        return (self.project / "docs/agents" / name).read_text(encoding="utf-8")


class WriteTest(Base):
    def test_writes_three_files_from_the_seed(self):
        source = self.seed(self.tmp / "seed")
        rc, out, _ = self.run_main(self.project, "--source", source)
        self.assertEqual(rc, 0)
        self.assertEqual(out.count("寫了："), 3)
        self.assertIn(str(source), out)
        self.assertEqual(self.agents("triage-labels.md"), "# Triage Labels\n")
        self.assertEqual(self.agents("domain.md"), "# Domain Docs\n")

    def test_conventions_become_the_milestone_ones(self):
        self.run_main(self.project, "--source", self.seed(self.tmp / "seed"))
        text = self.agents("issue-tracker.md")
        self.assertNotIn("One feature per directory", text)
        self.assertNotIn("<!--", text)
        for needle in ("`.scratch/<milestone>/`", "-acceptance.md", "`Status: done`", "docs/agents/ticket-template.md"):
            self.assertIn(needle, text)
        self.assertEqual(text.count("## Conventions"), 1)

    def test_everything_outside_the_list_is_kept(self):
        self.run_main(self.project, "--source", self.seed(self.tmp / "seed"))
        text = self.agents("issue-tracker.md")
        self.assertTrue(text.startswith("# Issue tracker: Local Markdown\n\nIssues and specs for this repo live"))
        self.assertIn("## Wayfinding operations\n\n- **Map**: `.scratch/<effort>/map.md`\n", text)
        self.assertIn("Create a new file under `.scratch/<milestone>/issues/` (creating the directory if needed).", text)
        self.assertRegex(text, r"`## Comments` heading\n\n## When a skill says")

    def test_existing_files_are_left_alone(self):
        (self.project / "docs/agents").mkdir(parents=True)
        (self.project / "docs/agents/domain.md").write_text("我自己寫的", encoding="utf-8")
        rc, out, _ = self.run_main(self.project, "--source", self.seed(self.tmp / "seed"))
        self.assertEqual(rc, 0)
        self.assertIn("已存在，沒動：docs/agents/domain.md", out)
        self.assertEqual(self.agents("domain.md"), "我自己寫的")
        self.assertIn("-acceptance.md", self.agents("issue-tracker.md"))

    def test_seed_without_conventions_writes_nothing(self):
        source = self.seed(self.tmp / "seed", tracker=SEED_TRACKER.replace("## Conventions", "## Layout"))
        rc, _, err = self.run_main(self.project, "--source", source)
        self.assertEqual(rc, 2)
        self.assertIn("格式變了", err)
        self.assertFalse((self.project / "docs").exists())

    def test_incomplete_seed_writes_nothing(self):
        source = self.seed(self.tmp / "seed", skip=("domain.md",))
        rc, _, err = self.run_main(self.project, "--source", source)
        self.assertEqual(rc, 2)
        self.assertFalse((self.project / "docs").exists())

    def test_wording_changes_in_the_seed_do_not_matter(self):
        tracker = SEED_TRACKER.replace("Issues and specs for this repo live", "Tickets live").replace("## Wayfinding operations", "## Other")
        rc, _, _ = self.run_main(self.project, "--source", self.seed(self.tmp / "seed", tracker=tracker))
        self.assertEqual(rc, 0)
        self.assertIn("-acceptance.md", self.agents("issue-tracker.md"))


class LocateTest(Base):
    def setUp(self):
        super().setUp()
        self.config, self.home = self.tmp / "config", self.tmp / "home"
        (self.config / "plugins").mkdir(parents=True)
        self.home.mkdir()

    def record(self, *entries):
        data = {"version": 2, "plugins": {"mattpocock-skills@some-marketplace": list(entries), "other@x": [{"installPath": "/nowhere"}]}}
        (self.config / "plugins/installed_plugins.json").write_text(json.dumps(data), encoding="utf-8")

    def locate(self):
        return m.locate(self.config, self.home)

    def test_nothing_installed(self):
        self.assertIsNone(self.locate())

    def test_install_record_newest_first(self):
        old = self.seed(self.tmp / "v1/skills/engineering/setup-matt-pocock-skills")
        new = self.seed(self.tmp / "v2/skills/engineering/setup-matt-pocock-skills")
        self.record({"installPath": str(self.tmp / "v1"), "lastUpdated": "2026-01-01T00:00:00Z"},
                    {"installPath": str(self.tmp / "v2"), "lastUpdated": "2026-06-01T00:00:00Z"})
        self.assertEqual(self.locate(), new)
        shutil.rmtree(new)
        self.assertEqual(self.locate(), old)

    def test_skill_in_another_bucket_is_found(self):
        moved = self.seed(self.tmp / "v1/skills/setup/setup-matt-pocock-skills")
        self.record({"installPath": str(self.tmp / "v1"), "lastUpdated": "2026-01-01T00:00:00Z"})
        self.assertEqual(self.locate(), moved)

    def test_cache_without_a_readable_record(self):
        cached = self.seed(self.config / "plugins/cache/some-marketplace/mattpocock-skills/1.0.0/skills/engineering/setup-matt-pocock-skills")
        self.assertEqual(self.locate(), cached)
        (self.config / "plugins/installed_plugins.json").write_text("not json", encoding="utf-8")
        self.assertEqual(self.locate(), cached)

    def test_linked_skills(self):
        linked = self.seed(self.home / ".agents/skills/setup-matt-pocock-skills")
        self.assertEqual(self.locate(), linked)
        preferred = self.seed(self.config / "skills/setup-matt-pocock-skills")
        self.assertEqual(self.locate(), preferred)

    def test_folder_missing_a_seed_is_skipped(self):
        self.seed(self.config / "skills/setup-matt-pocock-skills", skip=("triage-labels.md",))
        self.assertIsNone(self.locate())

    def test_another_plugin_with_the_same_skill_name_is_ignored(self):
        self.seed(self.config / "plugins/cache/x/other-plugin/1.0.0/skills/engineering/setup-matt-pocock-skills")
        self.assertIsNone(self.locate())

    def test_main_reports_when_nothing_is_installed(self):
        old = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.config)
        self.addCleanup(lambda: os.environ.pop("CLAUDE_CONFIG_DIR") if old is None else os.environ.__setitem__("CLAUDE_CONFIG_DIR", old))
        real_home = Path.home
        Path.home = staticmethod(lambda: self.home)
        self.addCleanup(setattr, Path, "home", real_home)
        rc, _, err = self.run_main(self.project)
        self.assertEqual(rc, 2)
        self.assertIn("找不到", err)
        self.assertFalse((self.project / "docs").exists())


@unittest.skipUnless(m.locate(), "這台機器沒有裝 mattpocock-skills")
class InstalledSeedTest(Base):
    """裝著的那一版種子範本還是這支腳本認得的樣子。"""

    def test_installed_seed_can_be_written(self):
        rc, out, err = self.run_main(self.project)
        self.assertEqual(rc, 0, err)
        text = self.agents("issue-tracker.md")
        self.assertIn("-acceptance.md", text)
        self.assertIn("`.scratch/<milestone>/issues/` (creating", text)
        self.assertNotIn("<feature-slug>", text.split("## When a skill says")[0])


if __name__ == "__main__":
    unittest.main()
