"""檢查專案骨架的狀態機與工程閘門硬契約（瘦身版，共用 skeleton_parser）。

    python3 check_docs.py [repo 根目錄，預設目前目錄]

硬契約違規印到 stderr、回傳 exit 1；字元上限超標僅印 `WARN:` 軟警告、不擋 exit code（無硬違規時 exit 0）。
接納半形 `|` 與半形括號 `(...)`，不檢查 `docs/` 逐檔寫入指令檔、`docs/research/` 日期位置或單行排版字數。
只用標準函式庫。
"""

import re
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import skeleton_parser as sp  # noqa: E402

PROGRESS = sp.PROGRESS_REL
ROADMAP = sp.ROADMAP_REL
DECISIONS = sp.DECISIONS_REL
BRIEF, ARCHITECTURE = "docs/design-brief.md", "ARCHITECTURE.md"
BUDGETS = {"AGENTS.md": 8000, ARCHITECTURE: 15000, PROGRESS: 20000, BRIEF: 30000}

SCRATCH = sp.SCRATCH_DIR
MILESTONES = sp.MILESTONES_HEADING
SESSIONS = sp.SESSIONS_HEADING
LOG = sp.DECISIONS_HEADING
ARCHIVED = sp.ARCHIVED_DECISIONS_HEADING
ACCEPTANCE = sp.ACCEPTANCE_HEADING
USER_TRIAL = sp.USER_TRIAL_HEADING
SPEC_SECTIONS = ("目標", "範圍", "共同規則", "驗收", "票序")

WAITING = sp.WAITING
ACTIVE = sp.ACTIVE_WORD
STATES = tuple(sp.STATES.keys())
CLOSED = sp.CLOSED_WORDS
DECIDERS = sp.DECIDERS
DECIDER_LIST = "".join(f"（{d}）" for d in DECIDERS)
SESSION_NOTE = sp.SESSION_NOTE
DECISION_NOTE = sp.DECISION_NOTE
CHANGE_NOTE = sp.CHANGE_NOTE
NO_CHANGE = sp.NO_CHANGE
KINDS = sp.KINDS
CHANGELOG, UNRELEASED = sp.CHANGELOG_REL, "[Unreleased]"

DEVIATION_RE = re.compile(r"^- \d{4}-\d{2}-\d{2} \S")
DATED_SESSION_NOTE_RE = re.compile(r"^Session 紀錄：\d{4}-\d{2}-\d{2} \S")
VERSION_RE = re.compile(r"^\[[^\]\s]+\] - \d{4}-\d{2}-\d{2}(?:\s.*)?$")
ENTRY_RE = re.compile(r"^- \*\*[^*]+\*\*[：:]")

DEVELOPMENT = sp.DEVELOPMENT_REL
GATE_SECTION = "閘門"
GATE_COLUMNS = ("閘門", "指令或設定檔")
GATE_ROWS = ("格式", "Lint", "型別", "單元測試", "端到端冒煙", "密鑰掃描", "依賴漏洞", "依賴更新")
NOT_APPLICABLE_RE = re.compile(r"^不適用[：:]\s*\S")
INLINE_CODE_RE = re.compile(r"`[^`\s][^`]*`")
ROADMAP_COLUMNS = ("里程碑", "目標", "狀態")


def _table(lines) -> tuple:
    rows = sp.table_rows(lines, unescape_pipe=False)
    if not rows:
        return [], []
    head = rows[0][1]
    data = [(n, c) for n, c in rows[1:] if not sp.is_separator_row("|" + "|".join(c) + "|")]
    return head, data


def check_progress(text: str) -> list:
    secs = sp.numbered_sections(text)
    if SESSIONS not in secs:
        return [f"{PROGRESS}：缺〈{SESSIONS}〉段"]
    head, rows = _table(secs[SESSIONS])
    if "下一步" not in head:
        return [f"{PROGRESS}：〈{SESSIONS}〉的表要有「下一步」欄"]
    if not rows:
        return [f"{PROGRESS}：〈{SESSIONS}〉沒有任何一列"]
    n, last = rows[-1]
    idx = head.index("下一步")
    step = last[idx] if len(last) > idx else ""
    if not (sp.COMMAND_RE.search(step) or INLINE_CODE_RE.search(step) or step.startswith(WAITING)):
        return [f"{PROGRESS}:{n}：最後一列的「下一步」要給下一個 session 的指令（行內程式碼），或以「{WAITING}」開頭"]
    return []


