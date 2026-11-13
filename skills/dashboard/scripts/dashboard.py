"""從 repo 的固定文件產生專案總覽頁：里程碑與票的進度、決策、ADR、最近的 session。

    python dashboard.py <repo>... [-o <輸出.html>]          # 產生一頁靜態 HTML，印出路徑
    python dashboard.py --serve [--port 8765] [--host 127.0.0.1] <repo>...
                                                           # 起本機伺服器，印出網址；頁面每 3 秒重讀一次

讀的檔（project-init 的骨架；缺的列在頁面的「讀不到的檔」，其餘照樣顯示）：
  docs/roadmap.md      〈里程碑〉的表：里程碑、目標、狀態（看開頭的詞：未開工、進行中、已驗收、不做）
  .scratch/<目錄>/     spec.md 的〈目標〉〈範圍〉；issues/*.md 的標題、Status:、勾選框
                       有 issues/ 卻不在里程碑表裡的目錄，另列在「不在 roadmap 的工作」
  docs/decisions.md    〈紀錄〉每條：日期、里程碑、決定者、內容（進行中的里程碑）
  docs/archive/*.md    〈決定〉：已驗收里程碑的決定，里程碑取檔名；舊骨架的段名〈偏差與決定〉也讀
                       這兩處以 `- ` 開頭卻不是 `- YYYY-MM-DD …` 的行，列在頁面的「讀不到的行」
  docs/adr/*.md        編號與標題
  docs/progress.md     〈Session 紀錄〉的表；最後一列的「下一步」
  git worktree list    別的 worktree 裡和主目錄不同的票，當成「進行中」

資料每次請求時現讀，不存快取。頁面不載入任何外部資源。只用標準函式庫。
"""

import argparse
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


def numbered_table(lines) -> list:
    """第一張表的每一列：(行號, {表頭欄名: 內容})。"""
    rows = []
    for number, line in lines:
        if line.strip().startswith("|"):
            rows.append((number, [c.strip().replace("\\|", "|") for c in CELL_SPLIT.split(line.strip().strip("|"))]))
        elif rows:
            break
    if len(rows) < 2:
        return []
    head = rows[0][1]
    return [(n, dict(zip(head, r))) for n, r in rows[2:] if len(r) == len(head)]


def table(lines) -> list:
    """第一張表的每一列，以表頭欄名為 key。"""
    return [row for _, row in numbered_table(list(enumerate(lines, 1)))]


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
    status = ""
    for l in lines:
        if l.startswith("## "):
            break
        m = STATUS.match(l)
        if m:
            status = m.group(1).strip("* ")
            break
    boxes = [m.group(1) != " " for m in map(CHECKBOX.match, lines) if m]
    return {"file": path.name, "title": plain(title), "status": status, "done": status.lower().startswith("done"),
            "dropped": bool(DROPPED.match(status)), "checked": sum(boxes), "boxes": len(boxes)}


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
    for number, row in numbered_table(numbered_sections(read(repo / "docs/roadmap.md")).get("里程碑", [])):
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


def decisions(repo: Path) -> tuple:
    """(決定, 讀不到的行)。封存檔裡的決定，里程碑是檔名（`m1.5.md` → `M1.5`）：早期的條目開頭常是「票 05」「拆票」。"""
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
    return sorted(out, key=lambda d: d["date"], reverse=True), unreadable


def adrs(repo: Path) -> list:
    out = []
    for p in sorted((repo / "docs/adr").glob("*.md")) if (repo / "docs/adr").is_dir() else []:
        m = ADR_FILE.match(p.name)
        if m:
            title = next((l.lstrip("# ").strip() for l in read(p).split("\n") if l.startswith("# ")), p.stem)
            out.append({"number": m.group(1), "title": plain(title), "file": p.name})
    return out


