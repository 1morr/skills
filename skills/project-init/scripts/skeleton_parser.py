"""共用專案骨架（roadmap、progress、decisions、.scratch 票面與紀錄）的單一解析器。

提供 check_docs、next_step、ticket_notes、dashboard 與 skel CLI 共用的權威解析邏輯：
- 統一票頭 `Status:` 與 `Blocked by:`（相容粗體 `**Blocked by:**`）
- 統一 `## Comments` 紀錄（`Session 紀錄：`、`決定：`、`變更：`、`等使用者：`），接納全半形分隔符 `｜`/`|` 與括號 `（...）`/`(...)`
- 統一里程碑佇列選擇：優先取 `進行中`；無 `進行中` 時自動切換到第一個未結束且 `排在 <已結束> 之後`（或未設前置）的工作佇列
只用標準函式庫。
"""

from __future__ import annotations

import datetime
import re
import subprocess
from pathlib import Path

ROADMAP_REL = "docs/roadmap.md"
PROGRESS_REL = "docs/progress.md"
DECISIONS_REL = "docs/decisions.md"
CHANGELOG_REL = "CHANGELOG.md"
DEVELOPMENT_REL = "docs/development.md"
SCRATCH_DIR = ".scratch"

MILESTONES_HEADING = "里程碑"
SESSIONS_HEADING = "Session 紀錄"
DECISIONS_HEADING = "紀錄"
ARCHIVED_DECISIONS_HEADING = "決定"
ACCEPTANCE_HEADING = "驗收"
USER_TRIAL_HEADING = "使用者試"

STATES = {"未開工": "todo", "進行中": "active", "已驗收": "done", "不做": "dropped"}
ACTIVE_WORD = "進行中"
CLOSED_WORDS = ("已驗收", "不做")
CLOSED_STATES = ("done", "dropped")

DECIDERS = ("使用者定", "使用者同意", "Agent 定")
UNMARKED = "未標"
KINDS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")

SESSION_NOTE = "Session 紀錄："
DECISION_NOTE = "決定："
CHANGE_NOTE = "變更："
NO_CHANGE = "變更：無"
WAITING = "等使用者："
COMMENTS_HEADING = "## Comments"

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
SEPARATOR_ROW_RE = re.compile(r"\|?[\s:|-]+\|?")
ITEM_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+)?")
AFTER_RE = re.compile(r"排在\s*`?([^\s`，。；、]+)`?\s*之後")
MILESTONE_DIR_RE = re.compile(r"^m\d+(\.\d+)?$", re.I)
ACCEPTANCE_SUFFIXES = ("-acceptance.md", "-close.md")

STATUS_RE = re.compile(r"^\**Status:?\**:?\s*(\S.*?)\s*$", re.I)
BLOCKED_RE = re.compile(r"^\**Blocked by:?\**:?\s*(.*)$", re.I)
DROPPED_RE = re.compile(r"^(?:wontfix|cancelled|canceled)\b", re.I)
CHECKBOX_RE = re.compile(r"^\s*[-*] \[([ xX])\]")
TICKET_NUMBER_RE = re.compile(r"^(\d+[a-z]?)-")
NOTE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(.*)$")
DECIDER_RE = re.compile(r"[（(](%s)[）)]" % "|".join(DECIDERS))
CHANGE_RE = re.compile(
    r"^變更：(%s)\s*[｜|]\s*([^｜|]*?\S[^｜|]*?)\s*[｜|]\s*(\S.*)$" % "|".join(KINDS)
)
COMMAND_RE = re.compile(r"`(/[^`\s][^`]*)`")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def strip_html_comments(text: str) -> str:
    """移除 <!-- ... -->，保持原本的行號（多行註解保留相同數量的換行）。"""
    return HTML_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def plain(text: str) -> str:
    """拿掉 Markdown 連結與反引號，留下純文字。"""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.replace("`", "").strip()


def label_of(name: str) -> str:
    return name.upper() if MILESTONE_DIR_RE.match(name) else name


def state_of(status: str) -> str:
    return next((code for word, code in STATES.items() if status.startswith(word)), "")