def _decision_lines(rel: str, title: str, lines) -> list:
    out = []
    for n, l in lines:
        if not l.strip():
            continue
        if not DEVIATION_RE.match(l):
            out.append(f"{rel}:{n}：〈{title}〉每條一行，寫成「- YYYY-MM-DD <里程碑>（<決定者>）：…」")
        elif len(sp.DECIDER_RE.findall(l)) != 1:
            out.append(f"{rel}:{n}：這一條要標一個決定者（全半形括號皆可）：{DECIDER_LIST}")
    return out


def check_decisions(text: str) -> list:
    secs = sp.numbered_sections(text)
    if LOG not in secs:
        return [f"{DECISIONS}：缺〈{LOG}〉段"]
    return _decision_lines(DECISIONS, LOG, secs[LOG])


def check_archive(root: Path) -> list:
    out = []
    archive = root / "docs" / "archive"
    for p in sorted(archive.glob("*.md")) if archive.is_dir() else []:
        rel = f"docs/archive/{p.name}"
        secs = sp.numbered_sections(sp.read_text(p))
        if SESSIONS not in secs:
            out.append(f"{rel}：缺〈{SESSIONS}〉段")
        if ARCHIVED not in secs:
            out.append(f"{rel}：缺〈{ARCHIVED}〉段（沒有決定就留空段）")
        else:
            out += _decision_lines(rel, ARCHIVED, secs[ARCHIVED])
        if not any(l.strip() for _, l in secs.get(USER_TRIAL, [])):
            out.append(f"{rel}：缺〈{USER_TRIAL}〉段，或段裡沒有字")
    return out


