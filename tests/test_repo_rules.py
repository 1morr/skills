"""AGENTS.md 裡能用程式檢查的 repo 規則。

    python -m unittest discover -s tests

每條規則是一個 check_*(root) 函式，回傳違規清單；它的 docstring 就是那條規則，AGENTS.md 指到這裡、不另抄一份。測試分兩種：
- RepoTest：這個 repo 現在每條都過。
- 其餘各 class：在暫存目錄造一個最小的 repo，證明違規會紅、無關的改動不紅。
只用標準函式庫。
"""

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 模型可以自己觸發的 skill：加進來之前先看 AGENTS.md〈結構〉
MODEL_INVOKED = {"diff"}
# 過渡期 md 裡的路徑縮寫指到哪：值是相對 repo 根的路徑，{skill} 換成那份 md 所屬的 skill
SHORT = {"O": "orca", "P": "pages", "S": "skills/{skill}/scripts", "T": "skills/{skill}/templates"}
# 有 md 要檢查的目錄
DOC_DIRS = ("skills", "orca", "pages")

LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
SHORT_PATH = re.compile(r"<([A-Z]+)>/([A-Za-z0-9_./-]+)")
README_ROW = re.compile(r"^\|\s*\[([^\]]+)\]\(skills/([^/]+)/SKILL\.md\)", re.M)
REL_UP = re.compile(r"(?<![A-Za-z0-9_.])((?:[A-Za-z0-9_-]+/)*(?:\.\./)+[A-Za-z0-9_./-]*)")
DOUBLE = '"' * 3


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
        if (root / d).is_dir():
            yield from sorted((root / d).rglob("*.md"))


def check_names(root: Path) -> list:
    """SKILL.md 的 name 等於資料夾名。"""
    out = []
    for name in skills(root):
        got = frontmatter(read(root / "skills" / name / "SKILL.md")).get("name")
        if got != name:
            out.append(f"skills/{name}/SKILL.md 的 name 是 {got!r}，要等於資料夾名")
    return out


def check_listed(root: Path) -> list:
    """每個 skill 都在 README 的表格裡，表格沒有多出來的名字，連結文字等於資料夾名。"""
    want = set(skills(root))
    out = []
    rows = README_ROW.findall(read(root / "README.md"))
    listed = {folder for _, folder in rows}
    out += [f"README 表格裡 [{label}] 連到 skills/{folder}/：名字要一樣" for label, folder in rows if label != folder]
    out += [f"README.md 的表格少了 {n}" for n in sorted(want - listed)]
    out += [f"README.md 的表格多了 {n}：skills/ 裡沒有這個 skill" for n in sorted(listed - want)]
    return out


def check_paths(root: Path) -> list:
    """md 裡的標準相對連結與過渡期縮寫路徑（<O>/…、<P>/… 等）都指得到檔案。"""
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


def _allowed_up_target(root: Path, md: Path, raw: str) -> bool:
    rel = md.relative_to(root)
    raw_clean = raw.rstrip(".")
    if not raw_clean:
        return False
    norm = Path(os.path.normpath(md.parent / raw_clean))
    try:
        target = norm.relative_to(root)
    except ValueError:
        return False
    if not target.parts:
        return False
    if rel.parts[0] == "skills" and len(rel.parts) >= 2:
        own_skill = rel.parts[1]
        return target.parts[:2] == ("skills", own_skill) or target.parts[0] == "pages"
    return target.parts[0] == rel.parts[0]


def check_no_cross_links(root: Path) -> list:
    """禁止 skill 連往其他 skill（如 ../<other-skill>），但允許用標準相對路徑 ../../pages/ 連往根目錄共用層。"""
    out = []
    for md in docs(root):
        if "templates" in md.relative_to(root).parts:
            continue
        bad = [m.group(1) for m in REL_UP.finditer(read(md)) if not _allowed_up_target(root, md, m.group(1))]
        if bad:
            shown = "、".join(dict.fromkeys(bad))
            out.append(f"{md.relative_to(root)} 有跨目錄路徑 {shown}：skill 之間不互連，僅允許連往自身或 pages/ 共用層")
    return out


