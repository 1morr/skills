"""範本和它們要配合的東西對得上。只在 plugin 裡跑，不複製進專案。

    python -m unittest discover -s skills/project-init/tests

- 填好的骨架通得過 check_docs.py。
- 範本的票改成 done、勾完驗收、留了 Session 紀錄，通得過協調者的 orca/scripts/merge-ticket.sh 與 check_docs.py；沒做完的被擋。
- check_commit_msg.py 和 merge-ticket.sh 收同一組 commit type。
- 範本裡沒有留給模型刪、卻不在清單上的佔位。
- docs/agents/ 的三個範本和這台機器裝的 mattpocock-skills 種子範本沒有走樣（沒裝就跳過）。
"""

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[1]
TEMPLATES = SKILL / "templates"
MERGE = ROOT / "orca/scripts/merge-ticket.sh"
# SKILL.md〈寫骨架〉列的佔位
PLACEHOLDERS = {"PROJECT": "Demo", "ONE_LINE": "示範專案。", "DATE": "2026-01-02", "MAIN_BRANCH": "main"}


def load(name):
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check_docs, check_commit_msg = load("check_docs"), load("check_commit_msg")


def fill(name: str) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: PLACEHOLDERS[m.group(1)], text)


class PlaceholderTest(unittest.TestCase):
    def test_every_placeholder_is_one_the_skill_fills(self):
        for p in sorted(TEMPLATES.iterdir()):
            for name in re.findall(r"\{\{(\w+)\}\}", p.read_text(encoding="utf-8")):
                self.assertIn(name, PLACEHOLDERS, f"{p.name} 用了 {{{{{name}}}}}，SKILL.md 和這裡的清單都要有")

    def test_skill_lists_the_same_placeholders_and_templates(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for name in PLACEHOLDERS:
            self.assertIn("{{%s}}" % name, skill)
        for p in TEMPLATES.iterdir():
            self.assertIn(f"`{p.name}`", skill, f"SKILL.md〈寫骨架〉沒有列 {p.name}")


class SkeletonTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="project-init-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def test_fresh_skeleton_passes_check_docs(self):
        self.write("docs/progress.md", fill("progress.md"))
        self.write("docs/roadmap.md", fill("roadmap.md"))
        self.assertEqual(check_docs.run(self.root), [])

    def test_skeleton_with_a_first_milestone_passes(self):
        self.write("docs/progress.md", fill("progress.md"))
        roadmap = fill("roadmap.md")
        self.assertIn("| 未開工。", roadmap)
        self.write("docs/roadmap.md", roadmap.replace("| 未開工。", "| 進行中。"))
        self.write(".scratch/m0/spec.md", "# M0\n\n## 目標\n\n## 範圍\n\n## 共同規則\n\n## 驗收\n\n### 使用者試\n\n無。\n\n## 票序\n")
        self.write(".scratch/m0/issues/01-gates.md", fill("ticket.md"))
        self.write(".scratch/m0/issues/02-m0-acceptance.md", fill("ticket.md"))
        self.assertEqual(check_docs.run(self.root), [])

    def test_filled_templates_pass_the_size_and_wording_checks(self):
        for name, rel in (("instructions.md", "AGENTS.md"), ("design-brief.md", check_docs.BRIEF), ("plan.md", check_docs.PLAN),
                          ("progress.md", check_docs.PROGRESS), ("roadmap.md", check_docs.ROADMAP)):
            self.write(rel, fill(name))
        self.assertEqual(check_docs.run(self.root), [])

    def test_instruction_sections_the_other_skills_read(self):
        text = fill("instructions.md")
        for needle in ("docs/progress.md", "Status:", "/implement <票路徑>", "/1morr:checkpoint", "/1morr:ticket-coordinator",
                       "完成標準", "NN-<里程碑>-acceptance", check_docs.SESSION_NOTE):
            self.assertIn(needle, text)


class MilestoneDocTest(unittest.TestCase):
    def test_instructions_point_at_it_and_it_names_what_the_check_enforces(self):
        self.assertIn("docs/agents/milestone.md", fill("instructions.md"))
        text = fill("milestone.md")
        for needle in ("/to-tickets docs/roadmap.md 拆 <里程碑> 的票", "NN-<里程碑>-acceptance", check_docs.USER_TRIAL,
                       check_docs.WAITING + "試用", *check_docs.SPEC_SECTIONS):
            self.assertIn(needle, text)


class CommitTypesTest(unittest.TestCase):
    def test_same_types_as_merge_ticket(self):
        line = next(l for l in MERGE.read_text(encoding="utf-8").split("\n") if l.startswith("CC="))
        types = re.search(r"\^\(([a-z|]+)\)", line).group(1).split("|")
        self.assertEqual(tuple(types), check_commit_msg.TYPES)


# templates/ 的檔名 → 它改自 setup-matt-pocock-skills 的哪個種子範本（出處與授權見 NOTICE.md）
SEEDS = {"issue-tracker.md": "issue-tracker-local.md", "triage-labels.md": "triage-labels.md", "domain.md": "domain.md"}
CONVENTIONS = re.compile(r"(^## Conventions[ \t]*\n)(.*?)(?=^## )", re.S | re.M)
# 種子範本裡我們改掉的那一句
PUBLISH = ("`.scratch/<feature-slug>/` (creating", "`.scratch/<milestone>/issues/` (creating")


def outside_conventions(text: str) -> str:
    """去掉〈Conventions〉底下的清單：那一段是我們自己的，其餘要和種子範本相同。"""
    return CONVENTIONS.sub(lambda m: m.group(1), text, count=1)


def installed_seed():
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    found = [d for d in config.glob("plugins/cache/*/mattpocock-skills/*/skills/*/setup-matt-pocock-skills")
             if all((d / s).is_file() for s in SEEDS.values())]
    return max(found, key=lambda d: d.stat().st_mtime) if found else None


class AgentDocsTest(unittest.TestCase):
    def test_issue_tracker_states_what_the_other_skills_rely_on(self):
        text = (TEMPLATES / "issue-tracker.md").read_text(encoding="utf-8")
        for needle in ("`.scratch/<milestone>/issues/<NN>-<slug>.md`", "`<NN>-<milestone>-acceptance.md`", "`Status: done`",
                       "`Blocked by:`", "`## Comments`", "docs/agents/ticket-template.md", "目標, 範圍, 共同規則, 驗收, 票序",
                       "docs/agents/milestone.md"):
            self.assertIn(needle, text)

    def test_only_the_list_is_ignored_when_comparing(self):
        ours = "# T\n\n## Conventions\n\n- 我們的\n\n## Other\n\n原文\n"
        self.assertEqual(outside_conventions(ours), outside_conventions(ours.replace("- 我們的", "- theirs\n- more")))
        self.assertNotEqual(outside_conventions(ours), outside_conventions(ours.replace("原文", "改過")))
        self.assertNotEqual(outside_conventions(ours), outside_conventions(ours.replace("## Other", "## Other\n\n## New section")))

    @unittest.skipUnless(installed_seed(), "這台機器沒有裝 mattpocock-skills")
    def test_copies_match_the_installed_seed(self):
        seed = installed_seed()
        for ours, theirs in SEEDS.items():
            with self.subTest(ours):
                mine = (TEMPLATES / ours).read_text(encoding="utf-8")
                upstream = (seed / theirs).read_text(encoding="utf-8")
                if ours == "issue-tracker.md":
                    mine, upstream = outside_conventions(mine), outside_conventions(upstream.replace(*PUBLISH))
                self.assertEqual(mine, upstream, f"{seed / theirs} 和 templates/{ours} 不一樣了：把上游的改動同步過來，並更新 NOTICE.md 的版本")


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "要 git 和 bash")
class MergeTicketTest(unittest.TestCase):
    """用範本的票開一個真的 repo，跑協調者合併用的腳本。"""

    TICKET = ".scratch/m0/issues/01-gates.md"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="project-init-merge-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.repo, self.work = self.root / "repo", self.root / "t01"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "docs").mkdir()
        (self.repo / "docs/progress.md").write_text(fill("progress.md"), encoding="utf-8")
        (self.repo / "docs/roadmap.md").write_text(fill("roadmap.md").replace("| 未開工。", "| 進行中。"), encoding="utf-8")
        ticket = self.repo / self.TICKET
        ticket.parent.mkdir(parents=True)
        ticket.write_text(fill("ticket.md"), encoding="utf-8")
        (ticket.parent / "02-m0-acceptance.md").write_text(fill("ticket.md"), encoding="utf-8")
        (self.repo / ".scratch/m0/spec.md").write_text("# M0\n\n## 目標\n\n## 範圍\n\n## 共同規則\n\n## 驗收\n\n### 使用者試\n\n無。\n\n## 票序\n", encoding="utf-8")
        self.commit(self.repo, "docs: scaffold")
        self.git(self.repo, "worktree", "add", "-q", "-b", "t01", str(self.work))

    def git(self, cwd, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        return subprocess.run(["git", "-C", str(cwd), "-c", "core.hooksPath=/dev/null", *args], env=env, capture_output=True, text=True, check=True)

    def commit(self, cwd, message):
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-q", "-m", message)

    def merge(self):
        env = dict(os.environ, REQUIRE="", BASE="main", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        return subprocess.run(["bash", str(MERGE), str(self.repo), str(self.work), self.TICKET, "merge: ticket 01 gates"],
                              env=env, capture_output=True, text=True)

    def finish(self, status="done", check=True, note=True, message="feat: add the check gate"):
        t = self.work / self.TICKET
        text = t.read_text(encoding="utf-8").replace("Status: ready-for-agent", f"Status: {status}")
        text = text.replace("- [ ]", "- [x]") if check else text
        t.write_text(text + ("\nSession 紀錄：閘門就位。\n" if note else ""), encoding="utf-8")
        self.commit(self.work, message)

    def test_finished_ticket_merges(self):
        self.finish()
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("merge: ticket 01 gates", self.git(self.repo, "log", "-1", "--format=%s").stdout)
        self.assertEqual(check_docs.run(self.repo), [])

    def test_ticket_without_a_session_note_fails_the_docs_check(self):
        self.finish(note=False)
        self.assertTrue(any("做完的票" in p for p in check_docs.run(self.work)), check_docs.run(self.work))

    def test_unfinished_tickets_are_held_back(self):
        for name, kw in (("status", {"status": "ready-for-agent"}), ("checkbox", {"check": False}),
                         ("subject", {"message": "Add the check gate"})):
            with self.subTest(name):
                self.setUp()
                self.finish(**kw)
                r = self.merge()
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("NOT READY", r.stdout)


if __name__ == "__main__":
    unittest.main()