def check_changelog(root: Path) -> list:
    if not (root / CHANGELOG).is_file():
        return []
    out, version, kind, fenced, seen = [], None, None, False, False
    cleaned = sp.strip_html_comments(sp.read_text(root / CHANGELOG))
    for n, line in enumerate(cleaned.split("\n"), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        if line.startswith("## "):
            version, kind = line[3:].strip(), None
            seen = seen or version == UNRELEASED
            if version != UNRELEASED and not VERSION_RE.match(version):
                out.append(f"{CHANGELOG}:{n}：`##` 標題寫成 `## {UNRELEASED}` 或 `## [<版號>] - YYYY-MM-DD`")
        elif line.startswith("### ") and version is not None:
            kind = line[4:].strip()
            if kind not in KINDS:
                out.append(f"{CHANGELOG}:{n}：分類只能是 {'、'.join(KINDS)}")
        elif version == UNRELEASED and line.startswith("- "):
            if kind is None:
                out.append(f"{CHANGELOG}:{n}：條目要放在某個分類底下（`### Added` 這類）")
            elif not ENTRY_RE.match(line):
                out.append(f"{CHANGELOG}:{n}：條目寫成 `- **<功能>**：<一句>`")
    if not seen:
        out.append(f"{CHANGELOG}：缺 `## {UNRELEASED}`")
    return out


def _roadmap_table(text: str) -> tuple:
    secs = sp.numbered_sections(text)
    if MILESTONES not in secs:
        return [], [], [f"{ROADMAP}：缺〈{MILESTONES}〉段"]
    head, rows = _table(secs[MILESTONES])
    missing = [c for c in ROADMAP_COLUMNS if c not in head]
    if missing:
        return [], [], [f"{ROADMAP}：〈{MILESTONES}〉的表要有「{'」「'.join(missing)}」欄"]
    return head, rows, []


def _dir_of(head: list, row: list) -> str:
    idx = head.index(MILESTONES) if MILESTONES in head else 0
    words = sp.plain(row[idx]).split() if len(row) > idx else []
    return words[0].lower() if words else ""


def check_roadmap(text: str) -> list:
    head, rows, errs = _roadmap_table(text)
    if errs:
        return errs
    out = []
    state_idx = head.index("狀態")
    active = []
    for n, r in rows:
        st = sp.plain(r[state_idx]) if len(r) > state_idx else ""
        if not st.startswith(STATES):
            out.append(f"{ROADMAP}:{n}：狀態要以{'、'.join(f'「{s}」' for s in STATES)}其中一個開頭")
        elif st.startswith(ACTIVE):
            active.append(_dir_of(head, r))
    if len(active) > 1:
        out.append(f"{ROADMAP}：有 {len(active)} 個里程碑的狀態以「{ACTIVE}」開頭，最多一個")
    return out


def check_warnings(root: Path) -> list:
    """字元上限軟警告（不擋 exit code）。"""
    out = []
    for rel, limit in BUDGETS.items():
        p = root / rel
        if p.is_file():
            size = len(sp.read_text(p))
            if size > limit:
                out.append(f"WARN: {rel}：{size} 字元，建議上限 {limit}（多 {size - limit}）")
    return out


def check_scratch(root: Path) -> list:
    out = []
    base = root / SCRATCH
    if not base.is_dir():
        return out
    roadmap_path = root / ROADMAP
    listed = None
    active = set()
    if roadmap_path.is_file():
        head, rows, errs = _roadmap_table(sp.read_text(roadmap_path))
        if not errs and head:
            s_idx = head.index("狀態")
            listed = {_dir_of(head, r): (r[s_idx] if len(r) > s_idx else "") for _, r in rows if _dir_of(head, r)}
            active = {d for d, st in listed.items() if sp.plain(st).startswith(ACTIVE)}

    has_changelog = (root / CHANGELOG).is_file()
    for d in sorted(p for p in base.iterdir() if (p / "issues").is_dir()):
        rel = f"{SCRATCH}/{d.name}"
        d_key = d.name.lower()
        if listed is not None and d_key not in listed:
            out.append(f"{rel}/：{ROADMAP} 的里程碑表沒有列它")
        spec_path = d / "spec.md"
        if not spec_path.is_file():
            out.append(f"{rel}/：有票卻沒有 spec.md")
        else:
            secs = sp.numbered_sections(sp.read_text(spec_path))
            missing = [s for s in SPEC_SECTIONS if s not in secs]
            if missing:
                out.append(f"{rel}/spec.md：缺〈{'〉〈'.join(missing)}〉段")
            elif d_key in active:
                if not any(re.match(rf"###\s*{USER_TRIAL}", l) for _, l in secs[ACCEPTANCE]):
                    out.append(f"{rel}/spec.md：〈{ACCEPTANCE}〉底下要有 `### {USER_TRIAL}`")

        tickets = [sp.parse_ticket(p) for p in sorted((d / "issues").glob("*.md"))]
        state_raw = listed.get(d_key, "") if listed else ""
        state_plain = sp.plain(state_raw)
        if state_plain and not state_plain.startswith((ACTIVE,) + CLOSED) and any(not t["closed"] for t in tickets):
            after = sp.AFTER_RE.search(state_raw) or sp.AFTER_RE.search(state_plain)
            if not after or after.group(1).lower() == d_key or (listed is not None and after.group(1).lower() not in listed):
                out.append(f"{ROADMAP}：{d.name} 有票沒做完，狀態又不是「{ACTIVE}」，需寫明排在表裡哪一列之後")

        if sp.MILESTONE_DIR_RE.match(d.name) and not any(t["file"].endswith(sp.ACCEPTANCE_SUFFIXES) for t in tickets):
            out.append(f"{rel}/issues/：沒有驗收票（檔名以 -acceptance.md 結尾）")

        for t in tickets:
            where = f"{rel}/issues/{t['file']}"
            raw_clean = sp.strip_html_comments(sp.read_text(d / "issues" / t["file"]))
            if not t["status"]:
                out.append(f"{where}：第一個 ## 之前要有一行 `Status:`")
            elif d_key in active and t["done"]:
                if t["open_questions_even_if_closed"]:
                    out.append(f"{where}：票做完了，Comments 裡的「{WAITING}」還沒有回答")
                comments_lines = [sp.ITEM_PREFIX_RE.sub("", l) for _, l in sp._comments_lines(raw_clean)]
                if not any(DATED_SESSION_NOTE_RE.match(l) for l in comments_lines):
                    out.append(f"{where}：做完的票要在 `## Comments` 之後留一行「{SESSION_NOTE}<YYYY-MM-DD> <做了什麼>」")
                if has_changelog and not any(l.startswith(CHANGE_NOTE) for l in comments_lines):
                    out.append(f"{where}：做完的票要在 `## Comments` 之後留至少一行「{CHANGE_NOTE}」（無使用者可見變更寫「{NO_CHANGE}」）")
                for l in comments_lines:
                    if l.startswith(DECISION_NOTE) and len(sp.DECIDER_RE.findall(l)) != 1:
                        out.append(f"{where}：「{DECISION_NOTE}」那一行要標一個決定者：{DECIDER_LIST}")
                if t["odd_changes"]:
                    out.append(f"{where}：「{CHANGE_NOTE}」那一行寫成「{CHANGE_NOTE}<{'|'.join(KINDS)}>｜<功能>｜<一句>」（半形 | 亦可）或「{NO_CHANGE}」")
            if listed and d_key in listed and not state_plain.startswith(CLOSED):
                if not t["has_acceptance"] or t["boxes"] == 0:
                    out.append(f"{where}：要有 `## {ACCEPTANCE}` 段並含勾選框")
    return out


def _any_ticket_done(root: Path) -> bool:
    base = root / SCRATCH
    if not base.is_dir():
        return False
    return any(sp.parse_ticket(p)["done"] for p in base.glob("*/issues/*.md"))


def check_gates(root: Path) -> list:
    if not (root / DEVELOPMENT).is_file():
        return []
    secs = sp.numbered_sections(sp.read_text(root / DEVELOPMENT))
    if GATE_SECTION not in secs:
        return [f"{DEVELOPMENT}：缺〈{GATE_SECTION}〉段"]
    head, rows = _table(secs[GATE_SECTION])
    if any(c not in head for c in GATE_COLUMNS):
        return [f"{DEVELOPMENT}：〈{GATE_SECTION}〉的表要有「{'」「'.join(GATE_COLUMNS)}」兩欄"]
    name_at, how_at = head.index(GATE_COLUMNS[0]), head.index(GATE_COLUMNS[1])
    out, started = [], _any_ticket_done(root)
    for gate in GATE_ROWS:
        found = [(n, r) for n, r in rows if len(r) > max(name_at, how_at) and r[name_at].replace("*", "").startswith(gate)]
        if not found:
            out.append(f"{DEVELOPMENT}：〈{GATE_SECTION}〉的表缺「{gate}」這一列")
            continue
        n, row = found[0]
        if started and not (INLINE_CODE_RE.search(row[how_at]) or NOT_APPLICABLE_RE.match(row[how_at])):
            out.append(f"{DEVELOPMENT}:{n}：已經有票做完了，「{gate}」還沒有著落（填行內程式碼指令或「不適用：<理由>」）")
    return out


def run(root: Path) -> list:
    out = []
    for rel, fn in ((PROGRESS, check_progress), (DECISIONS, check_decisions), (ROADMAP, check_roadmap)):
        if (root / rel).is_file():
            out += fn(sp.read_text(root / rel))
        else:
            out.append(f"找不到 {rel}")
    return out + check_archive(root) + check_changelog(root) + check_scratch(root) + check_gates(root)


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    root = Path(argv[0]) if argv else Path.cwd()
    warns = check_warnings(root)
    for w in warns:
        print(w, file=sys.stderr)
    found = run(root)
    for p in found:
        print(p, file=sys.stderr)
    if found:
        print(f"{len(found)} 條違規", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