def sessions(repo: Path) -> list:
    rows = table(sections(read(repo / "docs/progress.md")).get("Session 紀錄", []))
    return [{"date": r.get("日期", ""), "ticket": plain(r.get("票", "")), "result": plain(r.get("結果", "")),
             "next": r.get("下一步", "").strip()} for r in rows]


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
    log = sessions(repo)
    decided, unreadable = decisions(repo)
    return {"name": repo.name, "title": title_of(repo), "path": str(repo), "milestones": ms, "decisions": decided,
            "adrs": adrs(repo), "sessions": log[-30:][::-1], "next": log[-1]["next"] if log else "",
            "working": worktrees(repo, ms), "missing": [f for f in expected if not (repo / f).is_file()],
            "unreadable": odd_states + unreadable, "unlisted": unlisted(repo, ms)}


PAGE = r"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>專案總覽</title>
<style>
:root { color-scheme: light dark;
  --paper: oklch(0.985 0.004 85); --panel: oklch(0.962 0.006 85); --rule: oklch(0.88 0.008 85);
  --ink: oklch(0.25 0.012 260); --ink-2: oklch(0.47 0.012 260); --accent: oklch(0.5 0.15 255);
  --ins-bg: oklch(0.93 0.055 165); --ins-ink: oklch(0.38 0.1 165); --ins-bar: oklch(0.6 0.13 165);
  --note-bg: oklch(0.955 0.04 85); --note-ink: oklch(0.4 0.07 70); --note-bar: oklch(0.72 0.13 75);
  --font-ui: system-ui, -apple-system, "Segoe UI", "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
  --font-code: ui-monospace, "SF Mono", Menlo, Consolas, "Noto Sans Mono CJK TC", monospace; }
@media (prefers-color-scheme: dark) { :root {
  --paper: oklch(0.2 0.012 260); --panel: oklch(0.235 0.014 260); --rule: oklch(0.34 0.014 260);
  --ink: oklch(0.92 0.008 85); --ink-2: oklch(0.72 0.01 260); --accent: oklch(0.75 0.12 255);
  --ins-bg: oklch(0.33 0.05 165); --ins-ink: oklch(0.88 0.08 165); --ins-bar: oklch(0.66 0.13 165);
  --note-bg: oklch(0.27 0.025 80); --note-ink: oklch(0.86 0.06 85); --note-bar: oklch(0.74 0.12 80); } }