def _openai_allow_implicit(yaml_path: Path):
    """讀取 agents/openai.yaml 中 policy.allow_implicit_invocation 的字串值；未設時回傳 None。"""
    in_policy = False
    for raw in read(yaml_path).split("\n"):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            in_policy = line.strip() == "policy:"
            continue
        if in_policy:
            k, sep, v = line.strip().partition(":")
            if sep and k.strip() == "allow_implicit_invocation":
                return v.strip().strip("\"'")
    return None


def check_invocation(root: Path, allowed=frozenset(MODEL_INVOKED)) -> list:
    """沒設 disable-model-invocation: true 的 skill 恰好是 MODEL_INVOKED 裡那幾個；設了的必具備 agents/openai.yaml 且含 allow_implicit_invocation: false。"""
    out = []
    for name in skills(root):
        skill_dir = root / "skills" / name
        fm = frontmatter(read(skill_dir / "SKILL.md"))
        manual = fm.get("disable-model-invocation") == "true"
        openai_yaml = skill_dir / "agents/openai.yaml"
        if not manual and name not in allowed:
            out.append(f"{name} 沒有 disable-model-invocation: true，也不在 MODEL_INVOKED 裡")
        if manual and name in allowed:
            out.append(f"{name} 在 MODEL_INVOKED 裡，卻設了 disable-model-invocation")
        if manual:
            if not openai_yaml.is_file():
                out.append(f"{name} 設了 disable-model-invocation: true，但缺 skills/{name}/agents/openai.yaml")
            elif _openai_allow_implicit(openai_yaml) != "false":
                out.append(f"skills/{name}/agents/openai.yaml 要在 policy 底下設 allow_implicit_invocation: false")
        elif openai_yaml.is_file() and _openai_allow_implicit(openai_yaml) == "false":
            out.append(f"{name} 在 MODEL_INVOKED 裡，skills/{name}/agents/openai.yaml 卻設了 allow_implicit_invocation: false")
    return out


def check_tested(root: Path) -> list:
    """有 Python 腳本的目錄都有 tests/test_*.py，而且在 CI .github/workflows/*.yml 執行；orca 的腳本由 selftest.sh 測。"""
    ci = "\n".join(read(p) for p in sorted((root / ".github/workflows").glob("*.yml")))
    out = []
    dirs = [p.parent.parent for p in root.glob("skills/*/scripts/*.py")] + [p.parent.parent for p in root.glob("pages/scripts/*.py")]
    targets = sorted({f"{d.relative_to(root).as_posix()}/tests" for d in dirs}) + ["tests"]
    for t in targets:
        if not list((root / t).glob("test_*.py")):
            out.append(f"{t}/ 沒有 test_*.py")
        if not re.search(rf"-s {re.escape(t)}(?![\w/-])", ci):
            out.append(f"CI 沒有跑 {t}")
    if (root / "orca/scripts").is_dir() and list((root / "orca/scripts").glob("*.sh")):
        if "orca/scripts/selftest.sh" not in ci:
            out.append("CI 沒有跑 orca/scripts/selftest.sh")
    return out


FORBIDDEN_VARS = re.compile(r"\$\{CLAUDE_[A-Z0-9_]*\}?|\$ARGUMENTS\b")


def check_no_claude_vars(root: Path) -> list:
    """SKILL.md 與附屬 md 不寫 ${CLAUDE_SKILL_DIR}、${CLAUDE_PLUGIN_ROOT} 或 $ARGUMENTS：改用相對本檔的標準路徑與自然語言說明參數。"""
    out = []
    for md in docs(root):
        found = sorted(set(FORBIDDEN_VARS.findall(read(md))))
        if found:
            out.append(f"{md.relative_to(root)} 寫了 {'、'.join(found)}：跨 harness 不會替換，改用相對路徑")
    return out


CLAUDE_ONLY_WORDING = re.compile(r"\bAskUserQuestion\b|\bmodel:\s*[\"']?(?:opus|sonnet)\b", re.I)


