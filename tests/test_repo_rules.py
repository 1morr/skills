"""AGENTS.md 裡能用程式檢查的 repo 規則。

    python -m unittest discover -s tests

每條規則是一個 check_*(root) 函式，回傳違規清單；它的 docstring 就是那條規則，AGENTS.md 指到這裡、不另抄一份。測試分兩種：
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
MODEL_INVOKED = {"diff", "tutor"}
# md 裡的路徑縮寫指到哪：值是相對 repo 根的路徑，{skill} 換成那份 md 所屬的 skill
SHORT = {"O": "orca", "P": "pages", "S": "skills/{skill}/scripts", "T": "skills/{skill}/templates"}
# 有 md 要檢查的目錄
DOC_DIRS = ("skills", "orca", "pages")

LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
SHORT_PATH = re.compile(r"<([A-Z]+)>/([A-Za-z0-9_./-]+)")
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
    """md 裡沒有 ../：skill 之間不互連，共用的檔放 orca/ 或 pages/。"""
    return [f"{md.relative_to(root)} 有 ../：共用的檔放 orca/ 或 pages/，或改為載入對方 skill"
            for md in docs(root) if "../" in read(md)]


def check_invocation(root: Path, allowed=frozenset(MODEL_INVOKED)) -> list:
    """沒設 disable-model-invocation: true 的 skill 恰好是 MODEL_INVOKED 裡那幾個。"""
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


SHORT_DEF = re.compile(r"`<([A-Z]+)>`\s*是\s*本檔(?:同目錄|往上兩層)的\s*`([A-Za-z0-9_.-]+)/`")
ANY_SHORT_DEF = re.compile(r"`<([A-Z]+)>`\s*是[^。\n]*`[^`\n]+/`")


def check_short_declared(root: Path, short=frozenset(SHORT)) -> list:
    """SKILL.md 用相對自身位置的路徑（本檔同目錄／往上兩層的 `<目錄>/`）定義路徑縮寫，且縮寫都在 SHORT 裡；skill 內用到的縮寫都要在它的 SKILL.md 定義。"""
    out = []
    for name in skills(root):
        skill_dir = root / "skills" / name
        skill_text = read(skill_dir / "SKILL.md")
        declared = dict(SHORT_DEF.findall(skill_text))
        for key in ANY_SHORT_DEF.findall(skill_text):
            if key not in short:
                out.append(f"skills/{name}/SKILL.md 定義了 <{key}>，SHORT 裡沒有")
            elif key not in declared:
                out.append(f"skills/{name}/SKILL.md 的 <{key}> 要用相對本檔的路徑（本檔同目錄／往上兩層的 `<目錄>/`）定義")
        for key, tail in declared.items():
            if key in SHORT and tail != SHORT[key].rsplit("/", 1)[-1]:
                out.append(f"skills/{name}/SKILL.md 把 <{key}> 定義成 `{tail}/`，應為 `{SHORT[key].rsplit('/', 1)[-1]}/`")
        used = {key for md in sorted(skill_dir.rglob("*.md"))
                for key, _ in SHORT_PATH.findall(read(md)) if key in short}
        for key in sorted(used - set(declared)):
            out.append(f"skills/{name}/ 用了 <{key}>/，但 skills/{name}/SKILL.md 沒有用相對本檔的路徑定義 <{key}>")
    return out


FORBIDDEN_VARS = re.compile(r"\$\{CLAUDE_[A-Z0-9_]*\}?|\$ARGUMENTS\b")


def check_no_claude_vars(root: Path) -> list:
    """SKILL.md 與附屬 md 不寫 ${CLAUDE_SKILL_DIR}、${CLAUDE_PLUGIN_ROOT} 或 $ARGUMENTS：改用相對本檔的路徑縮寫與自然語言說明參數。"""
    out = []
    for md in docs(root):
        found = sorted(set(FORBIDDEN_VARS.findall(read(md))))
        if found:
            out.append(f"{md.relative_to(root)} 寫了 {'、'.join(found)}：跨 harness 不會替換，改用相對路徑縮寫")
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
    return sorted(list((root / "orca").rglob("*.sh")) + list((root / "skills").rglob("*.sh")))


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


def check_usage_header(root: Path) -> list:
    """腳本開頭寫用法：orca/scripts/ 的前兩行有「用法」（第一行可以是 shebang）；skills/*/scripts/ 和 pages/scripts/ 的 .py 以 docstring 開頭。"""
    out = []
    for f in sorted(list((root / "orca/scripts").glob("*.sh")) + list((root / "orca/scripts").glob("*.py"))):
        if "用法" not in "\n".join(read(f).split("\n")[:2]):
            out.append(f"{f.relative_to(root)} 開頭沒有寫用法")
    for f in sorted(list(root.glob("skills/*/scripts/*.py")) + list((root / "pages/scripts").glob("*.py"))):
        lines = [line for line in read(f).split("\n") if not line.startswith("#!")]
        if not lines or lines[0][:3] not in (DOUBLE, SINGLE):
            out.append(f"{f.relative_to(root)} 要以 docstring 開頭，寫用法和輸出格式")
    return out


DOUBLE, SINGLE = '"' * 3, "'" * 3
# 反引號裡以 open 開頭的指令（macOS）；內文裡的英文字 open 不算
OPENS_FOR_USER = re.compile(r"xdg-open|orca tab create|`open\s[^`]*`")


def check_no_opening_for_user(root: Path) -> list:
    """skill 不替使用者開瀏覽器或分頁（`open …`、xdg-open、orca tab create）：交付照 pages/HANDOFF.md，給網址和完整路徑。"""
    return [f"{md.relative_to(root)} 叫執行者替使用者開瀏覽器或分頁：改照 pages/HANDOFF.md 給網址和完整路徑"
            for md in docs(root) if OPENS_FOR_USER.search(read(md))]


# `handle=`、`state=heads-up`，以及腳本用的 `started: NO` / `started: yes`；orca 指令自己印的 `status: running`、`accepted: true` 不歸這條管
ORCA_KEY = re.compile(r"`([a-z][a-z-]*)(?:(=)([A-Za-z-]*)|(: )(NO|yes))`")


def check_orca_keys(root: Path) -> list:
    """引用 orca 腳本的 md（orca/ 裡的，和內文有 <O> 的）用反引號寫的輸出（`handle=`、`state=heads-up`、`started: NO`）：鍵要是 orca/scripts/ 某支腳本印的，寫了值的，值也要在那支腳本裡。selftest.sh 不算。"""
    scripts = [read(p) for p in sorted((root / "orca/scripts").glob("*")) if p.is_file() and p.name != "selftest.sh"]
    out = []
    for p in docs(root):
        text = read(p)
        if (root / "orca") not in p.parents and "<O>" not in text:
            continue
        for key, sep, value in sorted({(m[0], m[1] or m[3], m[2] or m[4]) for m in ORCA_KEY.findall(text)}):
            printing = [s for s in scripts if re.search(r"(?<![\w-])" + re.escape(key + sep), s)]
            word = re.compile(r"(?<![\w-])" + re.escape(value) + r"(?![\w-])")
            if not printing:
                out.append(f"{p.relative_to(root)}：`{key}{sep}` 沒有任何一支 orca 腳本印")
            elif value and not any(word.search(s) for s in printing):
                out.append(f"{p.relative_to(root)}：`{key}{sep}{value}` 的值不在印 {key}{sep} 的腳本裡")
    return out


FENCE = re.compile(r"^```.*?^```[ \t]*$", re.M | re.S)
HEADING_RAW = re.compile(r"^#+\s+(.+?)\s*$", re.M)
FILE_REF_GROUP = re.compile(
    r"(?:"
    r"\[[^\]]*\]\((?P<link>[^)#\s]+\.md)(?:#[^)]*)?\)"
    r"|`(?P<tick>[^`\n]*?\.md)`"
    r"|(?P<plain>(?:[A-Za-z0-9_.-]+/)*[A-Za-z][A-Za-z0-9_-]*\.md)"
    r")(?:\s*的)?"
    r"(?P<secs>(?:〈[^〉]+〉)+(?:[與和](?:〈[^〉]+〉)+)*)"
)
EXT_OWNER_GROUP = re.compile(
    r"(?:學習紀錄|roadmap|(?:專案的?)?指令檔(?:的|有)?|它的|把它)"
    r"(?P<secs>(?:〈[^〉]+〉)+(?:[與和](?:〈[^〉]+〉)+)*)"
)
SECTION_TOKEN = re.compile(r"〈([^〉]+)〉")


def has_heading(path: Path, section: str) -> bool:
    raws = HEADING_RAW.findall(FENCE.sub("", read(path)))
    if re.match(r"^\d+\.\s*", section):
        return any(h.startswith(section) for h in raws)
    norms = [re.sub(r"^\d+\.\s*", "", h) for h in raws]
    return any(h.startswith(section) for h in norms)


def resolve_ref_target(root: Path, md: Path, raw_path: str):
    m = re.match(r"^<([A-Z]+)>/(.+)$", raw_path)
    if m and m.group(1) in SHORT:
        rel = md.relative_to(root)
        skill = rel.parts[1] if rel.parts[0] == "skills" else ""
        cand = root / SHORT[m.group(1)].format(skill=skill) / m.group(2)
        return cand if cand.is_file() else None
    if "/" in raw_path:
        cand = (md.parent / raw_path).resolve()
        return cand if cand.is_file() else None
    return next((d / raw_path for d in (md.parent, root / "orca", root / "pages", root) if (d / raw_path).is_file()), None)


def check_section_refs(root: Path) -> list:
    """md 裡寫 `X.md〈節名〉`、`[X.md](X.md)〈節名〉`、連續 `〈節A〉〈節B〉` 或同檔裸 `〈節名〉` 時，目標檔案要有以節名開頭的標題；templates/ 不查。"""
    out = []
    for md in docs(root):
        if "templates" in md.relative_to(root).parts:
            continue
        text = FENCE.sub("", read(md))
        consumed = []
        file_checks = []
        for m in FILE_REF_GROUP.finditer(text):
            consumed.append((m.start(), m.end()))
            raw_path = m.group("link") or m.group("tick") or m.group("plain")
            target = resolve_ref_target(root, md, raw_path)
            if target:
                for sec in SECTION_TOKEN.findall(m.group("secs")):
                    file_checks.append((Path(raw_path).name, target, sec))
        for m in EXT_OWNER_GROUP.finditer(text):
            if not any(s <= m.start() < e for s, e in consumed):
                consumed.append((m.start(), m.end()))
        for name, target, sec in dict.fromkeys(file_checks):
            if not has_heading(target, sec):
                out.append(f"{md.relative_to(root)} 寫了 {name}〈{sec}〉，{target.relative_to(root)} 沒有這個開頭的標題")
        bare_secs = [m.group(1) for m in SECTION_TOKEN.finditer(text)
                     if not any(s <= m.start() < e for s, e in consumed)]
        for sec in dict.fromkeys(bare_secs):
            if not has_heading(md, sec):
                out.append(f"{md.relative_to(root)} 寫了〈{sec}〉，本檔沒有這個開頭的標題")
    return out


CW_PART_SNIPPET = re.compile(r"`(<div\b[^`\n]*\bdata-part=[^`\n]*)`")


def check_coursework_tutor_contract(root: Path) -> list:
    """coursework〈教學〉引用 tutor 的 GUIDE.md〈做法導讀〉，且 answer.html 的 data-part 標記格式與 tutor/scripts/fill.py 的 PART 一致。"""
    cw = root / "skills/coursework/SKILL.md"
    guide = root / "skills/tutor/GUIDE.md"
    fill_py = root / "skills/tutor/scripts/fill.py"
    if not (cw.is_file() and guide.is_file() and fill_py.is_file()):
        return []
    out = []
    cw_text = read(cw)
    refs = re.findall(r"GUIDE\.md`?〈([^〉]+)〉", cw_text)
    if "做法導讀" not in refs:
        out.append("skills/coursework/SKILL.md 沒有引用 GUIDE.md〈做法導讀〉")
    for sec in dict.fromkeys(refs):
        if not has_heading(guide, sec):
            out.append(f"skills/coursework/SKILL.md 引用了 GUIDE.md〈{sec}〉，但 skills/tutor/GUIDE.md 沒有這個標題")
    m = CW_PART_SNIPPET.search(cw_text)
    if not m:
        out.append("skills/coursework/SKILL.md 沒有寫出 answer.html 的 `<div … data-part=…>` 標記範例")
    else:
        ns = {}
        exec(compile(read(fill_py), str(fill_py), "exec"), ns)
        part_re = ns.get("PART")
        if part_re is None or not part_re.search(m.group(1)):
            out.append(f"skills/coursework/SKILL.md 的 `{m.group(1)}` 無法被 skills/tutor/scripts/fill.py 的 PART 解析")
    return out


CHECKS = (check_names, check_listed, check_paths, check_no_cross_links, check_invocation, check_tested,
          check_short_declared, check_no_claude_vars, check_portable_wording, check_shell_portable,
          check_manifests_match, check_usage_header, check_no_opening_for_user, check_orca_keys,
          check_section_refs, check_coursework_tutor_contract)


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
    """最小的合格 repo：diff（模型可觸發、有腳本）和 notes（手動、用 orca 與 pages）。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="repo-rules-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        r = self.root
        write(r, "skills/diff/SKILL.md", "---\nname: diff\ndescription: 對照頁。使用者要 diff 頁時用。\n---\n\n"
              "`<S>` 是本檔同目錄的 `scripts/`，`<P>` 是本檔往上兩層的 `pages/`。跑 `python <S>/diff.py a b`，細節見 [LOOK.md](LOOK.md)。\n")
        write(r, "skills/diff/LOOK.md", "# 外觀\n\n照 `<P>/TOKENS.md`。\n")
        write(r, "skills/diff/scripts/diff.py", DOUBLE + "比對兩個版本。\n\n    python diff.py a b\n" + DOUBLE + "\n")
        write(r, "skills/diff/tests/test_diff.py", "")
        write(r, "skills/notes/SKILL.md", "---\nname: notes\ndescription: 記筆記\ndisable-model-invocation: true\n---\n\n"
              "`<O>` 是本檔往上兩層的 `orca/`。先讀 `<O>/COORDINATOR.md`，再跑 `bash <O>/scripts/wait.sh <handle>`，寫到 `<批次目錄>/notes.md`。\n")
        write(r, "orca/COORDINATOR.md", "# 流程\n")
        write(r, "orca/scripts/wait.sh", "# 用法：bash wait.sh <handle>\necho \"${H}沒有回應\"\n")
        write(r, "orca/scripts/selftest.sh", "# 用法：bash selftest.sh\n")
        write(r, "pages/TOKENS.md", "# 配色\n")
        write(r, "tests/test_repo_rules.py", "")
        write(r, "README.md", "| Skill | 做什麼 |\n|---|---|\n| [diff](skills/diff/SKILL.md) | 對照 |\n| [notes](skills/notes/SKILL.md) | 筆記 |\n\n"
              "```\npython -m unittest discover -s skills/diff/tests\nbash orca/scripts/selftest.sh\npython -m unittest discover -s tests\n```\n")
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

    def test_script_missing_from_own_skill(self):
        sub(self.root, "skills/diff/SKILL.md", "<S>/diff.py", "<S>/compare.py")
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
        sub(self.root, "skills/notes/SKILL.md", "先讀", "載入 `diff` skill，省略的地方寫 `...`。先讀")
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
        write(self.root, "pages/scripts/build.py", DOUBLE + "組頁。" + DOUBLE + "\n")
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


class ShortDeclaredTest(Fixture):
    DEFINE = "`<Z>` 是本檔同目錄的 `zed/`。先讀"

    def test_abbreviation_missing_from_the_list(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", self.DEFINE)
        self.red(check_short_declared)

    def test_the_list_decides(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", self.DEFINE)
        self.clean(check_short_declared, short=frozenset(SHORT) | {"Z"})

    def test_used_shorthand_must_be_declared_with_relative_path(self):
        sub(self.root, "skills/notes/SKILL.md", "`<O>` 是本檔往上兩層的 `orca/`。", "")
        self.red(check_short_declared)
        sub(self.root, "skills/notes/SKILL.md", "先讀", "`<O>` 是 `${CLAUDE_PLUGIN_ROOT}/orca/`。先讀")
        self.red(check_short_declared)

    def test_wrong_target_directory_in_declaration(self):
        sub(self.root, "skills/notes/SKILL.md", "`<O>` 是本檔往上兩層的 `orca/`", "`<O>` 是本檔往上兩層的 `pages/`")
        self.red(check_short_declared)

    def test_placeholders_that_are_not_definitions_do_not_matter(self):
        sub(self.root, "skills/notes/SKILL.md", "先讀", "寫成 `<批次目錄>/r<N>/prompt.md`，`<N>` 是輪次。先讀")
        self.clean(check_short_declared)


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
                write(self.root, rel, original + "\n`<O>` 是 `${CLAUDE_PLUGIN_ROOT}/orca`。\n")
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


class UsageHeaderTest(Fixture):
    def test_script_without_usage(self):
        write(self.root, "orca/scripts/wait.sh", "set -u\necho hi\n")
        self.red(check_usage_header)

    def test_usage_too_far_down(self):
        write(self.root, "orca/scripts/wait.sh", "set -u\necho hi\n# 用法：bash wait.sh\n")
        self.red(check_usage_header)

    def test_shebang_python_and_wording_do_not_matter(self):
        write(self.root, "orca/scripts/wait.sh", "#!/bin/sh\n# 用法（掛在背景）：sh wait.sh <handle> [sent]\n")
        write(self.root, "orca/scripts/scr.py", "# 用法：python3 scr.py <handle>\n")
        write(self.root, "skills/diff/scripts/diff.py", "#!/usr/bin/env python3\n" + SINGLE + "換一種引號、換一種說法。" + SINGLE + "\nimport sys\n")
        self.clean(check_usage_header)

    def test_skill_or_pages_script_without_docstring(self):
        for rel in ("skills/diff/scripts/diff.py", "pages/scripts/build.py"):
            with self.subTest(rel):
                write(self.root, rel, "import sys\n# 用法寫在後面不算\n")
                self.red(check_usage_header)
                write(self.root, rel, DOUBLE + "有了。" + DOUBLE + "\n")


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


class OrcaKeysTest(Fixture):
    def setUp(self):
        super().setUp()
        write(self.root, "orca/scripts/wait.sh", "# 用法：bash wait.sh <handle>\n# state= 的值：done、heads-up\necho \"state=$st\"\necho \"started: yes\"\n")
        write(self.root, "orca/COORDINATOR.md", "# 流程\n\n第一行是 `state=`；`state=heads-up` 時先記下來。印 `started: yes` 才算開好。\n")

    def test_value_the_script_never_prints(self):
        sub(self.root, "orca/COORDINATOR.md", "`state=heads-up`", "`state=finished`")
        self.red(check_orca_keys)

    def test_key_no_script_prints(self):
        sub(self.root, "orca/COORDINATOR.md", "`state=`", "`status=`")
        self.red(check_orca_keys)

    def test_colon_form_and_skill_files_are_checked_too(self):
        sub(self.root, "orca/COORDINATOR.md", "`started: yes`", "`started: NO`")
        self.red(check_orca_keys)
        sub(self.root, "orca/COORDINATOR.md", "`started: NO`", "`started: yes`")
        sub(self.root, "skills/notes/SKILL.md", "寫到", "印 `gate=open` 才寫到")
        self.red(check_orca_keys)

    def test_script_renames_a_value(self):
        sub(self.root, "orca/scripts/wait.sh", "heads-up", "notice")
        self.red(check_orca_keys)

    def test_selftest_does_not_count_as_printing(self):
        write(self.root, "orca/scripts/selftest.sh", "# 用法：bash selftest.sh\necho \"gate=open\"\n")
        sub(self.root, "orca/COORDINATOR.md", "`state=`", "`gate=`")
        self.red(check_orca_keys)

    def test_wording_env_vars_and_other_skills_do_not_matter(self):
        sub(self.root, "orca/COORDINATOR.md", "時先記下來", "的那一輪，把全文抄進 ledger，再帶 `BASE=main` 跑；orca 回 `accepted: true`")
        write(self.root, "skills/diff/LOOK.md", "# 外觀\n\n照 `<P>/TOKENS.md`。屬性寫 `data-tol=x`、`state=whatever`。\n")
        self.clean(check_orca_keys)


class SectionRefsTest(Fixture):
    def setUp(self):
        super().setUp()
        write(self.root, "orca/COORDINATOR.md", "# 流程\n\n## 2. 開工：先查主分支\n\n## 授權\n")
        sub(self.root, "skills/notes/SKILL.md", "先讀",
            "\n\n## 1. 準備\n\n## 2. 收尾\n\n照 COORDINATOR.md〈開工〉和 `<O>/COORDINATOR.md`〈授權〉，再看〈準備〉。先讀")

    def test_section_that_does_not_exist(self):
        sub(self.root, "skills/notes/SKILL.md", "〈開工〉", "〈開公〉")
        self.red(check_section_refs)

    def test_heading_renamed_under_a_reference(self):
        sub(self.root, "orca/COORDINATOR.md", "## 授權", "## 權限")
        self.red(check_section_refs)

    def test_file_next_to_the_reference_is_checked_too(self):
        sub(self.root, "skills/diff/SKILL.md", "細節見", "照 LOOK.md〈文件頁〉。細節見")
        self.red(check_section_refs)

    def test_markdown_link_section_ref(self):
        sub(self.root, "skills/diff/SKILL.md", "[LOOK.md](LOOK.md)", "[LOOK.md](LOOK.md)〈外觀〉")
        self.clean(check_section_refs)
        sub(self.root, "skills/diff/SKILL.md", "[LOOK.md](LOOK.md)〈外觀〉", "[LOOK.md](LOOK.md)〈不存在〉")
        self.red(check_section_refs)

    def test_consecutive_section_refs_check_all_sections(self):
        sub(self.root, "skills/notes/SKILL.md", "COORDINATOR.md〈開工〉", "[COORDINATOR.md](COORDINATOR.md)〈開工〉〈授權〉")
        self.clean(check_section_refs)
        sub(self.root, "skills/notes/SKILL.md", "〈開工〉〈授權〉", "〈開工〉〈不存在〉")
        self.red(check_section_refs)
        sub(self.root, "skills/notes/SKILL.md", "〈開工〉〈不存在〉", "〈開工〉與〈不存在〉")
        self.red(check_section_refs)

    def test_bare_same_file_section_refs(self):
        sub(self.root, "skills/notes/SKILL.md", "再看〈準備〉", "再看〈1. 準備〉〈2. 收尾〉")
        self.clean(check_section_refs)
        sub(self.root, "skills/notes/SKILL.md", "〈2. 收尾〉", "〈下面沒有的節〉")
        self.red(check_section_refs)
        sub(self.root, "skills/notes/SKILL.md", "〈下面沒有的節〉", "〈9. 收尾〉")
        self.red(check_section_refs)

    def test_numbering_quotes_and_external_files_do_not_matter(self):
        sub(self.root, "orca/COORDINATOR.md", "## 2. 開工", "### 7. 開工")
        sub(self.root, "skills/notes/SKILL.md", "先讀",
            "回「照你的判斷」，見專案的 `docs/development.md`〈全部檢查〉、`issue-tracker.md` 的〈Conventions〉、"
            "學習紀錄〈讀者〉〈考試形式〉、roadmap〈M0 骨架〉、指令檔的〈UI〉〈視覺化〉。先讀")
        write(self.root, "skills/notes/templates/instructions.md", "照 README.md〈使用者專案才有的節〉與〈不存在的裸節〉。\n")
        self.clean(check_section_refs)


class CourseworkTutorContractTest(Fixture):
    def setUp(self):
        super().setUp()
        write(self.root, "skills/coursework/SKILL.md",
              "---\nname: coursework\ndescription: 作業\ndisable-model-invocation: true\n---\n\n"
              "每一題包成 `<div class=\"part\" data-part=\"a\">…</div><!--/part-->`，照它的 GUIDE.md〈做法導讀〉寫那一節。\n")
        write(self.root, "skills/tutor/SKILL.md",
              "---\nname: tutor\ndescription: 教學。\n---\n\n`<S>` 是本檔同目錄的 `scripts/`。見 [GUIDE.md](GUIDE.md)〈做法導讀〉。\n")
        write(self.root, "skills/tutor/GUIDE.md", "# 導讀頁\n\n## 做法導讀\n")
        write(self.root, "skills/tutor/scripts/fill.py", DOUBLE + "填值。" + DOUBLE + "\nimport re\n"
              'PART = re.compile(r"""<div\\b[^>]*\\bdata-part\\s*=\\s*["\']([^"\']+)["\'][^>]*>(.*?)</div>\\s*<!--/part-->""", re.S | re.I)\n')
        write(self.root, "skills/tutor/tests/test_fill.py", "")
        sub(self.root, "README.md", "| [notes](skills/notes/SKILL.md) | 筆記 |\n",
            "| [coursework](skills/coursework/SKILL.md) | 作業 |\n| [notes](skills/notes/SKILL.md) | 筆記 |\n| [tutor](skills/tutor/SKILL.md) | 教學 |\n")
        sub(self.root, "README.md", "```\n", "```\npython -m unittest discover -s skills/tutor/tests\n")
        sub(self.root, ".github/workflows/test.yml", "steps:\n", "steps:\n  - run: python -m unittest discover -s skills/tutor/tests -v\n")

    def test_valid_contract_passes(self):
        self.clean(check_coursework_tutor_contract)

    def test_missing_or_renamed_guide_section_fails(self):
        sub(self.root, "skills/tutor/GUIDE.md", "## 做法導讀", "## 作業教學")
        self.red(check_coursework_tutor_contract)
        sub(self.root, "skills/tutor/GUIDE.md", "## 作業教學", "## 做法導讀")
        sub(self.root, "skills/coursework/SKILL.md", "GUIDE.md〈做法導讀〉", "GUIDE.md")
        self.red(check_coursework_tutor_contract)

    def test_mismatched_data_part_marker_fails(self):
        sub(self.root, "skills/coursework/SKILL.md", "<!--/part-->", "")
        self.red(check_coursework_tutor_contract)


if __name__ == "__main__":
    unittest.main()