* { box-sizing: border-box; }
html { text-autospace: normal; }
body { margin: 0; overflow-wrap: anywhere; background: var(--paper); color: var(--ink); font: 1rem/1.6 var(--font-ui); }
main { max-width: 72rem; margin: 0 auto; padding: 1.5rem 1.25rem 4rem; }
h1 { font-size: 1.625rem; margin: 0; } h2 { font-size: 1.375rem; margin: 2.5rem 0 0.75rem; }
header { display: flex; flex-wrap: wrap; gap: 0.75rem 1.5rem; align-items: baseline; justify-content: space-between; }
nav { display: flex; flex-wrap: wrap; gap: 0.5rem; }
button, select, input { font: inherit; color: inherit; }
.tab, .chip { border: 1px solid var(--rule); background: var(--panel); border-radius: 999px; padding: 0.25rem 0.9rem; cursor: pointer; }
.tab[aria-selected="true"], .chip[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); font-weight: 600; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.small { font-size: 0.875rem; color: var(--ink-2); }
.num { font-variant-numeric: tabular-nums; }
.now { background: var(--note-bg); border-left: 4px solid var(--note-bar); padding: 0.9rem 1.1rem; border-radius: 0 0.5rem 0.5rem 0; margin-top: 1.25rem; }
.now code, td code { font-family: var(--font-code); font-size: 0.9375rem; overflow-wrap: anywhere; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(19rem, 100%), 1fr)); gap: 0.9rem; align-items: start; }
.card { border: 1px solid var(--rule); border-radius: 0.6rem; background: var(--panel); }
.card > summary { list-style: none; cursor: pointer; padding: 0.9rem 1.1rem; }
.card > summary::-webkit-details-marker { display: none; }
.card[data-state="active"] { border-color: var(--accent); }
.card .body { padding: 0 1.1rem 1rem; }
.row { display: flex; justify-content: space-between; gap: 0.75rem; align-items: baseline; }
.name { font-weight: 600; }
.bar { height: 0.4rem; background: var(--rule); border-radius: 999px; overflow: hidden; margin: 0.6rem 0 0.35rem; }
.bar > i { display: block; height: 100%; background: var(--ins-bar); }
.badge { font-size: 0.875rem; border-radius: 999px; padding: 0.05rem 0.6rem; white-space: nowrap; border: 1px solid var(--rule); }
.badge.done { background: var(--ins-bg); color: var(--ins-ink); border-color: transparent; }
.badge.active { color: var(--accent); border-color: var(--accent); }
.badge.agent { background: var(--note-bg); color: var(--note-ink); border-color: transparent; }
ul.plain { list-style: none; padding: 0; margin: 0.5rem 0 0; }
ul.plain li { padding: 0.3rem 0; border-top: 1px solid var(--rule); display: flex; flex-wrap: wrap; gap: 0.2rem 0.6rem; justify-content: space-between; align-items: baseline; }
ul.plain li > * { min-width: 0; overflow-wrap: anywhere; }
ul.scope { margin: 0.5rem 0 0; padding-left: 1.2rem; }
.more { margin-top: 0.7rem; } .more > summary { cursor: pointer; } .more p { margin: 0.5rem 0 0; }
.filters { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin-bottom: 0.75rem; }
.filters input, .filters select { border: 1px solid var(--rule); background: var(--paper); border-radius: 0.4rem; padding: 0.3rem 0.6rem; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 0.45rem 0.7rem 0.45rem 0; border-top: 1px solid var(--rule); }
th { font-size: 0.875rem; color: var(--ink-2); font-weight: 600; border-top: 0; white-space: nowrap; }
td.nowrap { white-space: nowrap; width: 1%; }
.empty { color: var(--ink-2); padding: 0.5rem 0; }
#live { font-size: 0.875rem; color: var(--ink-2); }
</style></head><body><main>
<header><div><h1 id="title">專案總覽</h1><div class="small" id="path"></div></div><nav id="tabs" role="tablist" aria-label="專案"></nav></header>
<div id="live"></div>
<div id="app"></div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
"use strict";
let DATA = JSON.parse(document.getElementById("data").textContent);
const view = { project: 0, decider: "", milestone: "", query: "", archived: false, open: {} };
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
function command(text) {
  const parts = String(text || "").split(/`([^`]*)`/);
  return parts.map((p, i) => (i % 2 ? el("code", {}, p) : p));
}
function milestoneCard(m, key) {
  const live = m.tickets.filter(t => !t.dropped), done = live.filter(t => t.done).length, total = live.length;
  const id = key + "/" + m.name;
  const card = el("details", { class: "card", "data-state": m.state, open: view.open[id] ?? m.state === "active" },
    el("summary", {},
      el("div", { class: "row" }, el("span", { class: "name" }, m.name), el("span", { class: "badge " + m.state }, STATE[m.state])),
      el("div", { class: "small" }, m.goal),
      m.tickets.length ? [el("div", { class: "bar", role: "img", "aria-label": `${done} / ${total} 張票完成` }, el("i", { style: `width:${total ? (100 * done / total) : 0}%` })),
               el("div", { class: "small num" }, `${done} / ${total} 張票完成`)] : el("div", { class: "small" }, m.status)),
    el("div", { class: "body" },
      m.tickets.length ? el("div", { class: "small" }, m.status) : null,
      m.tickets.length ? el("ul", { class: "plain" }, m.tickets.map(t => el("li", {},
        el("span", {}, t.title),
        el("span", { class: "badge " + (t.done ? "done" : "") + " num" }, t.done ? "完成" : (t.dropped ? "不做" : (t.checked ? `${t.checked}/${t.boxes}` : "未開始")))))) : null,
      (m.detail || m.scope.length) ? el("details", { class: "more" }, el("summary", { class: "small" }, "目標與範圍"),
        m.detail ? el("p", {}, m.detail) : null,
        m.scope.length ? el("ul", { class: "scope" }, m.scope.map(s => el("li", { class: "small" }, s))) : null) : null));
  card.addEventListener("toggle", () => { view.open[id] = card.open; });
  return card;
}
function decisionsView(p) {
  // 已封存里程碑的決定預設收起；選了某個里程碑或在搜尋時照樣找得到
  const pool = p.decisions.filter(d => view.archived || view.milestone || view.query || !d.archived);
  const list = pool.filter(d => (!view.decider || d.decider === view.decider) && (!view.milestone || d.milestone === view.milestone)
    && (!view.query || (d.text + d.label + d.milestone + d.date).toLowerCase().includes(view.query.toLowerCase())));
  const count = who => pool.filter(d => d.decider === who).length;
  const names = [...new Set(p.decisions.map(d => d.milestone).filter(Boolean))];
  const archived = p.decisions.filter(d => d.archived).length;
  const chip = (label, value) => el("button", { class: "chip", "aria-pressed": String(view.decider === value),
    onclick: () => { view.decider = value; render(); } }, label);
  return [
    el("div", { class: "filters" },
      chip(`全部 ${pool.length}`, ""), chip(`Agent 定 ${count("Agent 定")}`, "Agent 定"),
      chip(`使用者同意 ${count("使用者同意")}`, "使用者同意"), chip(`使用者定 ${count("使用者定")}`, "使用者定"),
      count("未標") ? chip(`未標 ${count("未標")}`, "未標") : null,
      archived ? el("button", { class: "chip", "aria-pressed": String(view.archived),
        onclick: () => { view.archived = !view.archived; render(); } }, `含已封存的 ${archived}`) : null,
      el("select", { "aria-label": "里程碑", onchange: e => { view.milestone = e.target.value; render(); } },
        el("option", { value: "" }, "所有里程碑"), names.map(n => el("option", { value: n, selected: view.milestone === n }, n))),
      el("input", { type: "search", placeholder: "搜尋決策", "aria-label": "搜尋決策", value: view.query, id: "q",
        oninput: e => { view.query = e.target.value; render(); document.getElementById("q").focus(); } })),
    list.length ? el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ["日期", "里程碑", "決定者", "決定"].map(h => el("th", {}, h)))),
      el("tbody", {}, list.slice(0, 300).map(d => el("tr", {},
        el("td", { class: "nowrap num" }, d.date), el("td", { class: "nowrap" }, d.milestone),
        el("td", { class: "nowrap" }, el("span", { class: "badge " + (d.decider === "Agent 定" ? "agent" : "") }, d.decider)),
        el("td", {}, d.label && d.label !== d.milestone ? el("span", { class: "small" }, d.label + "　") : null, d.text))))))
      : el("div", { class: "empty" }, p.decisions.length ? "沒有符合的決策。" : "還沒有決策紀錄。"),
    list.length > 300 ? el("div", { class: "small" }, `只顯示最新的 300 條，共 ${list.length} 條；用篩選縮小範圍。`) : null];
}
function render() {
  const p = DATA.projects[Math.min(view.project, DATA.projects.length - 1)];
  document.getElementById("title").textContent = p.title;
  document.getElementById("path").textContent = p.path;
  document.title = p.title + "：專案總覽";
  const tabs = document.getElementById("tabs"); tabs.replaceChildren();
  if (DATA.projects.length > 1) DATA.projects.forEach((q, i) => tabs.append(el("button", { class: "tab", role: "tab",
    "aria-selected": String(i === view.project), onclick: () => { view.project = i; view.milestone = ""; render(); } }, q.name)));
  const q = document.activeElement && document.activeElement.id === "q", pos = q ? document.activeElement.selectionStart : 0;
  document.getElementById("app").replaceChildren(...[
    p.missing.length ? el("div", { class: "now" }, "讀不到的檔：" + p.missing.join("、") + "。這個 repo 還沒照 project-init 的骨架，對應的區塊會是空的。") : null,
    p.unreadable.length ? el("details", { class: "now" }, el("summary", {}, `讀不到的行：${p.unreadable.length} 行不是約定的寫法`),
      el("ul", { class: "plain" }, p.unreadable.map(u => el("li", {}, el("span", {}, u.text, el("div", { class: "small" }, u.why)), el("span", { class: "small num" }, `${u.file}:${u.line}`))))) : null,
    el("div", { class: "now" },
      el("div", { class: "small" }, "下一步"), el("div", {}, p.next ? command(p.next) : "progress.md 沒有 session 紀錄。"),
      p.working.length ? [el("div", { class: "small", style: "margin-top:.7rem" }, `正在做（${p.working.length} 個 worktree）`),
        el("ul", { class: "plain" }, p.working.map(w => el("li", {}, el("span", {}, `${w.milestone}　${w.title}`),
          el("span", { class: "badge active num" }, (w.done ? "做完，等合併" : (w.boxes ? `${w.checked}/${w.boxes}` : "進行中")) + "　" + w.worktree))))] : null),
    el("h2", {}, "里程碑"),
    p.milestones.length ? el("div", { class: "grid" }, p.milestones.map(m => milestoneCard(m, p.name))) : el("div", { class: "empty" }, "roadmap.md 沒有里程碑表。"),
    p.unlisted.length ? [el("h2", {}, "不在 roadmap 的工作"),
      el("div", { class: "grid" }, p.unlisted.map(m => milestoneCard(m, p.name + "/unlisted")))] : null,
    el("h2", {}, "決策"), decisionsView(p),
    el("h2", {}, "架構決定（ADR）"),
    p.adrs.length ? el("ul", { class: "plain" }, p.adrs.map(a => el("li", {}, el("span", {}, a.title), el("span", { class: "small num" }, a.file)))) : el("div", { class: "empty" }, "沒有 ADR。"),
    el("h2", {}, "最近的 session"),
    p.sessions.length ? el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ["日期", "票", "結果"].map(h => el("th", {}, h)))),
      el("tbody", {}, p.sessions.map(s => el("tr", {}, el("td", { class: "nowrap num" }, s.date), el("td", { class: "nowrap" }, s.ticket), el("td", {}, s.result))))))
      : el("div", { class: "empty" }, "沒有 session 紀錄。")].flat(Infinity).filter(Boolean));
  if (q) { const input = document.getElementById("q"); input.focus(); input.setSelectionRange(pos, pos); }
}
render();
if (location.protocol.startsWith("http")) {
  const live = document.getElementById("live"); let last = JSON.stringify(DATA);
  const tick = async () => {
    try {
      const text = await (await fetch("data.json", { cache: "no-store" })).text();
      if (text !== last) { last = text; DATA = JSON.parse(text); render(); }
      live.textContent = "自動更新中，上次讀取 " + new Date().toLocaleTimeString();
    } catch (e) { live.textContent = "讀不到伺服器，畫面停在上次的內容。"; }
  };
  tick(); setInterval(tick, 3000);
}
</script></body></html>
"""


def data(repos: list) -> dict:
    return {"projects": [collect(r) for r in repos]}


def render(payload: dict) -> str:
    # </script> 不能出現在內嵌的 JSON 裡
    return PAGE.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))


def handler(repos: list):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.split("?")[0] == "/data.json":
                body, kind = json.dumps(data(repos), ensure_ascii=False).encode("utf-8"), "application/json"
            elif self.path.split("?")[0] in ("/", "/index.html"):
                body, kind = render(data(repos)).encode("utf-8"), "text/html"
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
