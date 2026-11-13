"""檢查 docs/progress.md、docs/roadmap.md、里程碑 spec 與票的格式；規則寫在 progress.md〈寫法與封存〉。

    python check_docs.py [repo 根目錄，預設目前目錄]

全部通過 exit 0；否則每條違規印一行到 stderr、exit 1。規則：
  progress.md
    - `##` 段依序各一次：寫法與封存、Session 紀錄、偏差與決定
    - 〈Session 紀錄〉整段是一張表（表外沒有別的字），每列不超過 200 字元
    - 最後一列的「下一步」給得出指令（含 `/…` 的行內程式碼），或以「等使用者：」開頭，或是「由協調者決定」
    - 〈偏差與決定〉每條一行、以 `- YYYY-MM-DD ` 開頭、不超過 200 字元、標一個決定者：（使用者定）（使用者同意）（Agent 定）
  roadmap.md
    - 有〈里程碑〉段，裡面的表有「狀態」欄，狀態以「進行中」開頭的最多一個
  .scratch/
    - 有 issues/ 的目錄要有 spec.md，`##` 段含：目標、範圍、共同規則、驗收、票序（標題後面可以加括號說明）
    - 里程碑目錄（m 加數字，例如 m0、m1.5）的 issues/ 要有一張 -acceptance.md 結尾的驗收票
    - 每張票在第一個 `##` 之前有一行 `Status:`
只用標準函式庫。
"""

import re
import sys
from pathlib import Path

PROGRESS = "docs/progress.md"
ROADMAP = "docs/roadmap.md"
SCRATCH = ".scratch"
MILESTONES, SESSIONS, DEVIATIONS = "里程碑", "Session 紀錄", "偏差與決定"
STATE = "狀態"
PROGRESS_SECTIONS = ("寫法與封存", SESSIONS, DEVIATIONS)
SPEC_SECTIONS = ("目標", "範圍", "共同規則", "驗收", "票序")
MAX_CHARS = 200
WAITING = "等使用者："
COORDINATOR = "由協調者決定"
ACTIVE = "進行中"

COMMAND = re.compile(r"`/[^`\s][^`]*`")
DEVIATION = re.compile(r"^- \d{4}-\d{2}-\d{2} \S")
DECIDERS = ("使用者定", "使用者同意", "Agent 定")
DECIDER = re.compile("（(?:%s)）" % "|".join(DECIDERS))
MILESTONE_DIR = re.compile(r"^m\d+(\.\d+)?$")
STATUS = re.compile(r"^\**Status:?\**:?\s*\S", re.I)
CELL_SPLIT = re.compile(r"(?<!\\)\|")


def sections(text: str) -> list:
    """[(標題, [(行號, 內容), …])]；程式碼區塊裡的 ## 不算標題，第一個 ## 之前的內容不屬於任何段。"""
    out, fenced = [], False
    for number, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            out.append((line[3:].strip(), []))
        elif out:
            out[-1][1].append((number, line))
    return out


def cells(row: str) -> list:
    return [c.strip() for c in CELL_SPLIT.split(row.strip().strip("|"))]


def is_row(line: str) -> bool:
    return line.strip().startswith("|")


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|?", line.strip())) and "-" in line


def table(lines) -> tuple:
    """(表頭欄位, [(行號, 欄位), …])；沒有表就是 ([], [])。"""
    rows = [(n, l) for n, l in lines if is_row(l)]
    if not rows:
        return [], []
    return cells(rows[0][1]), [(n, cells(l)) for n, l in rows[1:] if not is_separator(l)]