def check_portable_wording(root: Path) -> list:
    """md 不寫綁定單一 harness 的工具名與模型欄位（AskUserQuestion、model: \"opus\"、model: \"sonnet\"）。"""
    out = []
    for md in docs(root):
        found = sorted(set(CLAUDE_ONLY_WORDING.findall(read(md))))
        if found:
            out.append(f"{md.relative_to(root)} 寫了綁定單一 harness 的 {'、'.join(found)}")
    return out


BARE_VAR_THEN_CJK = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7f]")
GNU_ONLY = re.compile(r"\bstat -c\b|\btouch -d\b|\bsed -i\b")


def shell_scripts(root: Path) -> list:
    orca_sh = list((root / "orca").rglob("*.sh")) if (root / "orca").is_dir() else []
    return sorted(orca_sh + list((root / "skills").rglob("*.sh")))


def check_shell_portable(root: Path) -> list:
    """shell 腳本要在 macOS 內建的 bash 3.2 跑：變數緊貼中文要加大括號，不用 GNU 專屬的參數。註解行不查。"""
    out = []
    for sh in shell_scripts(root):
        for n, line in enumerate(read(sh).split("\n"), 1):
            if line.lstrip().startswith("#"):
                continue
            where = f"{sh.relative_to(root)}:{n}"
            if BARE_VAR_THEN_CJK.search(line):
                out.append(f"{where} 變數後面緊貼中文：寫成 ${{var}}，bash 3.2 會把中文吃進變數名")
            if GNU_ONLY.search(line):
                out.append(f"{where} 用了 GNU 專屬的 stat -c / touch -d / sed -i，macOS 沒有")
    return out


def check_manifests_match(root: Path) -> list:
    """plugin.json 和 marketplace.json 的 description 相同。"""
    a = json.loads(read(root / ".claude-plugin/plugin.json"))["description"]
    b = json.loads(read(root / ".claude-plugin/marketplace.json"))["plugins"][0]["description"]
    return [] if a == b else ["plugin.json 和 marketplace.json 的 description 不一樣"]


# 反引號裡以 open 開頭的指令（macOS）；內文裡的英文字 open 不算
OPENS_FOR_USER = re.compile(r"xdg-open|orca tab create|`open\s[^`]*`")


def check_no_opening_for_user(root: Path) -> list:
    """skill 不替使用者開瀏覽器或分頁（`open …`、xdg-open、orca tab create）：交付照 pages/HANDOFF.md。"""
    return [f"{md.relative_to(root)} 叫執行者替使用者開瀏覽器或分頁：改照 pages/HANDOFF.md 交付"
            for md in docs(root) if OPENS_FOR_USER.search(read(md))]


CW_PART_SNIPPET = re.compile(r"`(<div\b[^`\n]*\bdata-part=[^`\n]*)`")


def check_coursework_tutor_contract(root: Path) -> list:
    """當 skills/coursework/SKILL.md 含有 data-part= 範例時，能被 skills/tutor/scripts/fill.py 的 PART 解析。"""
    cw = root / "skills/coursework/SKILL.md"
    fill_py = root / "skills/tutor/scripts/fill.py"
    if not (cw.is_file() and fill_py.is_file()):
        return []
    snippets = CW_PART_SNIPPET.findall(read(cw))
    if not snippets:
        return []
    ns = {}
    exec(compile(read(fill_py), str(fill_py), "exec"), ns)
    part_re = ns.get("PART")
    out = []
    for snippet in snippets:
        if part_re is None or not part_re.search(snippet):
            out.append(f"skills/coursework/SKILL.md 的 `{snippet}` 無法被 skills/tutor/scripts/fill.py 的 PART 解析")
    return out


CHECKS = (check_names, check_listed, check_paths, check_no_cross_links, check_invocation, check_tested,
          check_no_claude_vars, check_portable_wording, check_shell_portable, check_manifests_match,
          check_no_opening_for_user, check_coursework_tutor_contract)


