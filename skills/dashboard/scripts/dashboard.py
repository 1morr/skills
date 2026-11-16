"""從 repo 的固定文件產生專案總覽頁：里程碑與票的進度、功能與變更、決策、ADR、最近的 session。

    python dashboard.py <repo>... [-o <輸出.html>]          # 產生一頁靜態 HTML，印出路徑
    python dashboard.py --serve [--port 8765] [--host 127.0.0.1] <repo>...
                                                           # 起本機伺服器，印出網址；頁面每 3 秒重讀一次

讀的檔（project-init 的骨架；缺的列在頁面的「讀不到的檔」，其餘照樣顯示）：
  docs/roadmap.md      〈里程碑〉的表：里程碑、目標、狀態（看開頭的詞：未開工、進行中、已驗收、不做）
                       欄數和表頭不一樣的列（儲存格裡有沒跳脫的 `|`）列在「讀不到的行」；docs/progress.md 的表也是
  .scratch/<目錄>/     spec.md 的〈目標〉〈範圍〉；issues/*.md 的標題、Status:、Blocked by:、〈驗收〉裡的勾選框
                       （票沒有〈驗收〉這一段時，數 `## Comments` 之前的）
                       有 issues/ 卻不在里程碑表裡的目錄，另列在「不在 roadmap 的工作」
                       還沒驗收的里程碑，票在 `## Comments` 之後留的 `Session 紀錄：<日期> …`、`決定：…（<決定者>）`、
                       `變更：<分類>｜<功能>｜<一句>`（列在「變更」的未發版裡，標「待組裝」；`變更：無` 不列），
                       以及沒做完的票還沒回答的 `等使用者：<題目>`（它後面沒有 `決定：` 行；列在「等你決定」）：
                       票是這兩種紀錄唯一的來源，沒寫日期的用票檔的修改日期。舊骨架把它們抄進下面兩個檔，
                       那兩個檔已經有同一張票的條目（「M1 票 03」「M1 03」）時不再從票讀一次
  docs/decisions.md    〈紀錄〉每條：日期、里程碑、決定者、內容（不是做票時定的決定）
  docs/archive/*.md    〈決定〉：已驗收里程碑的決定，里程碑取檔名；舊骨架的段名〈偏差與決定〉也讀
                       〈Session 紀錄〉的表：封存的 session 紀錄。儲存格裡有沒跳脫的 `|` 而多出欄位的列，
                       多的併進「結果」；少了「結果」後面幾欄的照讀；連「結果」都沒有的列在「讀不到的行」
                       這兩處以 `- ` 開頭卻不是 `- YYYY-MM-DD …` 的行，列在頁面的「讀不到的行」
  CHANGELOG.md         Keep a Changelog 的版本段（`## [Unreleased]`、`## [<版號>] - <日期>`）與六個分類底下的條目
                       `- **<功能>**：<一句>`（續行算進同一條）。已發版的段落裡不是這個寫法的條目照列、沒有功能名；
                       〈[Unreleased]〉裡不是這個寫法的列在「讀不到的行」。沒有這個檔就沒有這一區
                       「功能」區把同一個 <功能> 的條目排成一條時間線（新的在前），最早那一條的版本是它出現的版本
  docs/adr/*.md        編號與標題
  docs/progress.md     〈Session 紀錄〉的表；最後一列的「下一步」，以「等使用者：」開頭時列在「等你決定」
                       「等你決定」的每一題在 `waiting_all`：票上的在前，progress.md 的在後
                       下一步：沒在等使用者、進行中的里程碑又還有票時，是第一張沒做完、擋它的票都做完、自己沒在等使用者的票；
                       否則是最後一列寫的。算法和 project-init 的 `scripts/next_step.py` 同一套，`tests/test_skeleton_contract.py` 對
                       那張票另外放在 `next_ticket`（在等使用者時也有），頁面把它的指令放進可以複製的框
  git worktree list    別的 worktree 裡和主目錄不同的票，當成「進行中」

資料每次請求時現讀，不存快取。頁面不載入任何外部資源；配色和樣式都在本檔的 PAGE 裡，不取 pages/ 的。
只有 --serve 的頁面會每 3 秒重讀，靜態頁不會。只用標準函式庫。
頁面記在瀏覽器（localStorage）的兩件事：`dashboard-theme` 深淺色；`dashboard-seen:<repo 路徑>` 讀者按「標為看過」時
每樣東西的指紋，之後不一樣的標成「變了」「新的」。腳本不讀它們，也不寫任何東西進 repo。
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DECIDERS = ("使用者定", "使用者同意", "Agent 定")
UNMARKED = "未標"
# 早期的寫法，顯示時歸到現在的三種
OLD_DECIDERS = {"使用者決定": "使用者定", "使用者改決定": "使用者定", "擁有者決定": "使用者定", "使用者拍板": "使用者定",
                "使用者確認": "使用者同意", "協調者決定": "Agent 定"}
DECIDER_WORDS = "|".join(DECIDERS + tuple(OLD_DECIDERS))
DECISION = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (.*)$")
# 括號一開頭就是決定者的短括號：顯示時整個拿掉
DECIDER = re.compile("（(%s)[^）]{0,12}）" % DECIDER_WORDS)
# 決定者寫在括號中間（「（檢視，使用者決定）」）
DECIDER_IN_PARENS = re.compile("[（(][^（()）]*?(%s)[^（()）]*[）)]" % DECIDER_WORDS)
# 早期沒加括號的寫法；現在的三個詞不加括號時不認，內文裡太常見
DECIDER_BARE = re.compile("|".join(OLD_DECIDERS))
MILESTONE_FILE = re.compile(r"^[mM]\d+(\.\d+)?$")
DROPPED = re.compile(r"^(wontfix|cancelled|canceled)", re.I)
STATUS = re.compile(r"^\**Status:?\**:?\s*(\S.*?)\s*$", re.I)
CHECKBOX = re.compile(r"^\s*[-*] \[([ xX])\]")
ADR_FILE = re.compile(r"^(\d{3,4})-.*\.md$")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
SESSION_NOTE, DECISION_NOTE = "Session 紀錄：", "決定："
COMMENTS = "\n## Comments"
# 票上的紀錄行寫成清單（`- 決定：…`）或縮排的也認，和 project-init 的腳本一樣
ITEM = re.compile(r"^\s*(?:[-*+]\s+)?")
ACCEPTANCE = "驗收"
NOTE_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(.*)$")
TICKET_NUMBER = re.compile(r"^(\d+[a-z]?)-")
BLOCKED = re.compile(r"^Blocked by:\s*(.*)$", re.I)
COPIED_DECISION = re.compile(r"票\s*(\d+[a-z]?)")
KINDS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
CHANGE_NOTE, NO_CHANGE = "變更：", "變更：無"
CHANGE = re.compile(r"^變更：(%s)｜([^｜]+)｜(.+)$" % "|".join(KINDS))
UNRELEASED = "Unreleased"
VERSION_HEAD = re.compile(r"^## \[([^\]]+)\](?:\s*-\s*(\d{4}-\d{2}-\d{2}))?")
ENTRY = re.compile(r"^- \*\*(.+?)\*\*[：:]\s*(.*)$")
WAITING = "等使用者："
RESULT = "結果"
STATES = {"未開工": "todo", "進行中": "active", "已驗收": "done", "不做": "dropped"}


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def numbered_sections(text: str) -> dict:
    """{`##` 標題: [(行號, 行), …]}；程式碼區塊裡的不算標題，同名的取第一個。"""
    out, current, fenced = {}, None, False
    for number, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            title = re.split(r"[（(]", line[3:])[0].strip()
            current = out.setdefault(title, [])
            continue
        if current is not None:
            current.append((number, line))
    return out


def sections(text: str) -> dict:
    """{`##` 標題: [行, …]}"""
    return {title: [line for _, line in lines] for title, lines in numbered_sections(text).items()}


def table_rows(lines) -> list:
    """第一張表的每一行：(行號, [儲存格, …])，含表頭與分隔列；不到兩行就不是表。"""
    rows = []
    for number, line in lines:
        if line.strip().startswith("|"):
            rows.append((number, [c.strip().replace("\\|", "|") for c in CELL_SPLIT.split(line.strip().strip("|"))]))
        elif rows:
            break
    return rows if len(rows) >= 2 else []


def numbered_table(lines, file: str, unreadable: list) -> list:
    """第一張表的每一列：(行號, {表頭欄名: 內容})。欄數和表頭不一樣的列不讀，記進 unreadable。"""
    rows = table_rows(lines)
    if not rows:
        return []
    head, out = rows[0][1], []
    for number, cells in rows[2:]:
        if len(cells) == len(head):
            out.append((number, dict(zip(head, cells))))
        else:
            unreadable.append({"file": file, "line": number, "text": plain(" | ".join(cells))[:80],
                               "why": f"這一列有 {len(cells)} 欄，表頭是 {len(head)} 欄，沒有列進來；儲存格裡的 | 寫成 \\|"})
    return out


def plain(text: str) -> str:
    """拿掉 Markdown 的連結與反引號，留下讀得懂的字。"""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.replace("`", "").strip()


def state_of(status: str) -> str:
    """狀態開頭的詞對應的代號；不是約定的四個詞就是空字串。"""
    return next((state for word, state in STATES.items() if status.startswith(word)), "")


def ticket(path: Path) -> dict:
    lines = read(path).split("\n")
    title = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), path.stem)
    status, blocked = "", []
    for l in lines:
        if l.startswith("## "):
            break
        m = STATUS.match(l)
        if m and not status:
            status = m.group(1).strip("* ")
        m = BLOCKED.match(l)
        if m:
            blocked = re.findall(r"\d+[a-z]?", m.group(1))
    parts = sections("\n".join(lines))
    # 進度只看驗收條件：Comments 裡順手記的待辦不算
    criteria = parts[ACCEPTANCE] if ACCEPTANCE in parts else lines[:next((i for i, l in enumerate(lines) if l.startswith(COMMENTS.strip())), len(lines))]
    boxes = [m.group(1) != " " for m in map(CHECKBOX.match, criteria) if m]
    number = TICKET_NUMBER.match(path.name)
    asked, body = [], "\n".join(lines)
    for l in body.split(COMMENTS, 1)[1].split("\n") if COMMENTS in body else []:
        l = ITEM.sub("", l)
        if l.startswith(DECISION_NOTE):  # 回答寫成一行「決定：」，它前面的題就算答了
            asked = []
        elif l.startswith(WAITING) and l[len(WAITING):].strip():
            asked.append(plain(l[len(WAITING):]))
    closed = status.lower().startswith("done") or bool(DROPPED.match(status))
    return {"file": path.name, "number": number.group(1) if number else path.stem, "title": plain(title), "status": status,
            "done": status.lower().startswith("done"), "dropped": bool(DROPPED.match(status)), "blocked": blocked,
            "checked": sum(boxes), "boxes": len(boxes), "waiting": [] if closed else asked}


def notes(path: Path) -> dict:
    """票在 `## Comments` 之後留的紀錄：{date, sessions: [一句], decisions: [(一句, 決定者)], changes: [(分類, 功能, 一句)],
    odd: [(行號, 格式不對的「變更：」行)]}。"""
    text = read(path)
    out = {"date": "", "sessions": [], "decisions": [], "changes": [], "odd": []}
    start = text[:text.index(COMMENTS)].count("\n") + 1 if COMMENTS in text else 0
    for number, line in enumerate(text.split(COMMENTS, 1)[1].split("\n") if COMMENTS in text else [], start):
        line = ITEM.sub("", line)
        if line.startswith(SESSION_NOTE):
            rest = line[len(SESSION_NOTE):].strip()
            dated = NOTE_DATE.match(rest)
            if dated:
                out["date"], rest = out["date"] or dated.group(1), dated.group(2)
            out["sessions"].append(plain(rest))
        elif line.startswith(DECISION_NOTE):
            rest = line[len(DECISION_NOTE):].strip()
            out["decisions"].append((plain(DECIDER.sub("", rest)), decider_of(rest)))
        elif CHANGE.match(line.strip()):
            kind, feature, said = CHANGE.match(line.strip()).groups()
            out["changes"].append((kind, plain(feature), plain(said)))
        elif line.startswith(CHANGE_NOTE) and line.strip() != NO_CHANGE:
            out["odd"].append((number, line.strip()))
    if not out["date"] and (out["sessions"] or out["decisions"]):
        try:
            out["date"] = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
        except OSError:
            pass
    return out


def ticket_notes(repo: Path, live: list) -> list:
    """還沒驗收的里程碑裡每張留了紀錄的票：[(里程碑的名字, 票號, 紀錄)]；紀錄多一個 `file`，是票相對 repo 的路徑。"""
    out = []
    for m in live:
        for t in m["tickets"]:
            rel = f".scratch/{m['dir']}/issues/{t['file']}"
            found = notes(repo / rel)
            if any(found[k] for k in ("sessions", "decisions", "changes", "odd")):
                out.append((m["name"].split()[0], t["number"], dict(found, file=rel)))
    return out


def next_ticket(listed: list):
    """進行中的里程碑裡第一張沒做完、擋它的票都做完（或不做）、自己沒在等使用者的票：{milestone, dir, file, number, title, command}；沒有就是 None。"""
    for m in listed:
        if m["state"] != "active":
            continue
        closed = {t["number"] for t in m["tickets"] if t["done"] or t["dropped"]}
        known = {t["number"] for t in m["tickets"]}
        for t in m["tickets"]:
            if t["number"] not in closed and not t["waiting"] and all(b in closed or b not in known for b in t["blocked"]):
                return {"milestone": m["name"].split()[0], "dir": m["dir"], "file": t["file"], "number": t["number"], "title": t["title"],
                        "command": f"/implement .scratch/{m['dir']}/issues/{t['file']}"}
    return None


def tickets(directory: Path) -> list:
    return [ticket(p) for p in sorted((directory / "issues").glob("*.md"))] if (directory / "issues").is_dir() else []


def spec(directory: Path) -> dict:
    secs = sections(read(directory / "spec.md"))
    goal = " ".join(l.strip() for l in secs.get("目標", []) if l.strip() and not l.startswith("#"))
    scope = []
    for l in secs.get("範圍", []):
        if l.startswith("#") and "不做" in l:
            break
        if l.startswith(("- ", "* ")):
            scope.append(plain(l[2:]))
    return {"detail": plain(goal)[:400], "scope": scope[:40]}


def milestones(repo: Path) -> tuple:
    """(里程碑, 讀不到的行)。狀態開頭不是約定的詞時當成未開工，並列進讀不到的行。"""
    out, unreadable = [], []
    for number, row in numbered_table(numbered_sections(read(repo / "docs/roadmap.md")).get("里程碑", []), "docs/roadmap.md", unreadable):
        name = plain(row.get("里程碑", ""))
        if not name:
            continue
        status = plain(row.get("狀態", ""))
        if not state_of(status):
            unreadable.append({"file": "docs/roadmap.md", "line": number, "text": f"{name}：{status}"[:80],
                               "why": "狀態要以「%s」其中一個開頭，先當成未開工" % "、".join(STATES)})
        directory = repo / ".scratch" / name.split()[0].lower()
        out.append({"name": name, "goal": plain(row.get("目標", "")), "status": status, "state": state_of(status) or "todo",
                    "dir": directory.name, "tickets": tickets(directory), **spec(directory)})
    return out, unreadable


def unlisted(repo: Path, listed: list) -> list:
    """有票卻不在里程碑表裡的 `.scratch/` 目錄，長得和里程碑一樣，頁面另列一區。"""
    known = {m["dir"] for m in listed}
    out = []
    for d in sorted(p for p in (repo / ".scratch").iterdir() if (p / "issues").is_dir()) if (repo / ".scratch").is_dir() else []:
        if d.name.lower() in known:
            continue
        found = tickets(d)
        live = [t for t in found if not t["dropped"]]
        out.append({"name": d.name, "goal": "", "status": "docs/roadmap.md 的里程碑表沒有列它",
                    "state": "done" if live and all(t["done"] for t in live) else "todo", "dir": d.name, "tickets": found, **spec(d)})
    return out


def decider_of(rest: str) -> str:
    m = DECIDER_IN_PARENS.search(rest) or DECIDER_BARE.search(rest)
    if not m:
        return UNMARKED
    word = m.group(1) if m.re is DECIDER_IN_PARENS else m.group(0)
    return OLD_DECIDERS.get(word, word)


def decisions(repo: Path, from_tickets=()) -> tuple:
    """(決定, 讀不到的行)。封存檔裡的決定，里程碑是檔名（`m1.5.md` → `M1.5`）：早期的條目開頭常是「票 05」「拆票」。
    `from_tickets` 是 `ticket_notes` 讀到的；decisions.md 已經有同一張票的條目時（舊骨架抄過去的）不重複列。"""
    sources = []
    secs = numbered_sections(read(repo / "docs/decisions.md"))
    sources.append(("docs/decisions.md", "", secs.get("紀錄", []) + secs.get("搬移前的紀錄", [])))
    for archived in sorted((repo / "docs/archive").glob("*.md")) if (repo / "docs/archive").is_dir() else []:
        old = numbered_sections(read(archived))
        name = archived.stem.upper() if MILESTONE_FILE.match(archived.stem) else archived.stem
        sources.append((f"docs/archive/{archived.name}", name, old.get("決定", []) + old.get("偏差與決定", [])))
    out, unreadable = [], []
    for rel, archive, lines in sources:
        for number, line in lines:
            m = DECISION.match(line)
            if not m:
                if line.startswith("- "):
                    unreadable.append({"file": rel, "line": number, "text": plain(line[2:])[:80],
                                       "why": "決定要以「- YYYY-MM-DD 」開頭，沒有列進決策"})
                continue
            rest = m.group(2)
            head, colon, body = rest.partition("：")
            label = plain(DECIDER.sub("", head)) if colon else ""
            out.append({"date": m.group(1), "milestone": archive or re.split(r"[\s（(]", label)[0], "label": label,
                        "decider": decider_of(rest), "archived": bool(archive), "text": plain(DECIDER.sub("", body or rest))})
    copied = {(d["milestone"].upper(), n) for d in out if not d["archived"] for n in COPIED_DECISION.findall(d["label"])}
    for milestone, number, found in from_tickets:
        if (milestone.upper(), number) not in copied:
            out += [{"date": found["date"], "milestone": milestone, "label": f"{milestone} 票 {number}", "decider": decider,
                     "archived": False, "text": said} for said, decider in found["decisions"]]
    return sorted(out, key=lambda d: d["date"], reverse=True), unreadable


def changelog(repo: Path, from_tickets=()) -> tuple:
    """(版本段，照檔案的順序：[{version, date, entries: [{kind, feature, text, pending}]}], 讀不到的行)。
    `pending` 是還在票上、沒組進檔案的條目的票（「M1 03」），算在未發版裡；檔案裡的條目是空字串。"""
    versions, unreadable, version, kind, entry, fenced = [], [], None, None, None, False
    for number, line in enumerate(read(repo / "CHANGELOG.md").split("\n"), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if fenced or not line.strip():
            continue
        head = VERSION_HEAD.match(line)
        if line.startswith("## "):
            version, kind, entry = ({"version": head.group(1), "date": head.group(2) or "", "entries": []} if head else None), None, None
            if version:
                versions.append(version)
        elif line.startswith("### "):
            kind, entry = (line[4:].strip() if line[4:].strip() in KINDS else None), None
        elif version is None or kind is None:
            entry = None
        elif line.startswith("- "):
            m = ENTRY.match(line)
            if m or version["version"] != UNRELEASED:
                entry = {"kind": kind, "feature": plain(m.group(1)) if m else "", "text": plain(m.group(2) if m else line[2:]), "pending": ""}
                version["entries"].append(entry)
            else:
                entry = None
                unreadable.append({"file": "CHANGELOG.md", "line": number, "text": plain(line[2:])[:80],
                                   "why": "未發版的條目要寫成「- **<功能>**：<一句>」，沒有列進變更"})
        elif line[0] in " \t" and entry is not None:
            more = plain(line.strip().lstrip("-* "))  # 中文續行直接接上，兩邊都是英數才補空格
            entry["text"] += (" " if entry["text"][-1:].isascii() and more[:1].isascii() else "") + more
        else:
            entry = None
    pending = []
    for milestone, number, found in from_tickets:
        pending += [{"kind": k, "feature": feature, "text": said, "pending": f"{milestone} {number}"} for k, feature, said in found["changes"]]
        unreadable += [{"file": found["file"], "line": n, "text": odd[:80],
                        "why": "要寫成「變更：<%s>｜<功能>｜<一句>」或「變更：無」，沒有列進變更" % "|".join(KINDS)} for n, odd in found["odd"]]
    if pending:
        if not any(v["version"] == UNRELEASED for v in versions):
            versions.insert(0, {"version": UNRELEASED, "date": "", "entries": []})
        next(v for v in versions if v["version"] == UNRELEASED)["entries"] += pending
    return versions, unreadable


def features(versions: list) -> list:
    """[{name, since, entries: [{version, date, kind, text, pending}]}]：帶功能名的條目依功能分組，最近改過的功能在前，
    每個功能的條目新的在前；`since` 是最早那一條所在的版本。"""
    out = {}
    for v in versions:
        for e in v["entries"]:
            if e["feature"]:
                out.setdefault(e["feature"], []).append({"version": v["version"], "date": v["date"], "kind": e["kind"],
                                                         "text": e["text"], "pending": e["pending"]})
    return [{"name": name, "since": found[-1]["version"], "entries": found} for name, found in out.items()]


def adrs(repo: Path) -> list:
    out = []
    for p in sorted((repo / "docs/adr").glob("*.md")) if (repo / "docs/adr").is_dir() else []:
        m = ADR_FILE.match(p.name)
        if m:
            title = next((l.lstrip("# ").strip() for l in read(p).split("\n") if l.startswith("# ")), p.stem)
            out.append({"number": m.group(1), "title": plain(title), "file": p.name})
    return out


def sessions(repo: Path, from_tickets=()) -> tuple:
    """(session 紀錄，舊的在前；progress.md 最後一列的下一步；那一列，沒有就是 None；讀不到的行)。票上的 session 紀錄排進來；progress.md 已經有那張票的列時不重複列。"""
    unreadable = []
    rows = [row for _, row in numbered_table(numbered_sections(read(repo / "docs/progress.md")).get("Session 紀錄", []),
                                             "docs/progress.md", unreadable)]
    out = [{"date": r.get("日期", ""), "ticket": plain(r.get("票", "")), "result": plain(r.get("結果", "")),
            "next": r.get("下一步", "").strip()} for r in rows]
    step, last = (out[-1]["next"], out[-1]) if out else ("", None)
    copied = {s["ticket"].upper() for s in out}
    for milestone, number, found in from_tickets:
        if f"{milestone} {number}".upper() not in copied:
            out += [{"date": found["date"], "ticket": f"{milestone} {number}", "result": said, "next": ""} for said in found["sessions"]]
    return sorted(out, key=lambda s: s["date"]), step, last, unreadable


def archived_sessions(repo: Path) -> tuple:
    """([{里程碑, 檔名, rows}], 讀不到的行)：各封存檔〈Session 紀錄〉的表，新的在前。"""
    out, unreadable = [], []
    for archived in sorted((repo / "docs/archive").glob("*.md")) if (repo / "docs/archive").is_dir() else []:
        rows = table_rows(numbered_sections(read(archived)).get("Session 紀錄", []))
        if not rows:
            continue
        head, found = rows[0][1], []
        for number, cells in rows[2:]:
            extra = len(cells) - len(head)
            if extra > 0 and RESULT in head:  # 儲存格裡沒跳脫的 | 幾乎都在最長的「結果」欄
                i = head.index(RESULT)
                cells = cells[:i] + [" | ".join(cells[i:i + extra + 1])] + cells[i + extra + 1:]
            elif extra < 0 and RESULT in head and len(cells) > head.index(RESULT):  # 早期的列沒有「下一步」
                cells = cells + [""] * -extra
            if len(cells) != len(head):
                unreadable.append({"file": f"docs/archive/{archived.name}", "line": number, "text": plain(" | ".join(cells))[:80],
                                   "why": f"這一列有 {len(cells)} 欄，表頭是 {len(head)} 欄，沒有列進 session 紀錄"})
                continue
            r = dict(zip(head, cells))
            found.append({"date": r.get("日期", ""), "ticket": plain(r.get("票", "")), "result": plain(r.get(RESULT, ""))})
        name = archived.stem.upper() if MILESTONE_FILE.match(archived.stem) else archived.stem
        out.append({"milestone": name, "file": archived.name, "rows": found[::-1]})
    return sorted(out, key=lambda a: a["rows"][0]["date"] if a["rows"] else "", reverse=True), unreadable


def git(cwd: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10)


def worktrees(repo: Path, main: list) -> list:
    """別的 worktree 裡有人正在做的票：內容和主目錄不同，而且那個 worktree 有主目錄沒有的 commit
    或沒提交的改動。只是落後主目錄的舊 worktree 不算。"""
    try:
        listed = git(repo, "worktree", "list", "--porcelain")
        head = git(repo, "rev-parse", "HEAD").stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return []
    if listed.returncode or not head:
        return []
    listed = listed.stdout
    out = []
    for block in listed.strip().split("\n\n"):
        fields = dict(l.split(" ", 1) for l in block.split("\n") if " " in l)
        path = Path(fields.get("worktree", ""))
        if not fields.get("worktree") or path.resolve() == repo.resolve() or not path.is_dir():
            continue
        try:
            behind = git(path, "merge-base", "--is-ancestor", "HEAD", head).returncode == 0
            dirty = git(path, "status", "--porcelain", "--", ".scratch").stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if behind and not dirty.strip():
            continue
        for m in main:
            for mine in m["tickets"]:
                theirs = path / ".scratch" / m["dir"] / "issues" / mine["file"]
                ours = repo / ".scratch" / m["dir"] / "issues" / mine["file"]
                if theirs.is_file() and read(theirs) != read(ours):
                    out.append({"worktree": path.name, "branch": fields.get("branch", "").replace("refs/heads/", ""),
                                "milestone": m["name"], **ticket(theirs)})
    return out


def title_of(repo: Path) -> str:
    for name in ("AGENTS.md", "CLAUDE.md", "README.md"):
        for line in read(repo / name).split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
    return repo.name


def collect(repo: Path) -> dict:
    repo = repo.resolve()
    ms, odd_states = milestones(repo)
    expected = ("docs/roadmap.md", "docs/decisions.md", "docs/progress.md")
    loose = unlisted(repo, ms)
    kept = ticket_notes(repo, [m for m in ms + loose if m["state"] in ("todo", "active")])
    log, step, last, odd_sessions = sessions(repo, kept)
    decided, unreadable = decisions(repo, kept)
    old_sessions, odd_rows = archived_sessions(repo)
    changes, odd_entries = changelog(repo, kept)
    ahead = next_ticket(ms)
    asked = [{"text": q, "ticket": f"{m['name'].split()[0]} 票 {t['number']}", "date": "", "file": f".scratch/{m['dir']}/issues/{t['file']}"}
             for m in ms + loose if m["state"] in ("todo", "active") for t in m["tickets"] for q in t["waiting"]]
    if step.startswith(WAITING):
        asked.append({"text": step[len(WAITING):].strip(), "ticket": last["ticket"], "date": last["date"], "file": "docs/progress.md"})
    if ahead and not step.startswith(WAITING):
        step = f"新 session 下 `{ahead['command']}`"
    return {"name": repo.name, "title": title_of(repo), "path": str(repo), "milestones": ms, "decisions": decided,
            "adrs": adrs(repo), "changelog": changes, "features": features(changes), "sessions": log[-30:][::-1], "next": step, "next_ticket": ahead,
            "waiting": step[len(WAITING):].strip() if step.startswith(WAITING) else "",
            "waiting_from": {"date": last["date"], "ticket": last["ticket"]} if step.startswith(WAITING) else None, "waiting_all": asked,
            "unseen": [d for d in decided if d["decider"] == "Agent 定" and not d["archived"]], "archived_sessions": old_sessions,
            "working": worktrees(repo, ms), "missing": [f for f in expected if not (repo / f).is_file()],
            "unreadable": odd_states + odd_sessions + unreadable + odd_rows + odd_entries, "unlisted": loose}


PAGE = r"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>專案總覽</title>
<script>try { if (localStorage.getItem("dashboard-theme") === "dark") document.documentElement.dataset.theme = "dark"; } catch (e) { /* 讀不到就用淺色 */ }</script>
<style>
/* dashboard 自己的配色，不取 pages/ 的：黑白灰管字、線、表和側欄；琥珀色只表示「現在」，紅色只表示「你上次看過之後變了」。
   深色不跟系統：讀者在側欄切換，寫在 <html data-theme="dark">，記在這個瀏覽器。 */
:root {
  color-scheme: light;
  --paper: #FFFFFF; --tint: #F5F5F5; --rule: #DCDCDC; --ink: #181818; --ink-2: #5E5E5E;
  --rail: #F5F5F5; --rail-ink: #181818; --rail-2: #5E5E5E; --rail-on: #E4E4E4;
  --head: #EDEDED; --head-ink: #181818; --link: #181818;
  --now: #D97706; --now-ink: #9A4D00; --now-bg: #FEF3DC; --on-now: #181818;
  --chg: #C8102E; --chg-bg: #FDECEF; --on-chg: #FFFFFF;
  --font: system-ui, -apple-system, "Segoe UI", "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, "Noto Sans Mono CJK TC", monospace;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #121212; --tint: #181818; --rule: #2E2E2E; --ink: #E8E8E8; --ink-2: #A0A0A0;
  --rail: #181818; --rail-ink: #E8E8E8; --rail-2: #A0A0A0; --rail-on: #2B2B2B;
  --head: #242424; --head-ink: #E8E8E8; --link: #E8E8E8;
  --now: #F0A030; --now-ink: #F5B95C; --now-bg: #33260E; --on-now: #181818;
  --chg: #FF7A8C; --chg-bg: #3A151D; --on-chg: #181818;
}
* { box-sizing: border-box; }
html { text-autospace: normal; -webkit-text-size-adjust: 100%; scrollbar-color: var(--rule) transparent; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 0.9375rem/1.55 var(--font); font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere; display: grid; grid-template-columns: 13.5rem minmax(0, 1fr); min-height: 100vh; accent-color: var(--ink); caret-color: var(--ink); }
::selection { background: var(--ink); color: var(--paper); }
:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
a { color: var(--link); text-underline-offset: 0.2em; }
code { font-family: var(--mono); font-size: 0.875rem; }
button, select, input { font: inherit; color: inherit; }
h1, h2, h3, p, ul, ol { margin: 0; } ul, ol { padding: 0; list-style: none; }

/* 側欄 */
.rail { background: var(--rail); color: var(--rail-ink); padding: 1.75rem 0 1.25rem; display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
.rail .title { font-size: 1.375rem; font-weight: 800; padding: 0 1.5rem 1.25rem; line-height: 1.25; }
.rail a, .rail button { display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; width: 100%; padding: 0.55rem 1.5rem; color: var(--rail-ink);
  text-decoration: none; background: none; border: 0; text-align: left; cursor: pointer; transition: background-color 150ms; }
.rail a:hover, .rail button:hover { background: color-mix(in srgb, var(--rail-on) 45%, transparent); }
.rail [aria-current="page"], .rail [aria-pressed="true"] { background: var(--rail-on); font-weight: 700; }
.rail .n { font-size: 0.8125rem; color: var(--rail-2); font-weight: 400; }
.rail .n .chg { color: var(--on-chg); background: var(--chg); border-radius: 2px; padding: 0 0.35em; margin-left: 0.4em; font-weight: 700; }
.rail .grp { font-size: 0.8125rem; color: var(--rail-2); padding: 1.5rem 1.5rem 0.35rem; }
.rail .theme { margin-top: auto; font-size: 0.8125rem; color: var(--rail-2); }
.rail .live { padding: 0.5rem 1.5rem 0; font-size: 0.8125rem; color: var(--rail-2); line-height: 1.5; }
.rail .live.down { color: var(--rail-ink); font-weight: 700; }

main { padding: 2rem 2.5rem 4rem; min-width: 0; max-width: 84rem; }
h1 { font-size: 2rem; line-height: 1.25; font-weight: 800; }
h1 .ph { display: inline-block; }
h2 { font-size: 1.375rem; line-height: 1.3; font-weight: 800; margin: 2.5rem 0 0.75rem; display: flex; flex-wrap: wrap; gap: 0.25rem 0.9rem; align-items: baseline; }
h2 small, .small { font-size: 0.8125rem; font-weight: 400; color: var(--ink-2); }
h2 a { font-size: 0.875rem; font-weight: 400; margin-left: auto; }
.path { font-size: 0.8125rem; color: var(--ink-2); font-family: var(--mono); margin-bottom: 1.25rem; }
.empty { color: var(--ink-2); padding: 0.75rem 0; }

/* 變了的記號：紅色小方塊加字，留到按「標為看過」 */
.chg-mark { color: var(--chg); font-weight: 700; font-size: 0.8125rem; white-space: nowrap; }
.chg-mark::before { content: ""; display: inline-block; width: 0.5rem; height: 0.5rem; background: var(--chg); margin-right: 0.35em; }
.seen-bar { display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: center; background: var(--chg-bg); padding: 0.6rem 1rem; margin-bottom: 1.5rem; }
.seen-bar b { color: var(--chg); }
.btn { border: 1.5px solid var(--ink); background: var(--paper); border-radius: 3px; padding: 0.2rem 0.8rem; font-weight: 700; font-size: 0.875rem; cursor: pointer; transition: background-color 150ms, color 150ms; }
.btn:hover { background: var(--ink); color: var(--paper); }
.btn:active { transform: translateY(1px); }
.seen-bar .btn { margin-left: auto; }

/* 最上面：該你做的事 */
.next { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 32rem); gap: 1.25rem 2.5rem; align-items: end; padding: 1.25rem 0 1.5rem; border-top: 4px solid var(--ink); border-bottom: 1px solid var(--rule); }
.next.waiting { border-top-color: var(--now); }
.next .why { margin-top: 0.6rem; color: var(--ink-2); max-width: 70ch; text-wrap: balance; }
.next .why b { color: var(--now-ink); }
.next .asks { margin-top: 0.9rem; max-width: 70ch; border-top: 1px solid var(--rule); }
.next h1 code { font-size: 0.7em; }
.cmd-label { font-size: 0.8125rem; color: var(--ink-2); margin-bottom: 0.35rem; }
.cmd { display: flex; align-items: center; gap: 0.75rem; border: 2px solid var(--ink); border-radius: 4px; padding: 0.55rem 0.6rem 0.55rem 0.9rem; }
.cmd code { flex: 1; min-width: 0; }
.cmd .btn { background: var(--ink); color: var(--paper); flex: none; }
.cmd .btn:hover { background: var(--head); border-color: var(--head); color: var(--head-ink); }
.notes { border-bottom: 1px solid var(--rule); padding: 0.6rem 0; }
.notes > summary { cursor: pointer; font-weight: 700; }
.notes li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 0.15rem 1.5rem; padding: 0.5rem 0; border-top: 1px solid var(--rule); }
.notes li:first-child { margin-top: 0.6rem; }
.notes .at { font-family: var(--mono); font-size: 0.8125rem; color: var(--ink-2); }

/* 時刻表 */
.tt-wrap { overflow-x: auto; border-bottom: 3px solid var(--ink); }
table { border-collapse: separate; border-spacing: 0; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 0.55rem 0.9rem; }
.tt { table-layout: fixed; min-width: calc(3.5rem + var(--cols) * 11rem); }
.tt th, .tt td { border-right: 1px solid var(--rule); }
.tt th:last-child, .tt td:last-child { border-right: 0; }
.tt thead th { background: var(--head); color: var(--head-ink); font-weight: 400; font-size: 0.8125rem; line-height: 1.4; }
.tt thead th a { color: inherit; text-decoration: none; display: block; }
.tt thead th a:hover .nm { text-decoration: underline; }
.tt thead b { display: block; font-size: 1.5rem; line-height: 1.15; font-weight: 800; }
.tt thead .cnt { display: flex; justify-content: space-between; gap: 0.5rem; margin-top: 0.35rem; }
.tt thead th.active { background: var(--now); color: var(--on-now); }
.tt thead th.dropped b, .tt thead th.dropped .nm { text-decoration: line-through; }
.tt thead th.loose { background: var(--paper); color: var(--ink); box-shadow: inset 0 0 0 1.5px var(--ink); }
.tt .ord { width: 3.5rem; color: var(--ink-2); font-size: 0.8125rem; position: sticky; left: 0; background: var(--paper); z-index: 1; }
.tt thead .ord { background: var(--head); color: var(--head-ink); }
.tt tbody td { border-bottom: 1px solid var(--rule); height: 3.4rem; }
.tt tbody tr:nth-child(even) td { background: var(--tint); }
.tt tbody tr:last-child td { border-bottom: 0; }
.stop { display: grid; grid-template-columns: 0.75rem minmax(0, 1fr); gap: 0 0.55rem; align-items: baseline; }
/* worktree 的名字整段不斷行，放不下就截掉，完整的在 title */
.wt { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.why .wt { display: inline-block; vertical-align: bottom; }
.stop .sub { grid-column: 2; min-width: 0; font-size: 0.8125rem; color: var(--ink-2); display: flex; flex-wrap: wrap; gap: 0 0.75rem; }
.dot { width: 0.75rem; height: 0.75rem; border-radius: 50%; display: inline-block; box-shadow: inset 0 0 0 2px var(--ink-2); transform: translateY(0.05rem); flex: none; }
.dot.done { background: var(--ink); box-shadow: none; }
.dot.now { background: var(--now); box-shadow: 0 0 0 3px var(--now-bg); }
.dot.dropped { box-shadow: none; background: linear-gradient(var(--ink-2), var(--ink-2)) center / 100% 2px no-repeat; }
.tt td.now { box-shadow: inset 0 3px 0 var(--now), inset 0 -3px 0 var(--now); font-weight: 700; }
.tt td.now .sub { color: var(--now-ink); font-weight: 400; }
.tt td.dropped .t { text-decoration: line-through; color: var(--ink-2); }
.legend { display: flex; flex-wrap: wrap; gap: 0.25rem 1.5rem; font-size: 0.8125rem; color: var(--ink-2); padding-top: 0.6rem; }
.legend span { display: inline-flex; gap: 0.45rem; align-items: center; }

/* 一列一列的清單與表 */
.cols { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 2.5rem; }
.rows li, .rows tr > * { border-bottom: 1px solid var(--rule); }
.rows li { display: grid; grid-template-columns: 5.5rem 5.5rem minmax(0, 1fr); gap: 0.15rem 0.9rem; padding: 0.5rem 0; align-items: baseline; }
.rows li > :nth-child(-n+2), td.k { color: var(--ink-2); font-size: 0.8125rem; }
.rows.two li { grid-template-columns: 5.5rem minmax(0, 1fr); }
.rows.one li { grid-template-columns: minmax(0, 1fr); } .rows.one li > :first-child { color: inherit; font-size: inherit; }
.rows li .chg-mark { grid-column: -2; }
.grid th { white-space: nowrap; font-size: 0.8125rem; color: var(--ink-2); font-weight: 400; border-bottom: 2px solid var(--ink); padding-left: 0; }
.grid td { padding-left: 0; }
td.k { white-space: nowrap; width: 1%; padding-right: 1.25rem; }
td.k.wrap { white-space: normal; width: 9rem; }
.who { white-space: nowrap; }
.who::before { content: ""; display: inline-block; width: 0.6rem; height: 0.6rem; margin-right: 0.4em; box-shadow: inset 0 0 0 1.5px var(--ink-2); }
.who.agent { font-weight: 700; } .who.agent::before { background: var(--ink); box-shadow: none; }
.wide { overflow-x: auto; }

/* 篩選列 */
.filters { display: flex; flex-wrap: wrap; gap: 0.6rem 1rem; align-items: center; margin-bottom: 0.9rem; }
.seg { display: inline-flex; border: 1.5px solid var(--ink); border-radius: 3px; overflow: hidden; }
.seg button { border: 0; background: var(--paper); padding: 0.25rem 0.8rem; cursor: pointer; font-size: 0.875rem; border-right: 1px solid var(--rule); transition: background-color 150ms; }
.seg button:last-child { border-right: 0; }
.seg button:hover { background: var(--tint); }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--paper); font-weight: 700; }
.filters input[type="search"], .filters select { border: 1.5px solid var(--ink); background: var(--paper); border-radius: 3px; padding: 0.25rem 0.6rem; font-size: 0.875rem; min-width: 0; }
.filters input::placeholder { color: var(--ink-2); opacity: 1; }
.filters label { display: inline-flex; gap: 0.4rem; align-items: center; font-size: 0.875rem; }

/* 里程碑一頁：左邊車次，右邊內容 */
.ms { display: grid; grid-template-columns: 11rem minmax(0, 1fr); gap: 0.5rem 2rem; padding: 1.25rem 0 1.5rem; border-top: 3px solid var(--ink); }
.ms.active { border-top-color: var(--now); }
.ms .id b { font-size: 2rem; line-height: 1.1; font-weight: 800; display: block; }
.ms .id .st { margin-top: 0.4rem; font-weight: 700; }
.ms.active .id .st { color: var(--now-ink); }
.ms .goal { font-size: 1.125rem; font-weight: 700; }
.ms .detail { margin-top: 0.35rem; max-width: 70ch; color: var(--ink-2); }
.ms details { margin-top: 0.75rem; } .ms details .wide { margin-top: 0.25rem; } .ms summary, .fold > summary { cursor: pointer; color: var(--link); }
.ms .scope { margin-top: 0.4rem; padding-left: 1.2rem; list-style: disc; color: var(--ink-2); }
.ms table { margin-top: 0.75rem; }
.fold { border-bottom: 1px solid var(--rule); padding: 0.6rem 0; }
.fold > summary { color: var(--ink); font-weight: 700; display: flex; flex-wrap: wrap; gap: 0 0.9rem; align-items: baseline; }
.fold[open] > summary { margin-bottom: 0.4rem; }
.kind { font-size: 0.8125rem; color: var(--ink-2); margin: 0.9rem 0 0.1rem; }
.pending { font-size: 0.8125rem; color: var(--ink-2); white-space: nowrap; }

/* 半邊視窗：側欄收到頂端 */
@media (max-width: 62rem) {
  body { display: block; }
  .rail { position: static; height: auto; overflow: visible; padding: 0.75rem 1.25rem 0; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 0.25rem 1.25rem; align-items: baseline; }
  .rail .title { padding: 0; font-size: 1.125rem; }
  .rail nav { grid-column: 1 / -1; grid-row: 2; display: flex; overflow-x: auto; margin: 0 -1.25rem; padding: 0 0.75rem; scrollbar-width: none; }
  .rail a, .rail button { width: auto; padding: 0.5rem 0.75rem; white-space: nowrap; }
  .rail [aria-current="page"] { box-shadow: inset 0 -3px 0 var(--ink); }
  .rail .grp { display: none; }
  .rail .repos { display: flex; overflow-x: auto; }
  .rail .repos button { padding: 0.15rem 0.6rem; border-radius: 3px; font-size: 0.875rem; }
  .rail .theme { margin: 0; padding: 0.15rem 0.6rem; }
  .rail .live { grid-column: 1 / -1; grid-row: 3; margin: 0; padding: 0 0 0.4rem; } .rail .live br { display: none; }
  .rail nav { margin-bottom: 0.4rem; }
  main { padding: 1.25rem 1.25rem 3rem; }
  h1 { font-size: 1.625rem; }
  .next, .cols { grid-template-columns: minmax(0, 1fr); }
  .ms { grid-template-columns: minmax(0, 1fr); } .ms .id { display: flex; flex-wrap: wrap; gap: 0 0.9rem; align-items: baseline; } .ms .id .st { margin: 0; }
}
@media (max-width: 34rem) {
  .rail { grid-template-columns: minmax(0, 1fr) auto; } .rail .repos { grid-column: 1 / -1; grid-row: 4; padding-bottom: 0.4rem; }
  .rows li { grid-template-columns: 5.5rem minmax(0, 1fr); } .rows li > :nth-child(3) { grid-column: 1 / -1; }
  .rows.two li > :nth-child(2) { grid-column: 2; }
}
</style></head><body>
<div class="rail">
  <div class="title" id="title">專案總覽</div>
  <nav id="views" aria-label="分頁"></nav>
  <div class="repos" id="repos"></div>
  <button class="theme" id="theme" type="button"></button>
  <div class="live" id="live" role="status"></div>
</div>
<main id="app"></main>
<script id="data" type="application/json">__DATA__</script>
<script>
"use strict";
let DATA = JSON.parse(document.getElementById("data").textContent);
const LIVE = __LIVE__;
const VIEWS = [["now", "現在"], ["milestones", "里程碑"], ["changes", "功能與變更"], ["decisions", "決策"], ["log", "紀錄"]];
const view = { decider: "", milestone: "", query: "", archived: false, feature: "", repeated: false, by: "version", state: "", open: {} };
const el = (tag, attrs, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") n.className = v; else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) n.append(kid);
  return n;
};
const STATE = { done: "已驗收", active: "進行中", todo: "未開工", dropped: "不做" };
const KIND = { Added: "新增", Changed: "修改", Deprecated: "將移除", Removed: "移除", Fixed: "修正", Security: "安全" };
const versionName = v => (v === "Unreleased" ? "未發版" : v);
const command = text => String(text || "").split(/`([^`]*)`/).map((p, i) => (i % 2 ? el("code", {}, p) : p));
const bare = t => t.title.replace(new RegExp("^" + t.number + "\\s*[:：.、]\\s*"), "");
/* 中文在哪個字都能斷行：大標切成一句一句，換行只發生在標點後面 */
const phrases = parts => parts.map(p => (typeof p === "string" ? p.split(/(?<=[，；：。？！、])/).filter(Boolean).map(x => el("span", { class: "ph" }, x)) : p));
const short = date => (date || "").slice(5) || "—";

/* 網址的 # 記著哪個 repo、哪一頁：瀏覽器的上一頁回得去 */
function route() {
  const [a, b] = location.hash.slice(1).split("/");
  const project = Math.min(Math.max(parseInt(a, 10) || 0, 0), DATA.projects.length - 1);
  return { project, name: VIEWS.some(v => v[0] === b) ? b : "now" };
}
const href = (project, name) => `#${project}/${name}`;

/* 「你上次看過之後變了」：每樣東西記一個指紋，存在這個瀏覽器；按「標為看過」才更新 */
function prints(p) {
  const out = { "next": p.waiting_all.map(a => a.text).join("|") || p.next };
  for (const m of p.milestones.concat(p.unlisted)) {
    out["m:" + m.name] = m.state;
    for (const t of m.tickets) out[`t:${m.dir}/${t.file}`] = `${t.status}|${t.checked}/${t.boxes}`;
  }
  for (const d of p.decisions) out[`d:${d.date}|${d.label}|${d.text}`] = "1";
  for (const s of p.sessions) out[`s:${s.date}|${s.ticket}|${s.result}`] = "1";
  for (const v of p.changelog) for (const e of v.entries) out[`c:${v.version}|${e.feature}|${e.text}`] = "1";
  return out;
}
const store = { get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* 存不了就當每次都是第一次看 */ } } };
let seen = {}, now = {};
function loadSeen(p) {
  now = prints(p); seen = store.get("dashboard-seen:" + p.path);
  if (!seen) { seen = now; store.set("dashboard-seen:" + p.path, now); }
}
const changed = key => seen[key] !== now[key];
const mark = (key, word) => (changed(key) ? el("span", { class: "chg-mark" }, word || (key in seen ? "變了" : "新的")) : null);
function tally() {
  const of = prefix => Object.keys(now).filter(k => k.startsWith(prefix) && changed(k)).length;
  return { now: (changed("next") ? 1 : 0), milestones: of("t:") + of("m:"), changes: of("c:"), decisions: of("d:"), log: of("s:") };
}

function copyButton(text, code) {
  const b = el("button", { class: "btn", type: "button", onclick: async () => {
    try { await navigator.clipboard.writeText(text); b.textContent = "已複製"; }
    catch (e) { getSelection().selectAllChildren(code); b.textContent = "已選取，按複製鍵"; }
    setTimeout(() => { b.textContent = "複製"; }, 1600);
  } }, "複製");
  return b;
}
function ticketWord(t) { return t.done ? "完成" : t.dropped ? "不做" : t.checked ? `驗收 ${t.checked} / ${t.boxes}` : "未開始"; }
function waitsFor(m, t) {
  const closed = new Set(m.tickets.filter(x => x.done || x.dropped).map(x => x.number)), known = new Set(m.tickets.map(x => x.number));
  return t.done || t.dropped ? [] : t.blocked.filter(b => known.has(b) && !closed.has(b));
}
const workWord = w => (w.done ? "做完，等合併" : w.boxes ? `驗收 ${w.checked} / ${w.boxes}` : "進行中");
const workOn = (p, m, t) => p.working.find(w => w.milestone === m.name && w.file === t.file);
function counts(m) { const live = m.tickets.filter(t => !t.dropped); return [live.filter(t => t.done).length, live.length]; }
function isNow(p, m, t) {
  return !!workOn(p, m, t) || (p.next_ticket && p.next_ticket.dir === m.dir && p.next_ticket.file === t.file);
}

function nextBlock(p) {
  const t = p.next_ticket, code = t ? el("code", {}, t.command) : null, asks = p.waiting_all, ask = asks[0];
  const from = a => a.file === "docs/progress.md" ? ["docs/progress.md 最後一列留的", el("span", { class: "wt" }, `（${a.date}　${a.ticket}）`)] : [`${a.ticket} 留在票上的`];
  return el("section", { class: "next" + (ask ? " waiting" : "") },
    el("div", {},
      el("h1", {}, phrases(ask ? command(ask.text) : t ? [`做 ${t.milestone} 票 ${t.number}：${bare(t)}`] : p.next ? command(p.next) : ["還沒有下一步"])),
      el("p", { class: "why" }, ask ? [el("b", {}, asks.length > 1 ? `等你決定，共 ${asks.length} 題。` : "等你決定。"), from(ask), "；開一個新的 session 回答。"]
        : t ? "開一個新的 session，貼上這條指令。" : p.next ? "這是 docs/progress.md 最後一列寫的下一步。" : "docs/progress.md 還沒有 session 紀錄；第一張票做完就會出現在這裡。", " ", mark("next")),
      asks.length > 1 ? el("ul", { class: "rows two asks" }, asks.slice(1).map(a => el("li", {}, el("span", {}, a.file === "docs/progress.md" ? "progress.md" : a.ticket), el("span", {}, a.text)))) : null),
    t ? el("div", {}, el("div", { class: "cmd-label" }, p.waiting ? `答完之後的下一步：${t.milestone} 票 ${t.number} ${bare(t)}` : ask ? `這張不用等，可以先做：${t.milestone} 票 ${t.number} ${bare(t)}` : "新 session 的指令"),
      el("div", { class: "cmd" }, code, copyButton(t.command, code))) : null);
}
function notes(p) {
  return [
    p.missing.length ? el("div", { class: "notes" }, el("b", {}, "讀不到的檔："), p.missing.join("、") + "。這個 repo 還沒照 project-init 的骨架，對應的區塊會是空的。") : null,
    p.unreadable.length ? fold(p.name + "/unreadable", false, [`讀不到的行：${p.unreadable.length} 行不是約定的寫法，沒有列進來`],
      el("ul", {}, p.unreadable.map(u => el("li", {}, el("span", {}, u.text), el("span", { class: "at" }, `${u.file}:${u.line}`), el("span", { class: "small" }, u.why)))), "notes") : null];
}
function fold(id, openByDefault, summary, body, cls) {
  const box = el("details", { class: cls || "fold", open: view.open[id] ?? openByDefault }, el("summary", {}, summary), body);
  box.addEventListener("toggle", () => { view.open[id] = box.open; });
  return box;
}
function timetable(p, project) {
  const cols = p.milestones.map(m => [m, false]).concat(p.unlisted.map(m => [m, true]));
  if (!cols.length) return el("div", { class: "empty" }, "docs/roadmap.md 的〈里程碑〉還沒有表；照 project-init 的骨架加上之後，每個里程碑會是這裡的一欄。");
  const depth = Math.max(0, ...cols.map(([m]) => m.tickets.length));
  const head = ([m, loose]) => { const [done, total] = counts(m), [id, ...rest] = m.name.split(/\s+/);
    return el("th", { scope: "col", class: loose ? "loose" : m.state }, el("a", { href: href(project, "milestones") },
      el("b", {}, id), el("span", { class: "nm" }, rest.join(" ") || (loose ? "不在 roadmap" : "")),
      el("span", { class: "cnt" }, el("span", {}, total ? `${done} / ${total}` : "還沒拆票"), el("span", {}, loose ? "不在 roadmap" : STATE[m.state]), mark("m:" + m.name)))); };
  const cell = (m, t) => { if (!t) return el("td", {});
    const here = isNow(p, m, t), w = workOn(p, m, t), wait = waitsFor(m, t);
    const sub = [w ? workWord(w) : !t.done && !t.dropped && t.checked ? `驗收 ${t.checked} / ${t.boxes}` : null, t.dropped ? "不做" : null,
      w ? el("span", { class: "wt", title: "worktree " + w.worktree }, "在 " + w.worktree) : null, wait.length ? "等票 " + wait.join("、") : null].filter(Boolean);
    return el("td", { class: here ? "now" : t.dropped ? "dropped" : "" }, el("div", { class: "stop" },
      el("span", { class: "dot " + (t.done ? "done" : here ? "now" : t.dropped ? "dropped" : ""), role: "img", "aria-label": ticketWord(t) }),
      el("span", { class: "t" }, bare(t)),
      sub.length || changed(`t:${m.dir}/${t.file}`) ? el("span", { class: "sub" }, sub.map(s => (typeof s === "string" ? el("span", {}, s) : s)), mark(`t:${m.dir}/${t.file}`)) : null)); };
  return [el("div", { class: "tt-wrap", id: "tt" }, el("table", { class: "tt", style: `--cols:${cols.length}` },
    el("thead", {}, el("tr", {}, el("th", { class: "ord", scope: "col" }, "票"), cols.map(head))),
    el("tbody", {}, Array.from({ length: depth }, (_, i) => el("tr", {}, el("td", { class: "ord" }, String(i + 1).padStart(2, "0")), cols.map(([m]) => cell(m, m.tickets[i]))))))),
    depth ? el("div", { class: "legend" }, el("span", {}, el("i", { class: "dot done" }), "做完"), el("span", {}, el("i", { class: "dot now" }), "現在"),
      el("span", {}, el("i", { class: "dot" }), "還沒"), el("span", {}, el("i", { class: "dot dropped" }), "不做")) : null];
}
function decisionRow(d) {
  return el("li", {}, el("span", {}, short(d.date)), el("span", {}, d.label || d.milestone), el("span", {}, d.text, " ", mark(`d:${d.date}|${d.label}|${d.text}`, "新的")));
}
function sessionRows(list) {
  return el("ul", { class: "rows" }, list.map(s => el("li", {}, el("span", {}, short(s.date)), el("span", {}, s.ticket), el("span", {}, s.result, " ", mark(`s:${s.date}|${s.ticket}|${s.result}`, "新的")))));
}
function nowView(p, project) {
  const [done, total] = p.milestones.map(counts).reduce((a, c) => [a[0] + c[0], a[1] + c[1]], [0, 0]);
  return [nextBlock(p), notes(p),
    el("h2", {}, "里程碑時刻表", total ? el("small", {}, `${done} / ${total} 張票做完；一欄一個里程碑，琥珀色的線是現在`) : null), timetable(p, project),
    el("div", { class: "cols" },
      el("div", {}, el("h2", {}, "Agent 自己定、你還沒看的", el("small", {}, `${p.unseen.length} 條`), el("a", { href: href(project, "decisions") }, "全部決策")),
        p.unseen.length ? el("ul", { class: "rows" }, p.unseen.slice(0, 6).map(decisionRow)) : el("div", { class: "empty" }, "沒有。Agent 做票時自己定的決定會先列在這裡。"),
        p.unseen.length > 6 ? el("p", { class: "small", style: "margin-top:.5rem" }, `還有 ${p.unseen.length - 6} 條，在「決策」選「Agent 定」。`) : null),
      el("div", {},
        p.working.length ? [el("h2", {}, "正在做", el("small", {}, `${p.working.length} 個 worktree`)),
          el("ul", { class: "rows" }, p.working.map(w => el("li", {}, el("span", {}, w.worktree), el("span", {}, w.milestone.split(/\s+/)[0] + " " + w.number),
            el("span", {}, bare(w), "　", el("span", { class: "pending" }, workWord(w))))))] : null,
        el("h2", {}, "最近的 session", el("a", { href: href(project, "log") }, "全部紀錄")),
        p.sessions.length ? sessionRows(p.sessions.slice(0, 4)) : el("div", { class: "empty" }, "還沒有 session 紀錄。")))];
}
function milestonesView(p) {
  const all = p.milestones.concat(p.unlisted), list = all.filter(m => !view.state || m.state === view.state);
  const seg = (label, value) => el("button", { type: "button", "aria-pressed": String(view.state === value), onclick: () => { view.state = value; render(); } },
    `${label} ${value ? all.filter(m => m.state === value).length : all.length}`);
  const block = m => { const [done, total] = counts(m), [id, ...rest] = m.name.split(/\s+/), loose = p.unlisted.includes(m);
    return el("section", { class: "ms " + m.state },
      el("div", { class: "id" }, el("b", {}, id), el("span", {}, rest.join(" ")), el("div", { class: "st" }, loose ? "不在 roadmap" : STATE[m.state], total ? `　${done} / ${total}` : "", " ", mark("m:" + m.name))),
      el("div", {}, m.goal ? el("p", { class: "goal" }, m.goal) : null, el("p", { class: "detail" }, m.detail || m.status),
        m.scope.length ? fold(`${p.name}/scope/${m.name}`, false, `範圍 ${m.scope.length} 項`, el("ul", { class: "scope" }, m.scope.map(s => el("li", {}, s))), "more") : null,
        m.tickets.length ? (body => (m.state !== "active" ? fold(`${p.name}/tickets/${m.name}`, false, `${m.tickets.length} 張票`, body, "more") : body))(el("div", { class: "wide" }, el("table", { class: "grid rows" },
          el("thead", {}, el("tr", {}, ["票", "標題", "狀態", "等誰"].map(h => el("th", { scope: "col" }, h)))),
          el("tbody", {}, m.tickets.map(t => { const wait = waitsFor(m, t), here = isNow(p, m, t), w = workOn(p, m, t);
            return el("tr", {}, el("td", { class: "k" }, t.number),
              el("td", {}, el("span", { class: "dot " + (t.done ? "done" : here ? "now" : t.dropped ? "dropped" : ""), style: "margin-right:.55rem" }), bare(t)),
              el("td", { class: "k" }, w ? `${workWord(w)}　在 ${w.worktree}` : ticketWord(t), " ", mark(`t:${m.dir}/${t.file}`)), el("td", { class: "k" }, wait.length ? "票 " + wait.join("、") : "")); })))))
          : el("p", { class: "empty" }, "還沒拆票。"))); };
  return [el("h1", {}, "里程碑"), el("div", { class: "filters", style: "margin-top:1rem" },
      el("div", { class: "seg", role: "group", "aria-label": "狀態" }, seg("全部", ""), seg("進行中", "active"), seg("未開工", "todo"), seg("已驗收", "done"))),
    list.length ? list.map(block) : el("div", { class: "empty" }, all.length ? "這個狀態沒有里程碑。" : "docs/roadmap.md 的〈里程碑〉還沒有表。")];
}
function entry(e, lead) {
  return el("li", {}, lead ? el("span", {}, lead) : null,
    el("span", {}, e.feature ? el("b", {}, e.feature + "：") : null, e.text, " ", e.pending ? el("span", { class: "pending" }, `還在票上（${e.pending}），待組裝`) : null, " ", e.key ? mark(e.key, "新的") : null));
}
function changesView(p) {
  const seg = (label, value) => el("button", { type: "button", "aria-pressed": String(view.by === value), onclick: () => { view.by = value; render(); } }, label);
  const head = [el("h1", {}, "功能與變更"), el("div", { class: "filters", style: "margin-top:1rem" },
    el("div", { class: "seg", role: "group", "aria-label": "排法" }, seg("依版本", "version"), seg(`依功能 ${p.features.length}`, "feature")),
    view.by === "feature" ? [el("label", {}, el("input", { type: "checkbox", checked: view.repeated, onchange: e => { view.repeated = e.target.checked; render(); } }), `只看改過不只一次的 ${p.features.filter(f => f.entries.length > 1).length}`),
      el("input", { type: "search", placeholder: "搜尋功能", "aria-label": "搜尋功能", value: view.feature, id: "fq", oninput: e => { view.feature = e.target.value; render(); } })] : null)];
  if (!p.changelog.length) return [head[0], el("div", { class: "empty" }, "這個 repo 沒有 CHANGELOG.md；有了之後，每個版本會是這裡的一段。")];
  if (view.by === "version") return [head, p.changelog.map(v => { const waiting = v.entries.filter(e => e.pending).length;
    return fold(`${p.name}/v/${v.version}`, v.version === "Unreleased", [versionName(v.version), el("span", { class: "small" }, `${v.date ? v.date + "　" : ""}${v.entries.length} 條` + (waiting ? `，${waiting} 條還在票上` : ""))],
      v.entries.length ? Object.keys(KIND).filter(k => v.entries.some(e => e.kind === k)).map(k => [el("div", { class: "kind" }, `${KIND[k]}（${k}）`),
        el("ul", { class: "rows one" }, v.entries.filter(e => e.kind === k).map(e => entry({ ...e, key: `c:${v.version}|${e.feature}|${e.text}` })))]) : el("div", { class: "empty" }, "還沒有條目。")); })];
  const needle = view.feature.toLowerCase();
  const list = p.features.filter(f => (!view.repeated || f.entries.length > 1) && (!needle || (f.name + f.entries.map(e => e.text).join(" ")).toLowerCase().includes(needle)));
  return [head, list.length ? list.slice(0, 120).map(f => fold(`${p.name}/f/${f.name}`, f.entries.length > 1 && list.length <= 12,
      [f.name, el("span", { class: "small" }, `${versionName(f.since)} 起　${f.entries.length} 條`)],
      el("ul", { class: "rows" }, f.entries.map(e => el("li", {}, el("span", {}, versionName(e.version)), el("span", {}, KIND[e.kind]),
        el("span", {}, e.text, " ", e.pending ? el("span", { class: "pending" }, `還在票上（${e.pending}），待組裝`) : null))))))
      : el("div", { class: "empty" }, p.features.length ? "沒有符合的功能；清掉搜尋或取消勾選。" : "CHANGELOG.md 還沒有寫成「**功能**：一句」的條目。"),
    list.length > 120 ? el("p", { class: "small" }, `只顯示最近改過的 120 個，共 ${list.length} 個；用搜尋縮小範圍。`) : null];
}
function decisionsView(p) {
  const pool = p.decisions.filter(d => view.archived || view.milestone || view.query || !d.archived);
  const list = pool.filter(d => (!view.decider || d.decider === view.decider) && (!view.milestone || d.milestone === view.milestone)
    && (!view.query || (d.text + d.label + d.milestone + d.date).toLowerCase().includes(view.query.toLowerCase())));
  const count = who => pool.filter(d => d.decider === who).length, archived = p.decisions.filter(d => d.archived).length;
  const names = [...new Set(p.decisions.map(d => d.milestone).filter(Boolean))];
  const seg = (label, value) => el("button", { type: "button", "aria-pressed": String(view.decider === value), onclick: () => { view.decider = value; render(); } }, label);
  return [el("h1", {}, "決策"), el("div", { class: "filters", style: "margin-top:1rem" },
      el("div", { class: "seg", role: "group", "aria-label": "決定者" }, seg(`全部 ${pool.length}`, ""), seg(`Agent 定 ${count("Agent 定")}`, "Agent 定"),
        seg(`使用者同意 ${count("使用者同意")}`, "使用者同意"), seg(`使用者定 ${count("使用者定")}`, "使用者定"), count("未標") ? seg(`未標 ${count("未標")}`, "未標") : null),
      el("select", { "aria-label": "里程碑", onchange: e => { view.milestone = e.target.value; render(); } },
        el("option", { value: "" }, "所有里程碑"), names.map(n => el("option", { value: n, selected: view.milestone === n }, n))),
      el("input", { type: "search", placeholder: "搜尋決策", "aria-label": "搜尋決策", value: view.query, id: "q", oninput: e => { view.query = e.target.value; render(); } }),
      archived ? el("label", {}, el("input", { type: "checkbox", checked: view.archived, onchange: e => { view.archived = e.target.checked; render(); } }), `含已封存的 ${archived} 條`) : null),
    list.length ? el("div", { class: "wide" }, el("table", { class: "grid rows" },
      el("thead", {}, el("tr", {}, ["日期", "里程碑", "決定者", "決定"].map(h => el("th", { scope: "col" }, h)))),
      el("tbody", {}, list.slice(0, 300).map(d => el("tr", {}, el("td", { class: "k" }, d.date), el("td", { class: "k" }, d.milestone),
        el("td", { class: "k" }, el("span", { class: "who" + (d.decider === "Agent 定" ? " agent" : "") }, d.decider)),
        el("td", {}, d.label && d.label !== d.milestone ? el("span", { class: "small" }, d.label + "　") : null, d.text, " ", mark(`d:${d.date}|${d.label}|${d.text}`, "新的")))))))
      : el("div", { class: "empty" }, p.decisions.length ? "沒有符合的決策；放寬篩選或清掉搜尋。" : "還沒有決策紀錄；寫進 docs/decisions.md 的〈紀錄〉或票的 Comments 就會出現。"),
    list.length > 300 ? el("p", { class: "small" }, `只顯示最新的 300 條，共 ${list.length} 條；用篩選縮小範圍。`) : null,
    el("h2", {}, "架構決定（ADR）", el("small", {}, `${p.adrs.length} 份`)),
    p.adrs.length ? el("ul", { class: "rows two" }, p.adrs.map(a => el("li", {}, el("span", {}, a.number), el("span", {}, a.title, "　", el("span", { class: "small" }, "docs/adr/" + a.file)))))
      : el("div", { class: "empty" }, "docs/adr/ 還沒有 ADR。")];
}
function logView(p) {
  return [el("h1", {}, "紀錄"), el("h2", {}, "最近的 session", el("small", {}, `最新的 ${p.sessions.length} 列`)),
    p.sessions.length ? sessionRows(p.sessions) : el("div", { class: "empty" }, "還沒有 session 紀錄；docs/progress.md 的表或票的 Comments 有了就會出現。"),
    p.archived_sessions.length ? el("h2", {}, "已封存的") : null,
    p.archived_sessions.map(a => fold(`${p.name}/sessions/${a.file}`, false, [a.milestone, el("span", { class: "small" }, `${a.rows.length} 列　docs/archive/${a.file}`)],
      el("ul", { class: "rows" }, a.rows.map(s => el("li", {}, el("span", {}, short(s.date)), el("span", {}, s.ticket), el("span", {}, s.result))))))];
}
const PAGES = { now: nowView, milestones: milestonesView, changes: changesView, decisions: decisionsView, log: logView };
let shown = "";
function render() {
  const r = route(), p = DATA.projects[r.project];
  loadSeen(p);
  const diff = tally(), total = Object.values(diff).reduce((a, b) => a + b, 0);
  const size = { now: "", milestones: p.milestones.length, changes: p.changelog.reduce((a, v) => a + v.entries.length, 0), decisions: p.decisions.length, log: "" };
  document.getElementById("title").textContent = p.title;
  document.title = `${p.title}：${VIEWS.find(v => v[0] === r.name)[1]}`;
  document.getElementById("views").replaceChildren(...VIEWS.map(([name, label]) => el("a", { href: href(r.project, name), "aria-current": name === r.name ? "page" : false },
    label, el("span", { class: "n" }, size[name], diff[name] ? el("span", { class: "chg" }, `${diff[name]} 變了`) : null))));
  document.getElementById("repos").replaceChildren(...(DATA.projects.length > 1 ? [el("div", { class: "grp" }, "Repo"),
    DATA.projects.map((q, i) => el("button", { type: "button", "aria-pressed": String(i === r.project), onclick: () => { view.milestone = ""; location.hash = href(i, r.name); } }, q.name))].flat() : []));
  const typing = ["q", "fq"].includes(document.activeElement && document.activeElement.id) ? document.activeElement.id : "";
  const pos = typing ? document.activeElement.selectionStart : 0, tt = document.getElementById("tt"), left = tt ? tt.scrollLeft : null;
  const key = r.project + "/" + r.name;
  document.getElementById("app").replaceChildren(...[
    total ? el("div", { class: "seen-bar" }, el("span", {}, el("b", {}, `你上次看過之後有 ${total} 處變了`), "　紅色記號標著是哪幾處。"),
      el("button", { class: "btn", type: "button", onclick: () => { store.set("dashboard-seen:" + p.path, now); render(); } }, "標為看過")) : null,
    PAGES[r.name](p, r.project), el("p", { class: "path", style: "margin:2.5rem 0 0" }, p.path)].flat(Infinity).filter(Boolean));
  if (typing && document.getElementById(typing)) { const input = document.getElementById(typing); input.focus(); input.setSelectionRange(pos, pos); }
  const table = document.getElementById("tt");
  if (table) { if (left != null && shown === key) table.scrollLeft = left;
    else { const at = table.querySelector("th.active"); if (at) table.scrollLeft = Math.max(0, at.offsetLeft - 56 - (table.clientWidth - 56 - at.offsetWidth) / 2); } }
  if (shown && shown !== key) scrollTo(0, 0);
  shown = key;
}
const themeButton = document.getElementById("theme");
function setTheme(dark) {
  if (dark) document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("dashboard-theme", dark ? "dark" : "light"); } catch (e) { /* 存不了就只管這一次 */ }
  themeButton.textContent = dark ? "換成淺色" : "換成深色";
}
themeButton.addEventListener("click", () => setTheme(document.documentElement.dataset.theme !== "dark"));
setTheme(document.documentElement.dataset.theme === "dark");
addEventListener("hashchange", render);
render();
const live = document.getElementById("live");
if (!LIVE) live.append("靜態頁，停在產生的時候。", el("br"), "不加 static 才會自動更新。");
else {
  let last = JSON.stringify(DATA);
  const tick = async () => {
    try {
      const text = await (await fetch("data.json", { cache: "no-store" })).text();
      if (text !== last) { last = text; DATA = JSON.parse(text); render(); }
      live.className = "live"; live.replaceChildren("自動更新中，", el("br"), "上次讀取 " + new Date().toLocaleTimeString());
    } catch (e) { live.className = "live down"; live.replaceChildren("讀不到伺服器，", el("br"), "畫面停在上次的內容。"); }
  };
  tick(); setInterval(tick, 3000);
}
</script></body></html>
"""