def check_progress(text: str) -> list:
    out = []
    secs = sections(text)
    titles = [t for t, _ in secs]
    order = "、".join(f"〈{t}〉" for t in PROGRESS_SECTIONS)
    for title in PROGRESS_SECTIONS:
        if titles.count(title) == 0:
            out.append(f"{PROGRESS}：缺〈{title}〉段。## 段依序是{order}")
        elif titles.count(title) > 1:
            out.append(f"{PROGRESS}：〈{title}〉段出現 {titles.count(title)} 次，只能一次")
    known = [t for t in titles if t in PROGRESS_SECTIONS]
    if sorted(set(known), key=PROGRESS_SECTIONS.index) != list(dict.fromkeys(known)):
        out.append(f"{PROGRESS}：## 段的順序不對，依序是{order}")
    extra = [t for t in titles if t not in PROGRESS_SECTIONS]
    if extra:
        out.append(f"{PROGRESS}：多了〈{'〉〈'.join(extra)}〉段。細節放票、spec、brief 或 plan，這裡只有{order}")
    by_title = {}
    for title, lines in secs:
        by_title.setdefault(title, lines)

    if SESSIONS in by_title:
        lines = by_title[SESSIONS]
        for n, l in lines:
            if l.strip() and not is_row(l):
                out.append(f"{PROGRESS}:{n}：〈{SESSIONS}〉整段是一張表，表外不放別的字")
            if len(l) > MAX_CHARS:
                out.append(f"{PROGRESS}:{n}：這一列 {len(l)} 字元，上限 {MAX_CHARS}。細節放票的 Comments")
        head, rows = table(lines)
        if "下一步" not in head:
            out.append(f"{PROGRESS}：〈{SESSIONS}〉的表要有「下一步」欄")
        elif not rows:
            out.append(f"{PROGRESS}：〈{SESSIONS}〉沒有任何一列")
        else:
            n, last = rows[-1]
            step = last[head.index("下一步")] if len(last) > head.index("下一步") else ""
            if not (COMMAND.search(step) or step.startswith(WAITING) or step.startswith(COORDINATOR)):
                out.append(f"{PROGRESS}:{n}：最後一列的「下一步」要給下一個 session 的完整指令（寫成 `/指令 …`），"
                           f"或以「{WAITING}」開頭，或寫「{COORDINATOR}」")

    if DEVIATIONS in by_title:
        for n, l in by_title[DEVIATIONS]:
            if not l.strip():
                continue
            if not DEVIATION.match(l):
                out.append(f"{PROGRESS}:{n}：〈{DEVIATIONS}〉每條一行，寫成「- YYYY-MM-DD <里程碑> …」")
            elif len(DECIDER.findall(l)) != 1:
                out.append(f"{PROGRESS}:{n}：這一條要標一個決定者：" + "".join(f"（{d}）" for d in DECIDERS))
            if len(l) > MAX_CHARS:
                out.append(f"{PROGRESS}:{n}：這一條 {len(l)} 字元，上限 {MAX_CHARS}。細節放票、brief、plan 或 ADR")
    return out


def check_roadmap(text: str) -> list:
    by_title = {}
    for title, lines in sections(text):
        by_title.setdefault(title, lines)
    if MILESTONES not in by_title:
        return [f"{ROADMAP}：缺〈{MILESTONES}〉段"]
    head, rows = table(by_title[MILESTONES])
    if STATE not in head:
        return [f"{ROADMAP}：〈{MILESTONES}〉的表要有「{STATE}」欄"]
    i = head.index(STATE)
    active = [r for _, r in rows if len(r) > i and r[i].startswith(ACTIVE)]
    if len(active) > 1:
        return [f"{ROADMAP}：有 {len(active)} 個里程碑的狀態以「{ACTIVE}」開頭，最多一個"]
    return []


def check_scratch(root: Path) -> list:
    out = []
    base = root / SCRATCH
    if not base.is_dir():
        return out
    for d in sorted(p for p in base.iterdir() if (p / "issues").is_dir()):
        rel = f"{SCRATCH}/{d.name}"
        spec = d / "spec.md"
        if not spec.is_file():
            out.append(f"{rel}/：有票卻沒有 spec.md，里程碑開工的第一步是寫 spec")
        else:
            titles = [re.split(r"[（(]", t)[0].strip() for t, _ in sections(spec.read_text(encoding="utf-8"))]
            missing = [s for s in SPEC_SECTIONS if s not in titles]
            if missing:
                out.append(f"{rel}/spec.md：缺〈{'〉〈'.join(missing)}〉段")
        tickets = sorted((d / "issues").glob("*.md"))
        if MILESTONE_DIR.match(d.name) and not any(t.name.endswith("-acceptance.md") for t in tickets):
            out.append(f"{rel}/issues/：沒有驗收票（檔名以 -acceptance.md 結尾），它是里程碑的最後一張票")
        for t in tickets:
            head = t.read_text(encoding="utf-8").split("\n## ")[0]
            if not any(STATUS.match(line) for line in head.split("\n")):
                out.append(f"{rel}/issues/{t.name}：第一個 ## 之前要有一行 `Status:`")
    return out


def run(root: Path) -> list:
    out = []
    for rel, check in ((PROGRESS, check_progress), (ROADMAP, check_roadmap)):
        if (root / rel).is_file():
            out += check((root / rel).read_text(encoding="utf-8"))
        else:
            out.append(f"找不到 {rel}")
    return out + check_scratch(root)


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    found = run(Path(argv[0]) if argv else Path.cwd())
    for p in found:
        print(p, file=sys.stderr)
    if found:
        print(f"{len(found)} 條違規", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