class RepoTest(unittest.TestCase):
    def test_this_repo_follows_every_rule(self):
        for check in CHECKS:
            with self.subTest(check.__name__):
                self.assertEqual(check(ROOT), [])

    def test_every_rule_states_itself(self):
        for check in CHECKS:
            with self.subTest(check.__name__):
                self.assertTrue((check.__doc__ or "").strip(), "docstring 寫這條規則：AGENTS.md 不另抄")


def write(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def sub(root: Path, rel: str, old: str, new: str):
    text = read(root / rel)
    assert old in text, (rel, old)
    write(root, rel, text.replace(old, new))


class Fixture(unittest.TestCase):
    """最小的合格 repo：diff（模型可觸發、有腳本）和 notes（手動、配 openai.yaml）。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="repo-rules-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        r = self.root
        write(r, "skills/diff/SKILL.md", "---\nname: diff\ndescription: 對照頁。使用者要 diff 頁時用。\n---\n\n"
              "跑 `python scripts/diff.py a b`，細節見 [LOOK.md](LOOK.md)。\n")
        write(r, "skills/diff/LOOK.md", "# 外觀\n\n照 [TOKENS.md](../../pages/TOKENS.md)。\n")
        write(r, "skills/diff/scripts/diff.py", DOUBLE + "比對兩個版本。\n" + DOUBLE + "\n")
        write(r, "skills/diff/tests/test_diff.py", "")
        write(r, "skills/notes/SKILL.md", "---\nname: notes\ndescription: 記筆記\ndisable-model-invocation: true\n---\n\n"
              "先讀 `<O>/COORDINATOR.md`，再跑 `bash <O>/scripts/wait.sh <handle>`，寫到 `<批次目錄>/notes.md`。\n")
        write(r, "skills/notes/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        write(r, "orca/COORDINATOR.md", "# 流程\n")
        write(r, "orca/scripts/wait.sh", "# 用法：bash wait.sh <handle>\necho \"${H}沒有回應\"\n")
        write(r, "orca/scripts/selftest.sh", "# 用法：bash selftest.sh\n")
        write(r, "pages/TOKENS.md", "# 配色\n")
        write(r, "tests/test_repo_rules.py", "")
        write(r, "README.md", "| Skill | 做什麼 |\n|---|---|\n| [diff](skills/diff/SKILL.md) | 對照 |\n| [notes](skills/notes/SKILL.md) | 筆記 |\n")
        desc = "示範用的 skills。"
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

    def test_listed_skill_that_does_not_exist(self):
        sub(self.root, "README.md", "| [notes]", "| [gone](skills/gone/SKILL.md) | 沒了 |\n| [notes]")
        self.red(check_listed)

    def test_readme_label_differs_from_folder(self):
        sub(self.root, "README.md", "[notes](skills/notes", "[note](skills/notes")
        self.red(check_listed)

    def test_wording_and_order_do_not_matter(self):
        sub(self.root, "README.md", "| 筆記 |", "| 換一種說法：可以有冒號 |")
        sub(self.root, ".claude-plugin/plugin.json", "示範用的 skills。", "只提到 diff 的一句話。")
        self.clean(check_listed)


class PathsTest(Fixture):
    def test_broken_markdown_link(self):
        sub(self.root, "skills/diff/SKILL.md", "[LOOK.md](LOOK.md)", "[LOOK.md](LOOKS.md)")
        self.red(check_paths)

    def test_broken_relative_link_to_pages(self):
        sub(self.root, "skills/diff/LOOK.md", "../../pages/TOKENS.md", "../../pages/COLORS.md")
        self.red(check_paths)

    def test_legacy_shorthand_missing_target(self):
        sub(self.root, "skills/notes/SKILL.md", "<O>/scripts/wait.sh", "<O>/scripts/waitbg.sh")
        self.red(check_paths)

    def test_placeholders_urls_and_anchors_do_not_matter(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "見 [文檔](https://example.com/x.md) 和 [下面](#流程)，存到 `<暫存>/out.json`、`<repo>/docs/x.md`。先讀")
        sub(self.root, "skills/diff/SKILL.md", "[LOOK.md](LOOK.md)", "[外觀](LOOK.md#token)")
        self.clean(check_paths)


class CrossLinksTest(Fixture):
    def test_link_into_another_skill(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "照 [LOOK.md](../diff/LOOK.md)。先讀")
        self.red(check_no_cross_links)

    def test_detour_path_into_another_skill(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "照 `../../skills/diff/LOOK.md`。先讀")
        self.red(check_no_cross_links)

    def test_plain_path_from_shared_into_skill(self):
        sub(self.root, "orca/COORDINATOR.md", "# 流程", "# 流程\n\n腳本在 `../skills/diff/scripts`。")
        self.red(check_no_cross_links)

    def test_relative_path_to_shared_pages_and_own_skill_is_allowed(self):
        write(self.root, "skills/notes/sub/step.md", "見 [SKILL](../SKILL.md) 與 `../../../pages/TOKENS.md`。\n")
        sub(self.root, "skills/notes/SKILL.md", "先讀", "照 `../../pages/TOKENS.md`；載入 `diff` skill，省略寫 `...` 或 `.../x`。先讀")
        self.clean(check_no_cross_links)


class InvocationTest(Fixture):
    def test_model_invoked_skill_not_on_the_list(self):
        sub(self.root, "skills/notes/SKILL.md", "disable-model-invocation: true\n", "")
        (self.root / "skills/notes/agents/openai.yaml").unlink()
        self.red(check_invocation)

    def test_flag_set_to_false(self):
        sub(self.root, "skills/notes/SKILL.md", "disable-model-invocation: true", "disable-model-invocation: false")
        self.red(check_invocation)

    def test_listed_skill_that_became_manual(self):
        sub(self.root, "skills/diff/SKILL.md", "---\n\n", "disable-model-invocation: true\n---\n\n")
        write(self.root, "skills/diff/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        self.red(check_invocation)

    def test_manual_skill_missing_openai_yaml(self):
        (self.root / "skills/notes/agents/openai.yaml").unlink()
        self.red(check_invocation)

    def test_manual_skill_with_wrong_openai_policy(self):
        for bad in ("policy:\n  allow_implicit_invocation: true\n", "allow_implicit_invocation: false\n", "interface:\n  display_name: Notes\n"):
            with self.subTest(bad=bad.strip()):
                write(self.root, "skills/notes/agents/openai.yaml", bad)
                self.red(check_invocation)

    def test_model_invoked_skill_blocking_implicit_in_openai_yaml_fails(self):
        write(self.root, "skills/diff/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        self.red(check_invocation)

    def test_the_list_decides_and_extra_openai_keys_are_fine(self):
        write(self.root, "skills/notes/agents/openai.yaml",
              "interface:\n  display_name: Notes\npolicy:\n  # 手動觸發\n  allow_implicit_invocation: false\n")
        self.clean(check_invocation)
        sub(self.root, "skills/notes/SKILL.md", "disable-model-invocation: true\n", "")
        (self.root / "skills/notes/agents/openai.yaml").unlink()
        self.clean(check_invocation, allowed=frozenset({"diff", "notes"}))

    def test_description_wording_does_not_matter(self):
        sub(self.root, "skills/notes/SKILL.md", "description: 記筆記", "description: 提到 disable-model-invocation 這個字也沒關係")
        self.clean(check_invocation)


class TestedTest(Fixture):
    def test_scripts_without_tests(self):
        shutil.rmtree(self.root / "skills/diff/tests")
        self.red(check_tested)

    def test_new_scripts_folder_needs_tests_and_ci(self):
        write(self.root, "pages/scripts/overflow.py", DOUBLE + "量溢出。" + DOUBLE + "\n")
        self.red(check_tested)
        write(self.root, "pages/tests/test_overflow.py", "")
        self.red(check_tested)
        sub(self.root, ".github/workflows/test.yml", "steps:\n", "steps:\n  - run: python -m unittest discover -s pages/tests\n")
        self.clean(check_tested)

    def test_ci_stops_running_a_suite(self):
        for old in ("  - run: python -m unittest discover -s skills/diff/tests -v\n",
                    "  - run: bash orca/scripts/selftest.sh\n",
                    "  - run: python -m unittest discover -s tests -v\n"):
            with self.subTest(old.strip()):
                original = read(self.root / ".github/workflows/test.yml")
                sub(self.root, ".github/workflows/test.yml", old, "")
                self.red(check_tested)
                write(self.root, ".github/workflows/test.yml", original)

    def test_repo_suite_is_not_satisfied_by_a_longer_path(self):
        sub(self.root, ".github/workflows/test.yml", "  - run: python -m unittest discover -s tests -v\n", "")
        self.red(check_tested)

    def test_readme_command_formatting_is_not_locked(self):
        write(self.root, "README.md", "| Skill | 做什麼 |\n|---|---|\n| [diff](skills/diff/SKILL.md) | 對照 |\n| [notes](skills/notes/SKILL.md) | 筆記 |\n\n測試照 CI 跑。\n")
        self.clean(check_tested)

    def test_skill_without_scripts_needs_no_tests(self):
        write(self.root, "skills/notes/frame.md", "# 外框\n")
        sub(self.root, ".github/workflows/test.yml", "steps:", "name: test\nsteps:")
        self.clean(check_tested)


class NoClaudeVarsTest(Fixture):
    def test_claude_skill_dir_in_skill_md_or_companion(self):
        for rel in ("skills/diff/SKILL.md", "skills/diff/LOOK.md"):
            with self.subTest(rel):
                original = read(self.root / rel)
                write(self.root, rel, original + "\n腳本在 `${CLAUDE_SKILL_DIR}/scripts`。\n")
                self.red(check_no_claude_vars)
                write(self.root, rel, original)

    def test_claude_plugin_root_in_skill_or_shared_file(self):
        for rel in ("skills/notes/SKILL.md", "orca/COORDINATOR.md"):
            with self.subTest(rel):
                original = read(self.root / rel)
                write(self.root, rel, original + "\n路徑在 `${CLAUDE_PLUGIN_ROOT}/orca`。\n")
                self.red(check_no_claude_vars)
                write(self.root, rel, original)

    def test_literal_arguments_var_forbidden(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "參數：$ARGUMENTS。先讀")
        self.red(check_no_claude_vars)

    def test_standard_shell_env_vars_are_fine(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "可用 `SKILLS_ROOT`、`$HOME`、`${XDG_STATE_HOME:-$HOME/.local/state}`。先讀")
        self.clean(check_no_claude_vars)


class PortableWordingTest(Fixture):
    def test_ask_user_question_is_forbidden(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "用 `AskUserQuestion` 問使用者。先讀")
        self.red(check_portable_wording)

    def test_hardcoded_claude_model_fields_are_forbidden(self):
        for snippet in ('model: "opus"', 'model: "sonnet"', "model: 'opus'", "model: sonnet"):
            with self.subTest(snippet):
                original = read(self.root / "skills/notes/SKILL.md")
                sub(self.root, "skills/notes/SKILL.md", "先讀", f"開子代理（{snippet}）。先讀")
                self.red(check_portable_wording)
                write(self.root, "skills/notes/SKILL.md", original)

    def test_portable_tier_descriptions_are_fine(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀",
            "向使用者提問（有互動提問工具就用它）；開高階推理子代理（如 Opus / Pro 級）與快速子代理（如 Sonnet / Flash 級），傳 `--model <模型>`。先讀")
        self.clean(check_portable_wording)


class ShellPortableTest(Fixture):
    SH = "orca/scripts/wait.sh"

    def test_bare_variable_followed_by_cjk(self):
        sub(self.root, self.SH, "${H}沒有回應", "$H沒有回應")
        self.red(check_shell_portable)

    def test_gnu_only_flags(self):
        for line in ("stat -c %Y f", "touch -d '-5 minutes' f", "sed -i s/a/b/ f"):
            with self.subTest(line):
                original = read(self.root / self.SH)
                write(self.root, self.SH, original + line + "\n")
                self.red(check_shell_portable)
                write(self.root, self.SH, original)

    def test_comments_braces_and_ascii_do_not_matter(self):
        sub(self.root, self.SH, "echo", "# 存到 $LOG（預設在家目錄），GNU 的 touch -d 在 macOS 不認\n"
            "stat -f %m \"$H\"; sed -e s/a/b/ f; echo \"$H: ${H}號\"\necho")
        self.clean(check_shell_portable)

    def test_scripts_inside_a_skill_are_checked_too(self):
        write(self.root, "skills/notes/scripts/run.sh", "echo \"$H沒有\"\n")
        self.red(check_shell_portable)


class ManifestsMatchTest(Fixture):
    def test_one_manifest_reworded(self):
        sub(self.root, ".claude-plugin/plugin.json", "示範用", "展示用")
        self.red(check_manifests_match)

    def test_both_reworded_and_other_keys_do_not_matter(self):
        for rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
            sub(self.root, rel, "示範用", "展示用")
        sub(self.root, ".claude-plugin/plugin.json", '"name": "x"', '"name": "another"')
        self.clean(check_manifests_match)


class NoOpeningForUserTest(Fixture):
    def test_opening_the_default_browser(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "用預設瀏覽器打開（Linux `xdg-open`）。先讀")
        self.red(check_no_opening_for_user)

    def test_opening_an_orca_tab(self):
        sub(self.root, "pages/TOKENS.md", "# 配色", "# 配色\n\n`orca tab create --url <網址> --json`。")
        self.red(check_no_opening_for_user)

    def test_opening_with_the_macos_command(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "做完跑 `open page.html`。先讀")
        self.red(check_no_opening_for_user)

    def test_checking_with_browser_automation_is_fine(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "用瀏覽器自動化工具打開頁面截圖，再在對話給網址；`orca terminal create` 照用；"
            "open source 的套件、`openssl dgst`、`with open(path) as f` 都不算。先讀")
        self.clean(check_no_opening_for_user)


class CourseworkTutorContractTest(Fixture):
    def setUp(self):
        super().setUp()
        write(self.root, "skills/coursework/SKILL.md",
              "---\nname: coursework\ndescription: 作業\ndisable-model-invocation: true\n---\n\n"
              "每一題包成 `<div class=\"part\" data-part=\"a\">…</div><!--/part-->`。\n")
        write(self.root, "skills/coursework/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        write(self.root, "skills/tutor/SKILL.md",
              "---\nname: tutor\ndescription: 教學\ndisable-model-invocation: true\n---\n\n見 `scripts/fill.py`。\n")
        write(self.root, "skills/tutor/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        write(self.root, "skills/tutor/scripts/fill.py", DOUBLE + "填值。" + DOUBLE + "\nimport re\n"
              'PART = re.compile(r"""<div\\b[^>]*\\bdata-part\\s*=\\s*["\']([^"\']+)["\'][^>]*>(.*?)</div>\\s*<!--/part-->""", re.S | re.I)\n')
        write(self.root, "skills/tutor/tests/test_fill.py", "")
        sub(self.root, "README.md", "| [notes](skills/notes/SKILL.md) | 筆記 |\n",
            "| [coursework](skills/coursework/SKILL.md) | 作業 |\n| [notes](skills/notes/SKILL.md) | 筆記 |\n| [tutor](skills/tutor/SKILL.md) | 教學 |\n")
        sub(self.root, ".github/workflows/test.yml", "steps:\n", "steps:\n  - run: python -m unittest discover -s skills/tutor/tests -v\n")

    def test_valid_contract_passes(self):
        self.clean(check_coursework_tutor_contract)

    def test_omitting_snippet_is_allowed(self):
        write(self.root, "skills/coursework/SKILL.md",
              "---\nname: coursework\ndescription: 作業\ndisable-model-invocation: true\n---\n\n寫出 `answer.html`。\n")
        self.clean(check_coursework_tutor_contract)

    def test_mismatched_data_part_marker_fails(self):
        sub(self.root, "skills/coursework/SKILL.md", "<!--/part-->", "")
        self.red(check_coursework_tutor_contract)


if __name__ == "__main__":
    unittest.main()
