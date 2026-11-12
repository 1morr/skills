"""AGENTS.md 裡能用程式檢查的 repo 規則。

    python -m unittest discover -s tests

每條規則是一個 check_*(root) 函式，回傳違規清單。測試分兩種：
- RepoTest：這個 repo 現在每條都過。
- 其餘各 class：在暫存目錄造一個最小的 repo，證明違規會紅、無關的改動不紅。
只用標準函式庫。
"""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 模型可以自己觸發的 skill：加進來之前先看 AGENTS.md〈結構〉
MODEL_INVOKED = {"diff"}
# md 裡的路徑縮寫指到哪：值是相對 repo 根的路徑，{skill} 換成那份 md 所屬的 skill
SHORT = {"O": "orca", "P": "pages", "D": "skills/{skill}/scripts", "S": "skills/{skill}/scripts", "DIFF": "skills/diff"}
# 有 md 要檢查的目錄
DOC_DIRS = ("skills", "orca", "pages")

LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
SHORT_PATH = re.compile(r"<([A-Z]+)>/([A-Za-z0-9_./-]+)")
MANIFEST_NAME = re.compile(r"(?:^|；)\s*([a-z][a-z0-9-]*)：")
README_ROW = re.compile(r"^\|\s*\[([^\]]+)\]\(skills/([^/]+)/SKILL\.md\)", re.M)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def skills(root: Path) -> list:
    return sorted(p.parent.name for p in (root / "skills").glob("*/SKILL.md"))


def frontmatter(text: str) -> dict:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep and not key.startswith(" "):
            out[key.strip()] = value.strip()
    return out


def docs(root: Path):
    for d in DOC_DIRS:
        yield from sorted((root / d).rglob("*.md"))


def check_names(root: Path) -> list:
    out = []
    for name in skills(root):
        got = frontmatter(read(root / "skills" / name / "SKILL.md")).get("name")
        if got != name:
            out.append(f"skills/{name}/SKILL.md 的 name 是 {got!r}，要等於資料夾名")
    return out


def check_listed(root: Path) -> list:
    """每個 skill 都在 README 的表格和兩份 manifest 的 description 裡，而且那三處沒有多出來的名字。"""
    want = set(skills(root))
    out = []
    rows = README_ROW.findall(read(root / "README.md"))
    listed = {folder for _, folder in rows}
    out += [f"README 表格裡 [{label}] 連到 skills/{folder}/：名字要一樣" for label, folder in rows if label != folder]
    manifests = {
        ".claude-plugin/plugin.json": json.loads(read(root / ".claude-plugin/plugin.json"))["description"],
        ".claude-plugin/marketplace.json": json.loads(read(root / ".claude-plugin/marketplace.json"))["plugins"][0]["description"],
    }
    places = {"README.md 的表格": listed}
    places.update({f"{k} 的 description": set(MANIFEST_NAME.findall(v)) for k, v in manifests.items()})
    for where, got in places.items():
        out += [f"{where}少了 {n}" for n in sorted(want - got)]
        out += [f"{where}多了 {n}：skills/ 裡沒有這個 skill" for n in sorted(got - want)]
    return out


def check_paths(root: Path) -> list:
    """md 裡的相對連結和 <O>/…、<P>/… 這類縮寫路徑都指得到檔案。"""
    out = []
    for md in docs(root):
        text = read(md)
        rel = md.relative_to(root)
        skill = rel.parts[1] if rel.parts[0] == "skills" else ""
        for target in LINK.findall(text):
            if re.match(r"[a-z]+:", target):
                continue
            if not (md.parent / target).exists():
                out.append(f"{rel} 連到 {target}，沒有這個檔")
        for key, path in SHORT_PATH.findall(text):
            if key not in SHORT:
                continue
            path = path.rstrip("./")
            if not (root / SHORT[key].format(skill=skill) / path).exists():
                out.append(f"{rel} 寫了 <{key}>/{path}，{SHORT[key].format(skill=skill)}/ 底下沒有")
    return out