def data(repos: list) -> dict:
    return {"projects": [collect(r) for r in repos]}


def render(payload: dict, live: bool = False) -> str:
    """live：頁面要不要每 3 秒向伺服器重讀 data.json；只有 --serve 的頁是。"""
    page = PAGE.replace("__LIVE__", "true" if live else "false")
    # </script> 不能出現在內嵌的 JSON 裡
    return page.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))


def handler(repos: list):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.split("?")[0] == "/data.json":
                body, kind = json.dumps(data(repos), ensure_ascii=False).encode("utf-8"), "application/json"
            elif self.path.split("?")[0] in ("/", "/index.html"):
                body, kind = render(data(repos), live=True).encode("utf-8"), "text/html"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return Handler


def server(repos: list, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), handler(repos))


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="從 repo 的固定文件產生專案總覽頁")
    parser.add_argument("repos", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    missing = [str(r) for r in args.repos if not r.is_dir()]
    if missing:
        print("找不到目錄：" + "、".join(missing), file=sys.stderr)
        return 1
    if args.serve:
        httpd = server(args.repos, args.host, args.port)
        print(f"http://{args.host}:{httpd.server_address[1]}/", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    out = args.output or Path(tempfile.mkdtemp(prefix="dashboard-")) / "dashboard.html"
    out.write_text(render(data(args.repos)), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