def numbered_sections(text: str, strip_parens: bool = True) -> dict:
    """{`##` 標題: [(行號, 行), …]}；跳過 HTML 註解與 fenced code block，同名標題取第一個。"""
    cleaned = strip_html_comments(text)
    out, current, fenced = {}, None, False
    for number, line in enumerate(cleaned.split("\n"), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            raw_title = line[3:].strip()
            title = re.split(r"[（(]", raw_title)[0].strip() if strip_parens else raw_title
            current = out.setdefault(title, [])
            continue
        if current is not None:
            current.append((number, line))
    return out


def sections_list(text: str) -> list:
    """[(原始標題, [(行號, 行), …])]；跳過 HTML 註解與 fenced code block，保留順序與重複段供驗證。"""
    cleaned = strip_html_comments(text)
    out, fenced = [], False
    for number, line in enumerate(cleaned.split("\n"), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            out.append((line[3:].strip(), []))
        elif out:
            out[-1][1].append((number, line))
    return out


def sections(text: str, strip_parens: bool = True) -> dict:
    return {title: [line for _, line in lines] for title, lines in numbered_sections(text, strip_parens=strip_parens).items()}


def split_cells(line: str, unescape_pipe: bool = True) -> list:
    raw = [c.strip() for c in CELL_SPLIT_RE.split(line.strip().strip("|"))]
    return [c.replace("\\|", "|") for c in raw] if unescape_pipe else raw


def is_separator_row(line: str) -> bool:
    s = line.strip()
    return bool(SEPARATOR_ROW_RE.fullmatch(s)) and "-" in s


def table_rows(lines, unescape_pipe: bool = True) -> list:
    """第一張表的每一行：(行號, [儲存格, …])，含表頭與分隔列；不到兩行就不是表。"""
    rows = []
    for number, line in lines:
        if line.strip().startswith("|"):
            rows.append((number, split_cells(line, unescape_pipe=unescape_pipe)))
        elif rows:
            break
    return rows if len(rows) >= 2 else []


def numbered_table(lines, file: str = "", unreadable: list | None = None) -> list:
    """第一張表的資料列：[(行號, {表頭欄名: 內容})]。欄數不符時不讀，若給 unreadable 則記錄原因。"""
    rows = table_rows(lines)
    if not rows:
        return []
    head, out = rows[0][1], []
    for number, cells in rows[1:]:
        if all(set(c) <= {":", "-", " "} and "-" in c for c in cells if c) and len(cells) == len(head):
            continue
        if len(cells) == len(head):
            out.append((number, dict(zip(head, cells))))
        elif unreadable is not None:
            unreadable.append({
                "file": file,
                "line": number,
                "text": plain(" | ".join(cells))[:80],
                "why": f"這一列有 {len(cells)} 欄，表頭是 {len(head)} 欄，沒有列進來；儲存格裡的 | 寫成 \\|",
            })
    return out


def decider_of(text: str) -> str:
    m = DECIDER_RE.search(text)
    return m.group(1) if m else UNMARKED


def strip_decider(text: str) -> str:
    return DECIDER_RE.sub("", text).strip()


def committed_or_mtime_date(path: Path, use_git: bool = False) -> str:
    if use_git:
        try:
            r = subprocess.run(
                ["git", "-C", str(path.parent), "log", "-1", "--format=%as", "--", path.name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        return datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
    except OSError:
        return ""


def _comments_lines(cleaned_text: str) -> list:
    """回傳 `## Comments` 之後的 [(行號, 行)]，跳過 fenced code block。"""
    lines = cleaned_text.split("\n")
    start_idx = None
    fenced = False
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.strip() == COMMENTS_HEADING:
            start_idx = idx + 1
            break
    if start_idx is None:
        return []
    out = []
    fenced = False
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append((idx + 1, line))
    return out


def parse_ticket(path: Path, git_date_fallback: bool = False) -> dict:
    """解析單張票檔的標題、Status、Blocked by、驗收進度與 Comments 紀錄。"""
    raw_text = read_text(path)
    cleaned = strip_html_comments(raw_text)
    lines = cleaned.split("\n")

    raw_title = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), path.stem)
    status, blocked = "", []
    fenced = False
    for l in lines:
        if l.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if l.startswith("## "):
            break
        m = STATUS_RE.match(l)
        if m and not status:
            status = m.group(1).strip("* ").strip()
        m = BLOCKED_RE.match(l)
        if m:
            blocked = re.findall(r"\d+[a-z]?", m.group(1))

    secs = numbered_sections(cleaned)
    has_acceptance = ACCEPTANCE_HEADING in secs
    if has_acceptance:
        criteria_lines = [l for _, l in secs[ACCEPTANCE_HEADING]]
    else:
        cutoff = next((i for i, l in enumerate(lines) if l.strip() == COMMENTS_HEADING), len(lines))
        criteria_lines = lines[:cutoff]

    boxes = []
    fenced = False
    for l in criteria_lines:
        if l.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            m = CHECKBOX_RE.match(l)
            if m:
                boxes.append(m.group(1) != " ")

    num_match = TICKET_NUMBER_RE.match(path.name)
    number = num_match.group(1) if num_match else path.stem
    done = status.lower().startswith("done")
    dropped = bool(DROPPED_RE.match(status))
    closed = done or dropped

    date = ""
    sessions, decisions, changes, odd_changes, asked = [], [], [], [], []
    for line_no, raw_line in _comments_lines(cleaned):
        line = ITEM_PREFIX_RE.sub("", raw_line)
        if line.startswith(SESSION_NOTE):
            rest = line[len(SESSION_NOTE):].strip()
            dated = NOTE_DATE_RE.match(rest)
            if dated:
                date = date or dated.group(1)
                rest = dated.group(2)
            sessions.append(rest)
        elif line.startswith(DECISION_NOTE):
            rest = line[len(DECISION_NOTE):].strip()
            decisions.append((strip_decider(rest), decider_of(rest), line))
            asked = []
        elif line.startswith(WAITING) and line[len(WAITING):].strip():
            asked.append(line[len(WAITING):].strip())
        elif CHANGE_RE.match(line.strip()):
            kind, feature, said = CHANGE_RE.match(line.strip()).groups()
            changes.append((kind.strip(), feature.strip(), said.strip()))
        elif line.startswith(CHANGE_NOTE) and line.strip() != NO_CHANGE:
            odd_changes.append((line_no, line.strip()))

    if not date and (sessions or decisions or asked):
        date = committed_or_mtime_date(path, use_git=git_date_fallback)

    clean_title = plain(raw_title)
    bare_title = re.sub(r"^\S+\s*[:：—-]\s*", "", clean_title)
    return {
        "file": path.name,
        "number": number,
        "title": clean_title,
        "bare_title": bare_title,
        "status": status,
        "done": done,
        "dropped": dropped,
        "closed": closed,
        "blocked": blocked,
        "has_acceptance": has_acceptance,
        "checked": sum(boxes),
        "boxes": len(boxes),
        "waiting": [] if closed else [plain(q) for q in asked],
        "waiting_raw": [] if closed else asked,
        "open_questions_even_if_closed": asked,
        "date": date,
        "sessions": sessions,
        "decisions": decisions,
        "changes": changes,
        "odd_changes": odd_changes,
    }


def parse_spec(directory: Path) -> dict:
    secs = sections(read_text(directory / "spec.md"))
    goal = " ".join(l.strip() for l in secs.get("目標", []) if l.strip() and not l.startswith("#"))
    scope = []
    for l in secs.get("範圍", []):
        if l.startswith("#") and "不做" in l:
            break
        if l.startswith(("- ", "* ")):
            scope.append(plain(l[2:]))
    return {"detail": plain(goal)[:400], "scope": scope[:40]}


def parse_tickets_in(directory: Path, git_date_fallback: bool = False) -> list:
    issues = directory / "issues"
    if not issues.is_dir():
        return []
    return [parse_ticket(p, git_date_fallback=git_date_fallback) for p in sorted(issues.glob("*.md"))]


def parse_milestones(repo: Path) -> tuple:
    """解析 docs/roadmap.md 的〈里程碑〉表，回傳 (milestones, unreadable)。"""
    out, unreadable = [], []
    roadmap_secs = numbered_sections(read_text(repo / ROADMAP_REL))
    for number, row in numbered_table(roadmap_secs.get(MILESTONES_HEADING, []), ROADMAP_REL, unreadable):
        name = plain(row.get(MILESTONES_HEADING, ""))
        if not name:
            continue
        raw_status = row.get("狀態", "").strip()
        status = plain(raw_status)
        st = state_of(status)
        if not st:
            unreadable.append({
                "file": ROADMAP_REL,
                "line": number,
                "text": f"{name}：{status}"[:80],
                "why": "狀態要以「%s」其中一個開頭，先當成未開工" % "、".join(STATES),
            })
        after_match = AFTER_RE.search(raw_status) or AFTER_RE.search(status)
        label = name.split()[0]
        directory = repo / SCRATCH_DIR / label.lower()
        out.append({
            "name": name,
            "label": label,
            "goal": plain(row.get("目標", "")),
            "status": status,
            "raw_status": raw_status,
            "state": st or "todo",
            "after": after_match.group(1).lower() if after_match else "",
            "after_name": after_match.group(1) if after_match else "",
            "dir": directory.name,
            "tickets": parse_tickets_in(directory),
            **parse_spec(directory),
        })
    return out, unreadable


def unlisted_efforts(repo: Path, listed: list) -> list:
    known = {m["dir"] for m in listed}
    out = []
    scratch = repo / SCRATCH_DIR
    if not scratch.is_dir():
        return out
    for d in sorted(p for p in scratch.iterdir() if (p / "issues").is_dir()):
        if d.name.lower() in known:
            continue
        found = parse_tickets_in(d)
        live = [t for t in found if not t["dropped"]]
        out.append({
            "name": d.name,
            "label": d.name,
            "goal": "",
            "status": f"{ROADMAP_REL} 的里程碑表沒有列它",
            "raw_status": "",
            "state": "done" if live and all(t["done"] for t in live) else "todo",
            "after": "",
            "after_name": "",
            "dir": d.name,
            "tickets": found,
            **parse_spec(d),
        })
    return out


def open_tickets(milestone: dict) -> list:
    return [t for t in milestone["tickets"] if not t["closed"]]


def current_milestone(listed: list):
    """目前的工作佇列：優先取 `進行中`；無 `進行中` 時，取第一個未結束、有未完成票且前置列已結束（或無前置）的列。"""
    for m in listed:
        if m["state"] == "active":
            return m
    by_dir = {m["dir"]: m for m in listed}
    for m in listed:
        if m["state"] in CLOSED_STATES or not open_tickets(m):
            continue
        if not m["after"] or (m["after"] in by_dir and by_dir[m["after"]]["state"] in CLOSED_STATES):
            return m
    return None


def doable_tickets(milestone: dict) -> list:
    """回傳該里程碑目前可立即執行的票（未關、未等使用者、同目錄已知的前置票皆已結束）。"""
    closed = {t["number"] for t in milestone["tickets"] if t["closed"]}
    known = {t["number"] for t in milestone["tickets"]}
    return [
        t for t in open_tickets(milestone)
        if not t["waiting"] and all(b in closed or b not in known for b in t["blocked"])
    ]


def next_ticket_of(listed: list):
    """回傳目前工作佇列中第一張可做的票資訊；沒有時回傳 None。"""
    now = current_milestone(listed)
    if not now:
        return None
    ready = doable_tickets(now)
    if not ready:
        return None
    t = ready[0]
    return {
        "milestone": now["label"],
        "dir": now["dir"],
        "file": t["file"],
        "number": t["number"],
        "title": t["title"],
        "bare_title": t["bare_title"],
        "command": f"/implement {SCRATCH_DIR}/{now['dir']}/issues/{t['file']}",
    }


def last_progress_step(repo: Path) -> tuple:
    """回傳 (最後一列的下一步, 最後一列 dict 或 None, unreadable)。"""
    unreadable = []
    secs = numbered_sections(read_text(repo / PROGRESS_REL))
    rows = [r for _, r in numbered_table(secs.get(SESSIONS_HEADING, []), PROGRESS_REL, unreadable)]
    if not rows:
        return "", None, unreadable
    last = rows[-1]
    return last.get("下一步", "").strip(), last, unreadable