def check_no_cross_links(root: Path) -> list:
    return [f"{md.relative_to(root)} 有 ../：共用的檔放 orca/ 或 pages/，或用 Skill 工具載入對方"
            for md in docs(root) if "../" in read(md)]


def check_invocation(root: Path, allowed=frozenset(MODEL_INVOKED)) -> list:
    out = []
    for name in skills(root):
        fm = frontmatter(read(root / "skills" / name / "SKILL.md"))
        manual = fm.get("disable-model-invocation") == "true"
        if not manual and name not in allowed:
            out.append(f"{name} 沒有 disable-model-invocation: true，也不在 MODEL_INVOKED 裡")
        if manual and name in allowed:
            out.append(f"{name} 在 MODEL_INVOKED 裡，卻設了 disable-model-invocation")
    return out


def check_tested(root: Path) -> list:
    """有 Python 腳本的目錄都有 tests/，而且 CI 和 README 都跑它；orca 的腳本由 selftest.sh 測。"""
    ci = "\n".join(read(p) for p in sorted((root / ".github/workflows").glob("*.yml")))
    readme = read(root / "README.md")
    out = []
    dirs = [p.parent.parent for p in root.glob("skills/*/scripts/*.py")] + [p.parent.parent for p in root.glob("pages/scripts/*.py")]
    targets = sorted({f"{d.relative_to(root).as_posix()}/tests" for d in dirs}) + ["tests"]
    for t in targets:
        if not list((root / t).glob("test_*.py")):
            out.append(f"{t}/ 沒有 test_*.py")
        for where, text in (("CI", ci), ("README", readme)):
            if not re.search(rf"-s {re.escape(t)}(?![\w/-])", text):
                out.append(f"{where} 沒有跑 {t}")
    if list((root / "orca/scripts").glob("*.sh")):
        for where, text in (("CI", ci), ("README", readme)):
            if "orca/scripts/selftest.sh" not in text:
                out.append(f"{where} 沒有跑 orca/scripts/selftest.sh")
    return out


CHECKS = (check_names, check_listed, check_paths, check_no_cross_links, check_invocation, check_tested)


class RepoTest(unittest.TestCase):
    def test_this_repo_follows_every_rule(self):
        for check in CHECKS:
            with self.subTest(check.__name__):
                self.assertEqual(check(ROOT), [])


def write(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def sub(root: Path, rel: str, old: str, new: str):
    text = read(root / rel)
    assert old in text, (rel, old)
    write(root, rel, text.replace(old, new))


class Fixture(unittest.TestCase):
    """最小的合格 repo：diff（模型可觸發、有腳本）和 notes（手動、用 orca 與 pages）。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="repo-rules-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        r = self.root
        write(r, "skills/diff/SKILL.md", "---\nname: diff\ndescription: 對照頁。使用者要 diff 頁時用。\n---\n\n"
              "`<D>` 是腳本目錄。跑 `python <D>/diff.py a b`，細節見 [LOOK.md](LOOK.md)。\n")
        write(r, "skills/diff/LOOK.md", "# 外觀\n\n照 `<P>/TOKENS.md`。\n")
        write(r, "skills/diff/scripts/diff.py", "")
        write(r, "skills/diff/tests/test_diff.py", "")
        write(r, "skills/notes/SKILL.md", "---\nname: notes\ndescription: 記筆記\ndisable-model-invocation: true\n---\n\n"
              "先讀 `<O>/COORDINATOR.md`，再跑 `bash <O>/scripts/wait.sh <handle>`，寫到 `<批次目錄>/notes.md`。\n")
        write(r, "orca/COORDINATOR.md", "# 流程\n")
        write(r, "orca/scripts/wait.sh", "")
        write(r, "orca/scripts/selftest.sh", "")
        write(r, "pages/TOKENS.md", "# 配色\n")
        write(r, "tests/test_repo_rules.py", "")
        write(r, "README.md", "| Skill | 做什麼 |\n|---|---|\n| [diff](skills/diff/SKILL.md) | 對照 |\n| [notes](skills/notes/SKILL.md) | 筆記 |\n\n"
              "```\npython -m unittest discover -s skills/diff/tests\nbash orca/scripts/selftest.sh\npython -m unittest discover -s tests\n```\n")
        desc = "diff：對照頁；notes：記筆記。"
        write(r, ".claude-plugin/plugin.json", json.dumps({"name": "x", "description": desc}, ensure_ascii=False))
        write(r, ".claude-plugin/marketplace.json", json.dumps({"plugins": [{"name": "x", "description": desc}]}, ensure_ascii=False))
        write(r, ".github/workflows/test.yml", "steps:\n  - run: python -m unittest discover -s skills/diff/tests -v\n"
              "  - run: bash orca/scripts/selftest.sh\n  - run: python -m unittest discover -s tests -v\n")

    def clean(self, check, **kw):
        self.assertEqual(check(self.root, **kw), [])

    def red(self, check, **kw):
        self.assertNotEqual(check(self.root, **kw), [])

    def test_fixture_follows_every_rule(self):
        for check in CHECKS:
            with self.subTest(check.__name__):
                self.clean(check)


class NamesTest(Fixture):
    def test_name_differs_from_folder(self):
        sub(self.root, "skills/notes/SKILL.md", "name: notes", "name: note-taking")
        self.red(check_names)

    def test_name_missing(self):
        sub(self.root, "skills/notes/SKILL.md", "name: notes\n", "")
        self.red(check_names)

    def test_other_frontmatter_and_body_do_not_matter(self):
        sub(self.root, "skills/notes/SKILL.md", "description: 記筆記", "description: name: something-else\nargument-hint: \"[題目]\"")
        sub(self.root, "skills/notes/SKILL.md", "先讀", "name: body-text\n\n先讀")
        self.clean(check_names)


class ListedTest(Fixture):
    def test_missing_from_readme(self):
        sub(self.root, "README.md", "| [notes](skills/notes/SKILL.md) | 筆記 |\n", "")
        self.red(check_listed)

    def test_missing_from_each_manifest(self):
        for rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
            with self.subTest(rel):
                original = read(self.root / rel)
                sub(self.root, rel, "；notes：記筆記", "")
                self.red(check_listed)
                write(self.root, rel, original)

    def test_listed_skill_that_does_not_exist(self):
        sub(self.root, "README.md", "| [notes]", "| [gone](skills/gone/SKILL.md) | 沒了 |\n| [notes]")
        self.red(check_listed)

    def test_manifest_names_a_removed_skill(self):
        sub(self.root, ".claude-plugin/plugin.json", "diff：", "gone：沒了；diff：")
        self.red(check_listed)

    def test_readme_label_differs_from_folder(self):
        sub(self.root, "README.md", "[notes](skills/notes", "[note](skills/notes")
        self.red(check_listed)

    def test_wording_and_order_do_not_matter(self):
        sub(self.root, "README.md", "| 筆記 |", "| 換一種說法：可以有冒號 |")
        sub(self.root, ".claude-plugin/plugin.json", "diff：對照頁；notes：記筆記。", "notes：改寫過的說明；diff：也改寫了。")
        self.clean(check_listed)


class PathsTest(Fixture):
    def test_broken_markdown_link(self):
        sub(self.root, "skills/diff/SKILL.md", "[LOOK.md](LOOK.md)", "[LOOK.md](LOOKS.md)")
        self.red(check_paths)

    def test_script_missing_from_own_skill(self):
        sub(self.root, "skills/diff/SKILL.md", "<D>/diff.py", "<D>/compare.py")
        self.red(check_paths)

    def test_file_missing_from_shared_folders(self):
        for rel, old, new in (("skills/notes/SKILL.md", "<O>/scripts/wait.sh", "<O>/scripts/waitbg.sh"),
                              ("skills/diff/LOOK.md", "<P>/TOKENS.md", "<P>/COLORS.md")):
            with self.subTest(rel):
                original = read(self.root / rel)
                sub(self.root, rel, old, new)
                self.red(check_paths)
                write(self.root, rel, original)

    def test_placeholders_urls_and_anchors_do_not_matter(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "見 [文檔](https://example.com/x.md) 和 [下面](#流程)，存到 `<暫存>/out.json`、`<repo>/docs/x.md`。先讀")
        sub(self.root, "skills/diff/SKILL.md", "[LOOK.md](LOOK.md)", "[外觀](LOOK.md#token)")
        self.clean(check_paths)


class CrossLinksTest(Fixture):
    def test_link_into_another_skill(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "照 [LOOK.md](../diff/LOOK.md)。先讀")
        self.red(check_no_cross_links)

    def test_plain_path_into_another_skill(self):
        sub(self.root, "orca/COORDINATOR.md", "# 流程", "# 流程\n\n腳本在 `../skills/diff/scripts`。")
        self.red(check_no_cross_links)

    def test_naming_another_skill_is_fine(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "呼叫 Skill 工具載入 `diff`，省略的地方寫 `...`。先讀")
        self.clean(check_no_cross_links)


class InvocationTest(Fixture):
    def test_model_invoked_skill_not_on_the_list(self):
        sub(self.root, "skills/notes/SKILL.md", "disable-model-invocation: true\n", "")
        self.red(check_invocation)

    def test_flag_set_to_false(self):
        sub(self.root, "skills/notes/SKILL.md", "disable-model-invocation: true", "disable-model-invocation: false")
        self.red(check_invocation)

    def test_listed_skill_that_became_manual(self):
        sub(self.root, "skills/diff/SKILL.md", "---\n\n", "disable-model-invocation: true\n---\n\n")
        self.red(check_invocation)

    def test_the_list_decides(self):
        sub(self.root, "skills/notes/SKILL.md", "disable-model-invocation: true\n", "")
        self.clean(check_invocation, allowed=frozenset({"diff", "notes"}))

    def test_description_wording_does_not_matter(self):
        sub(self.root, "skills/notes/SKILL.md", "description: 記筆記", "description: 提到 disable-model-invocation 這個字也沒關係")
        self.clean(check_invocation)


class TestedTest(Fixture):
    def test_scripts_without_tests(self):
        shutil.rmtree(self.root / "skills/diff/tests")
        self.red(check_tested)

    def test_new_scripts_folder_needs_all_three(self):
        write(self.root, "pages/scripts/build.py", "")
        self.red(check_tested)
        write(self.root, "pages/tests/test_build.py", "")
        self.red(check_tested)
        sub(self.root, ".github/workflows/test.yml", "steps:\n", "steps:\n  - run: python -m unittest discover -s pages/tests\n")
        self.red(check_tested)
        sub(self.root, "README.md", "```\n", "```\npython -m unittest discover -s pages/tests\n")
        self.clean(check_tested)

    def test_ci_or_readme_stops_running_a_suite(self):
        for rel, old in ((".github/workflows/test.yml", "  - run: python -m unittest discover -s skills/diff/tests -v\n"),
                         ("README.md", "python -m unittest discover -s skills/diff/tests\n"),
                         (".github/workflows/test.yml", "  - run: bash orca/scripts/selftest.sh\n"),
                         (".github/workflows/test.yml", "  - run: python -m unittest discover -s tests -v\n")):
            with self.subTest(old.strip()):
                original = read(self.root / rel)
                sub(self.root, rel, old, "")
                self.red(check_tested)
                write(self.root, rel, original)

    def test_repo_suite_is_not_satisfied_by_a_longer_path(self):
        sub(self.root, ".github/workflows/test.yml", "  - run: python -m unittest discover -s tests -v\n", "")
        sub(self.root, "README.md", "python -m unittest discover -s tests\n", "")
        self.red(check_tested)

    def test_skill_without_scripts_needs_no_tests(self):
        write(self.root, "skills/notes/frame.md", "# 外框\n")
        sub(self.root, ".github/workflows/test.yml", "steps:", "name: test\nsteps:")
        self.clean(check_tested)


if __name__ == "__main__":
    unittest.main()
