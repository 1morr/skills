#!/usr/bin/env python3
"""把 report.json 渲染成 showcase.html（寫在 report.json 旁邊）；加 --pr-md 時另寫 pr.md。

只用標準函式庫，任何 repo 不必安裝東西就能跑。輸入格式見
../references/report-schema.md。

diff 一律在這裡從 git 讀，不從報告讀，所以讀者看到的每段 hunk 都是真的。
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import fnmatch
import html
import json
import re
import subprocess
import sys
from pathlib import Path

LEVELS = ("before-after", "after", "tests", "static")
# GitHub 留言附件上限 25 MB，留一點餘裕。
MAX_HTML_BYTES = 20 * 1024 * 1024
# GitHub 的 PR 描述或留言上限 65536 字元。
MAX_PR_CHARS = 60000
LONG_HUNK_LINES = 150
DEFAULT_CONTEXT = 6
GAP = "⋯"
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
VIDEO_TYPES = {".mp4", ".webm"}
# 不靠 mimetypes：它在 Windows 上會讀登錄檔，結果因機器而異。
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".webm": "video/webm"}

LABELS = {
    "en": {
        "summary": "Summary",
        "evidence": "Evidence",
        "why": "Why",
        "how": "How it works",
        "decisions": "Decisions",
        "key_changes": "Key changes",
        "files": "All changed files",
        "try_it": "Try it yourself",
        "unverified": "Not verified",
        "level": "Evidence level",
        "before-after": "Before and after, both run",
        "after": "After only",
        "tests": "Tests or command output",
        "static": "Static, nothing run",
        "why_not_higher": "Why not higher",
        "awaiting": "No source states the motivation. Awaiting the author.",
        "inferred": "inferred",
        "stated": "stated",
        "sources": "Sources",
        "alternatives": "Alternatives considered",
        "before": "Before",
        "after_label": "After",
        "side_by_side": "Side by side",
        "slider": "Slider",
        "command": "Command",
        "working_tree": "working tree",
        "generated": "Generated",
        "files_count": "{n} files",
    },
    "zh-Hant": {
        "summary": "摘要",
        "evidence": "證據",
        "why": "為什麼",
        "how": "怎麼做的",
        "decisions": "決策",
        "key_changes": "關鍵改動",
        "files": "所有改動的檔案",
        "try_it": "自己試試",
        "unverified": "未驗證",
        "level": "證據等級",
        "before-after": "修改前後都實跑",
        "after": "只跑了修改後",
        "tests": "測試或指令輸出",
        "static": "靜態，沒有實跑",
        "why_not_higher": "為什麼沒有更高",
        "awaiting": "沒有任何來源說明動機，待作者補充。",
        "inferred": "推斷",
        "stated": "有來源",
        "sources": "來源",
        "alternatives": "考慮過的替代方案",
        "before": "修改前",
        "after_label": "修改後",
        "side_by_side": "並排",
        "slider": "滑桿",
        "command": "指令",
        "working_tree": "工作區",
        "generated": "產生於",
        "files_count": "{n} 個檔案",
    },
}

STATUS = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed", "C": "copied", "T": "type changed"}


class ReportError(Exception):
    """報告無法渲染；訊息列出找到的每個問題。"""


# ---------- git ----------


def git(repo: Path, *args: str, ok_codes: tuple[int, ...] = (0,)) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode not in ok_codes:
        raise ReportError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def changed_files(repo: Path, base: str, head: str | None, exclude: str | None) -> list[dict]:
    rev = [base] + ([head] if head else [])
    status_tokens = git(repo, "diff", "--name-status", "-M", "-z", *rev).split("\0")
    files: list[dict] = []
    i = 0
    while i < len(status_tokens):
        code = status_tokens[i]
        if not code:
            i += 1
            continue
        kind = code[0]
        if kind in "RC":
            files.append({"path": status_tokens[i + 2], "old": status_tokens[i + 1], "status": kind})
            i += 3
        else:
            files.append({"path": status_tokens[i + 1], "old": None, "status": kind})
            i += 2

    stats: dict[str, tuple[str, str]] = {}
    num_tokens = git(repo, "diff", "--numstat", "-M", "-z", *rev).split("\0")
    i = 0
    while i < len(num_tokens):
        tok = num_tokens[i]
        if not tok:
            i += 1
            continue
        added, deleted, path = tok.split("\t", 2)
        if path == "":  # 改名：舊路徑與新路徑接在後面各自成一個 token
            path = num_tokens[i + 2]
            i += 3
        else:
            i += 1
        stats[path] = (added, deleted)
    for f in files:
        f["added"], f["deleted"] = stats.get(f["path"], ("-", "-"))

    if head is None:
        for path in git(repo, "ls-files", "--others", "--exclude-standard").splitlines():
            if exclude and (path == exclude or path.startswith(exclude + "/")):
                continue
            files.append({"path": path, "old": None, "status": "A", "untracked": True,
                          "added": str(count_lines(repo / path)), "deleted": "0"})
    return files


def count_lines(path: Path) -> int | str:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (UnicodeDecodeError, OSError):
        return "-"


def file_diff(repo: Path, base: str, head: str | None, f: dict) -> str:
    if f.get("untracked"):
        return git(repo, "diff", "--no-color", "--no-index", "--", "/dev/null", f["path"], ok_codes=(0, 1))
    rev = [base] + ([head] if head else [])
    paths = [f["old"], f["path"]] if f["old"] else [f["path"]]
    return git(repo, "diff", "--no-color", "-M", *rev, "--", *paths)


def trim_hunk(hunk: str, needle: str, context: int) -> str:
    """只留含 needle 的行與前後 context 行；省略處以 ⋯ 標出，讀者才看得到自己少看了什麼。"""
    header, *body = hunk.split("\n")
    hits = [i for i, line in enumerate(body) if needle in line]
    if not hits:  # 只命中標頭（函式名）時整段保留
        return hunk
    keep = sorted({j for i in hits for j in range(max(0, i - context), min(len(body), i + context + 1))})
    out, prev = [header], -1
    for i in keep:
        if i > prev + 1:
            out.append(GAP)
        out.append(body[i])
        prev = i
    if prev < len(body) - 1:
        out.append(GAP)
    return "\n".join(out)


def split_hunks(diff_text: str) -> list[str]:
    hunks: list[list[str]] = []
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            hunks.append([line])
        elif line.startswith("diff --git"):
            continue
        elif hunks:
            hunks[-1].append(line)
    return ["\n".join(h) for h in hunks]


# ---------- validation and assembly ----------


def ref_at(repo: Path, ref: str | None, sha: str, field: str, warnings: list[str]) -> str | None:
    """分支名只在它正指向該 commit 時才顯示，免得誤導。"""
    if not ref or sha.startswith(ref):  # ref 欄位填的是 SHA 時，放在 SHA 旁邊沒有資訊量
        return None
    proc = subprocess.run(["git", "rev-parse", "--verify", "-q", ref + "^{commit}"],
                          cwd=repo, capture_output=True, text=True)
    if proc.stdout.strip() != sha:
        warnings.append(f"range.{field} `{ref}` does not point at {sha[:8]}; left out of the report")
        return None
    return ref


# 不該送到讀者手上的個人路徑與像秘密的值。
LEAK_PATTERNS = [
    re.compile(r"\b[A-Za-z]:(?:\\\\|\\|/)(?:Users|Documents and Settings)(?:\\\\|\\|/)[^\\/\s\"]+", re.IGNORECASE),
    re.compile(r"(?<![\w.])/(?:home|Users)/[\w.-]+"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password|passwd|authorization)\b[\"']?\s*[:=]\s*[\"']?"
               r"(?!redacted|\*|x{3}|<|\$\{)[^\s\"',;]{8,}"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/-]{16,}"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"),
]


def leaks(text: str) -> list[str]:
    return [m.group(0) for p in LEAK_PATTERNS for m in p.finditer(text or "")]


def load_text(base_dir: Path, item: dict, key: str, errors: list[str]) -> str | None:
    if key in item:
        return item[key]
    if f"{key}_file" in item:
        p = base_dir / item[f"{key}_file"]
        if not p.is_file():
            errors.append(f"evidence file not found: {p}")
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    return None


def data_uri(path: Path) -> str:
    return f"data:{MIME[path.suffix.lower()]};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def media(uri: str, alt: str) -> str:
    """錄影自動播放並循環，讀者不用按就看得到整段操作。"""
    if uri.startswith("data:video/"):
        return f'<video src="{uri}" autoplay loop muted playsinline controls aria-label="{alt}"></video>'
    return f'<img src="{uri}" alt="{alt}">'


def build(report: dict, report_dir: Path, repo: Path) -> tuple[dict, list[str]]:
    """對照 repo 驗證報告，並備齊渲染需要的一切。"""
    errors: list[str] = []
    warnings: list[str] = []

    for key in ("title", "summary", "range", "files", "evidence"):
        if key not in report:
            errors.append(f"missing required field: {key}")
    if errors:
        raise ReportError("\n".join(errors))

    rng = report["range"]
    base = git(repo, "rev-parse", "--verify", rng["base"] + "^{commit}").strip()
    head = git(repo, "rev-parse", "--verify", rng["head"] + "^{commit}").strip() if rng.get("head") else None
    base_ref = ref_at(repo, rng.get("base_ref"), base, "base_ref", warnings)
    head_ref = ref_at(repo, rng.get("head_ref"), head, "head_ref", warnings) if head else None

    try:
        exclude = report_dir.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        exclude = None
    files = changed_files(repo, base, head, exclude)
    if not files:
        errors.append(f"no changes between {rng['base']} and {rng.get('head') or 'the working tree'}")
    by_path = {f["path"]: f for f in files}

    # 每個改動的檔案都有說明；每個說明鍵都對得上改動的檔案。
    notes: dict[str, str] = report["files"]
    used: set[str] = set()
    for f in files:
        key = f["path"] if f["path"] in notes else next(
            (k for k in notes if fnmatch.fnmatchcase(f["path"], k)), None)
        if key is None:
            errors.append(f"changed file has no note in `files`: {f['path']}")
        else:
            f["note_key"] = key
            used.add(key)
    for key in notes:
        if key not in used:
            errors.append(f"`files` key matches no changed file: {key}")

    hunks_out = []
    chosen: dict[tuple[str, str], int] = {}  # (檔案, hunk 標頭) → 第幾個條目選了它
    for n, h in enumerate(report.get("hunks", []), 1):
        f = by_path.get(h.get("file", ""))
        if f is None:
            errors.append(f"hunk file is not in the change: {h.get('file')}")
            continue
        all_hunks = split_hunks(file_diff(repo, base, head, f))
        sel = [x for x in all_hunks if h["match"] in x] if h.get("match") else all_hunks
        if not sel:
            errors.append(f"hunk selector matched nothing in {f['path']}: {h.get('match')!r}")
            continue
        for x in sel:
            key = (f["path"], x.split("\n", 1)[0])
            if key in chosen:
                warnings.append(f"hunks entries {chosen[key]} and {n} select the same hunk in {f['path']}; merge them")
            chosen.setdefault(key, n)
        if h.get("match"):
            sel = [trim_hunk(x, h["match"], h.get("context", DEFAULT_CONTEXT)) for x in sel]
        lines = sum(x.count("\n") + 1 for x in sel)
        if lines > LONG_HUNK_LINES:
            warnings.append(f"{f['path']}: {lines} diff lines selected; narrow `match` or lower `context`")
        hunks_out.append({"file": f["path"], "note": h.get("note", ""), "text": "\n".join(sel)})

    ev = report["evidence"]
    if ev.get("level") not in LEVELS:
        errors.append(f"evidence.level must be one of {', '.join(LEVELS)}")
    elif ev["level"] != "before-after" and not ev.get("why_not_higher"):
        errors.append("evidence.why_not_higher is required unless the level is before-after")
    items = []
    for item in ev.get("items", []):
        kind = item.get("kind")
        out = {"kind": kind, "caption": item.get("caption", "")}
        if kind in ("image", "compare"):
            for side in (("before", "after") if kind == "compare" else ("after",)):
                p = report_dir / item.get(side, "")
                if not item.get(side) or not p.is_file():
                    errors.append(f"{kind} evidence `{side}` image not found: {p}")
                elif p.suffix.lower() not in IMAGE_TYPES | VIDEO_TYPES:
                    errors.append(f"not an image or video type ({', '.join(sorted(IMAGE_TYPES | VIDEO_TYPES))}): {p}")
                else:
                    out[side] = data_uri(p)
        elif kind == "output":
            out["command"] = item.get("command", "")
            out["before"] = load_text(report_dir, item, "before", errors)
            out["after"] = load_text(report_dir, item, "after", errors)
            if out["after"] is None:
                errors.append(f"output evidence needs `after` or `after_file`: {out['caption']!r}")
        else:
            errors.append(f"unknown evidence kind: {kind!r} (image, compare, output)")
        items.append(out)

    if errors:
        raise ReportError("\n".join(errors))

    texts = {"report.json": json.dumps(report, ensure_ascii=False)}
    for item in items:
        if item["kind"] == "output":
            texts[f"evidence {item['caption']!r}"] = f"{item['before'] or ''}\n{item['after']}"
    for where, text in texts.items():
        found = sorted(set(leaks(text)))
        if found:
            warnings.append(f"possible personal path or secret in {where}: {', '.join(found[:5])}; scrub it")

    return {
        "report": report,
        "base": base,
        "head": head,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "files": files,
        "hunks": hunks_out,
        "items": items,
    }, warnings


# ---------- Markdown-lite to HTML ----------


def inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`)", html.escape(text, quote=True))
    out = []
    for part in parts:
        if len(part) > 1 and part.startswith("`") and part.endswith("`"):
            out.append(f"<code>{part[1:-1]}</code>")
        else:
            part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part)
            part = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', part)
            out.append(part)
    return "".join(out)


def blocks(text: str) -> str:
    out = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if all(re.match(r"^[-*] ", ln) for ln in lines):
            out.append("<ul>" + "".join(f"<li>{inline(ln[2:])}</li>" for ln in lines) + "</ul>")
        elif all(re.match(r"^\d+[.)] ", ln) for ln in lines):
            out.append("<ol>" + "".join(f"<li>{inline(ln.split(' ', 1)[1])}</li>" for ln in lines) + "</ol>")
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


def diff_html(text: str) -> str:
    rows = []
    for line in text.splitlines():
        cls = "hunk" if line.startswith("@@") or line == GAP else "add" if line.startswith("+") else "del" if line.startswith("-") else "ctx"
        rows.append(f'<span class="{cls}">{html.escape(line) or " "}</span>')
    return f'<pre class="diff">{"".join(rows)}</pre>'


# ---------- HTML ----------

CSS = """
:root{--bg:#f8f8f6;--fg:#1c1c1a;--muted:#686862;--line:#e2e1dc;--card:#fff;--accent:#2d56c8;
--add-bg:#e5f3e8;--add-fg:#14532d;--del-bg:#fbe8e8;--del-fg:#7f1d1d;--warn-bg:#fdf1cf;--warn-fg:#5c4300;--code-bg:#efeeea}
@media (prefers-color-scheme:dark){:root{--bg:#151514;--fg:#e7e5e0;--muted:#9b988f;--line:#2f2e2b;--card:#1d1c1a;--accent:#8ea9ff;
--add-bg:#11301c;--add-fg:#a9e4bb;--del-bg:#3b1717;--del-fg:#f4b3b3;--warn-bg:#3a2f0e;--warn-fg:#f2d78d;--code-bg:#262522}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 system-ui,-apple-system,"Segoe UI","Noto Sans TC",sans-serif}
main{max-width:1080px;margin:0 auto;padding:40px 16px 96px}
a{color:var(--accent)}
h1{font-size:1.75rem;line-height:1.25;margin:0 0 .4rem}
h2{font-size:1.1rem;margin:2.6rem 0 .8rem;padding-bottom:.35rem;border-bottom:1px solid var(--line)}
h3{font-size:.98rem;margin:1.4rem 0 .4rem}
.meta{color:var(--muted);font-size:.85rem}
.meta code{font-size:.8rem}
nav{display:flex;flex-wrap:wrap;gap:.3rem .9rem;margin:1.2rem 0 0;font-size:.85rem}
nav a{color:var(--muted);text-decoration:none}nav a:hover{color:var(--accent)}
.lead{font-size:1.05rem}
code{font-family:ui-monospace,"Cascadia Code",Consolas,monospace;font-size:.86em;background:var(--code-bg);padding:.08em .35em;border-radius:4px}
.tag{display:inline-block;font-size:.75rem;line-height:1.4;padding:.05em .55em;border-radius:999px;border:1px solid var(--line);color:var(--muted);vertical-align:.1em}
.warn{background:var(--warn-bg);color:var(--warn-fg);padding:.55rem .8rem;border-radius:6px;margin:.6rem 0}
.level{display:flex;flex-wrap:wrap;gap:.4rem 1rem;align-items:baseline;padding:.7rem .9rem;border:1px solid var(--line);border-radius:8px;background:var(--card)}
.level strong{font-size:.95rem}
figure{margin:1.1rem 0;padding:12px;background:var(--card);border:1px solid var(--line);border-radius:8px}
figcaption{font-size:.9rem;margin-bottom:.6rem}
figure img,figure video{display:block;max-width:100%;height:auto;border:1px solid var(--line)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pair>div{min-width:0}
.pair .side-label{font-size:.78rem;color:var(--muted);margin-bottom:.25rem}
.modes{display:flex;gap:.3rem;margin-bottom:.6rem}
.modes button{font:inherit;font-size:.8rem;padding:.15rem .6rem;border:1px solid var(--line);background:transparent;color:var(--fg);border-radius:6px;cursor:pointer}
.modes button[aria-pressed=true]{background:var(--fg);color:var(--bg)}
.compare[data-mode=pair] .slider-wrap,.compare[data-mode=slider] .pair{display:none}
.slider{position:relative;max-width:100%}
.slider img{border:0}
.slider .top{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:fill;clip-path:inset(0 calc(100% - var(--pos,50%)) 0 0)}
.slider-wrap input{width:100%;margin-top:.5rem}
.slider-legend{display:flex;justify-content:space-between;font-size:.78rem;color:var(--muted)}
pre{margin:.4rem 0;overflow-x:auto}
pre.out{font:12.5px/1.5 ui-monospace,"Cascadia Code",Consolas,monospace;background:var(--code-bg);padding:10px 12px;border-radius:6px;white-space:pre}
.diff{font:12.5px/1.5 ui-monospace,"Cascadia Code",Consolas,monospace;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 0}
.diff span{display:block;padding:0 12px;white-space:pre}
.diff .add{background:var(--add-bg);color:var(--add-fg)}
.diff .del{background:var(--del-bg);color:var(--del-fg)}
.diff .hunk{color:var(--muted)}
.hunk-note{margin:.2rem 0 .3rem}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th,td{text-align:left;vertical-align:top;padding:.4rem .5rem;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted)}
td.num{white-space:nowrap;font-family:ui-monospace,Consolas,monospace;font-size:.8rem}
.plus{color:var(--add-fg)}.minus{color:var(--del-fg)}
details summary{cursor:pointer}
.decision{padding:.6rem 0;border-bottom:1px solid var(--line)}
.decision:last-child{border-bottom:0}
figure .pair img,figure>img{cursor:zoom-in}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.85);display:flex;align-items:flex-start;justify-content:center;overflow:auto;padding:24px;cursor:zoom-out;z-index:10}
#zoom[hidden]{display:none}
#zoom img{max-width:none;background:#fff}
@media (max-width:720px){.pair{grid-template-columns:1fr}h1{font-size:1.45rem}}
"""

JS = """
var zoom=document.getElementById('zoom'),zoomImg=zoom.querySelector('img');
document.querySelectorAll('figure .pair img, figure>img').forEach(function(i){
  i.addEventListener('click',function(){zoomImg.src=i.src;zoomImg.alt=i.alt;zoom.hidden=false});
});
zoom.addEventListener('click',function(){zoom.hidden=true});
document.addEventListener('keydown',function(e){if(e.key==='Escape')zoom.hidden=true});
document.querySelectorAll('.compare').forEach(function(c){
  var btns=c.querySelectorAll('[data-mode]');
  btns.forEach(function(b){b.addEventListener('click',function(){
    c.dataset.mode=b.dataset.mode;
    btns.forEach(function(x){x.setAttribute('aria-pressed',String(x===b))});
  })});
  var r=c.querySelector('input[type=range]'),s=c.querySelector('.slider');
  r.addEventListener('input',function(){s.style.setProperty('--pos',r.value+'%')});
  // 尺寸不同的兩張圖用滑桿會對不齊，只提供並排。
  var imgs=c.querySelectorAll('.pair img');
  function check(){
    if(!imgs[0].complete||!imgs[1].complete)return;
    if(imgs[0].naturalWidth!==imgs[1].naturalWidth||imgs[0].naturalHeight!==imgs[1].naturalHeight){
      c.querySelector('.modes').hidden=true;
    }
  }
  imgs.forEach(function(i){i.addEventListener('load',check)});check();
});
"""


def range_label(model: dict, L: dict) -> str:
    def side(sha: str, ref: str | None) -> str:
        return f"{ref} @ {sha[:8]}" if ref else sha[:8]
    head = side(model["head"], model["head_ref"]) if model["head"] else L["working_tree"]
    return f"{side(model['base'], model['base_ref'])} → {head}"


def render_html(model: dict, L: dict) -> str:
    r = model["report"]
    ev = r["evidence"]
    sec: list[tuple[str, str, str]] = []  # (id, label, body)

    sec.append(("summary", L["summary"], f'<div class="lead">{blocks(r["summary"])}</div>'))

    body = f'<div class="level"><span class="tag">{L["level"]}</span><strong>{L[ev["level"]]}</strong>'
    if ev.get("why_not_higher"):
        body += f'<span class="meta">{L["why_not_higher"]}: {inline(ev["why_not_higher"])}</span>'
    body += "</div>"
    for n, item in enumerate(model["items"], 1):
        cap = f"<figcaption>{inline(item['caption'])}</figcaption>" if item["caption"] else ""
        alt = html.escape(item["caption"])
        if item["kind"] == "image":
            body += f'<figure id="ev-{n}">{cap}{media(item["after"], alt)}</figure>'
        elif item["kind"] == "compare" and "data:video/" in item["before"][:16] + item["after"][:16]:
            # 兩段錄影的時間軸對不上，滑桿沒有意義，只並排。
            body += (
                f'<figure id="ev-{n}">{cap}'
                f'<div class="pair"><div><div class="side-label">{L["before"]}</div>{media(item["before"], L["before"] + ": " + alt)}</div>'
                f'<div><div class="side-label">{L["after_label"]}</div>{media(item["after"], L["after_label"] + ": " + alt)}</div></div></figure>'
            )
        elif item["kind"] == "compare":
            body += (
                f'<figure id="ev-{n}" class="compare" data-mode="pair">{cap}'
                f'<div class="modes"><button data-mode="pair" aria-pressed="true">{L["side_by_side"]}</button>'
                f'<button data-mode="slider" aria-pressed="false">{L["slider"]}</button></div>'
                f'<div class="pair"><div><div class="side-label">{L["before"]}</div><img src="{item["before"]}" alt="{L["before"]}: {alt}"></div>'
                f'<div><div class="side-label">{L["after_label"]}</div><img src="{item["after"]}" alt="{L["after_label"]}: {alt}"></div></div>'
                f'<div class="slider-wrap"><div class="slider"><img src="{item["after"]}" alt="{L["after_label"]}: {alt}">'
                f'<img class="top" src="{item["before"]}" alt="{L["before"]}: {alt}"></div>'
                f'<input type="range" min="0" max="100" value="50" aria-label="{L["slider"]}">'
                f'<div class="slider-legend"><span>◀ {L["before"]}</span><span>{L["after_label"]} ▶</span></div></div></figure>'
            )
        else:
            body += f'<figure id="ev-{n}">{cap}'
            if item["command"]:
                body += f'<div class="meta">{L["command"]}: <code>{html.escape(item["command"])}</code></div>'
            if item["before"] is not None:
                body += (f'<div class="pair"><div><div class="side-label">{L["before"]}</div><pre class="out">{html.escape(item["before"])}</pre></div>'
                         f'<div><div class="side-label">{L["after_label"]}</div><pre class="out">{html.escape(item["after"])}</pre></div></div>')
            else:
                body += f'<pre class="out">{html.escape(item["after"])}</pre>'
            body += "</figure>"
    sec.append(("evidence", L["evidence"], body))

    why = r.get("why") or {}
    body = ""
    if not why.get("sources"):
        body += f'<div class="warn">{L["awaiting"]}</div>'
        if why.get("text"):
            body += f'<span class="tag">{L["inferred"]}</span>{blocks(why["text"])}'
    else:
        body += blocks(why.get("text", ""))
        body += f'<p class="meta">{L["sources"]}: {"; ".join(inline(s) for s in why["sources"])}</p>'
    sec.append(("why", L["why"], body))

    if r.get("how"):
        sec.append(("how", L["how"], blocks(r["how"])))

    if r.get("decisions"):
        body = ""
        for d in r["decisions"]:
            basis = d.get("basis", "inferred")
            body += f'<div class="decision"><strong>{inline(d["decision"])}</strong> <span class="tag">{L.get(basis, basis)}</span>'
            body += blocks(d.get("why", ""))
            if d.get("alternatives"):
                body += f'<p class="meta">{L["alternatives"]}: {inline(d["alternatives"])}</p>'
            if d.get("source"):
                body += f'<p class="meta">{L["sources"]}: {inline(d["source"])}</p>'
            body += "</div>"
        sec.append(("decisions", L["decisions"], body))

    if model["hunks"]:
        body = ""
        for n, h in enumerate(model["hunks"], 1):
            body += (f'<div class="hunk-block" id="hunk-{n}"><h3><code>{html.escape(h["file"])}</code></h3>'
                     f'<div class="hunk-note">{blocks(h["note"])}</div>{diff_html(h["text"])}</div>')
        sec.append(("key-changes", L["key_changes"], body))

    sec.append(("files", L["files"], files_table(model, L)))

    if r.get("try_it"):
        sec.append(("try-it", L["try_it"], "<ol>" + "".join(f"<li>{inline(s)}</li>" for s in r["try_it"]) + "</ol>"))
    if r.get("unverified"):
        sec.append(("unverified", L["unverified"], "<ul>" + "".join(f"<li>{inline(s)}</li>" for s in r["unverified"]) + "</ul>"))

    nav = "".join(f'<a href="#{sid}">{label}</a>' for sid, label, _ in sec)
    sections = "".join(f'<section id="{sid}"><h2>{label}</h2>{b}</section>' for sid, label, b in sec)
    generated = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
    return (
        f'<!doctype html><html lang="{html.escape(r.get("lang", "en"))}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">'
        f"<title>{html.escape(r['title'])}</title><style>{CSS}</style></head><body><main>"
        f"<header><h1>{inline(r['title'])}</h1>"
        f'<div class="meta"><code>{html.escape(range_label(model, L))}</code> · {L["generated"]} {generated}</div>'
        f"<nav>{nav}</nav></header>{sections}</main>"
        f'<div id="zoom" hidden><img alt=""></div><script>{JS}</script></body></html>'
    )


def grouped_files(model: dict) -> list[tuple[str, str, list[dict]]]:
    notes = model["report"]["files"]
    groups: dict[str, list[dict]] = {k: [] for k in notes}
    for f in model["files"]:
        groups[f["note_key"]].append(f)
    return [(k, notes[k], fs) for k, fs in groups.items()]


def files_table(model: dict, L: dict) -> str:
    rows = ""
    for key, note, fs in grouped_files(model):
        if len(fs) == 1 and fs[0]["path"] == key:
            f = fs[0]
            name = f"<code>{html.escape(f['path'])}</code>"
            if f["old"]:
                name = f"<code>{html.escape(f['old'])}</code> → {name}"
            stat = f'<span class="plus">+{f["added"]}</span> <span class="minus">−{f["deleted"]}</span>'
            rows += f'<tr><td>{name}</td><td>{STATUS.get(f["status"], f["status"])}</td><td class="num">{stat}</td><td>{inline(note)}</td></tr>'
        else:
            listing = "".join(f"<div><code>{html.escape(f['path'])}</code></div>" for f in fs)
            name = f'<details><summary><code>{html.escape(key)}</code> · {L["files_count"].format(n=len(fs))}</summary>{listing}</details>'
            rows += f'<tr><td>{name}</td><td></td><td class="num"></td><td>{inline(note)}</td></tr>'
    return f"<table><tbody>{rows}</tbody></table>"


# ---------- PR Markdown ----------


def fence(text: str, lang: str = "") -> str:
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return f"{ticks}{lang}\n{text}\n{ticks}"


def render_md(model: dict, L: dict, include_hunks: bool = True) -> str:
    r = model["report"]
    ev = r["evidence"]
    out = [f"## {r['title']}", "", f"`{range_label(model, L)}`", "", r["summary"].strip(), ""]

    level = f"**{L['level']}:** {L[ev['level']]}"
    if ev.get("why_not_higher"):
        level += f". {L['why_not_higher']}: {ev['why_not_higher']}"
    out += [f"### {L['evidence']}", "", level, ""]
    for item in model["items"]:
        if item["kind"] in ("image", "compare"):
            # 文字版沒有圖；caption 寫的是看到的差異，單獨讀也懂。
            out.append(f"- {item['caption']}")
        else:
            out.append(f"<details><summary>{html.escape(item['caption'])}</summary>\n")
            if item["command"]:
                out.append(f"{L['command']}: `{item['command']}`\n")
            if item["before"] is not None:
                out += [f"**{L['before']}**\n", fence(item["before"]), f"\n**{L['after_label']}**\n"]
            out += [fence(item["after"]), "\n</details>"]
    out.append("")

    why = r.get("why") or {}
    out += [f"### {L['why']}", ""]
    if not why.get("sources"):
        out.append(f"> {L['awaiting']}")
        if why.get("text"):
            out += ["", f"_{L['inferred']}:_ {why['text'].strip()}"]
    else:
        out += [why.get("text", "").strip(), "", f"_{L['sources']}: {'; '.join(why['sources'])}_"]
    out.append("")

    if r.get("how"):
        out += [f"### {L['how']}", "", r["how"].strip(), ""]

    if r.get("decisions"):
        out += [f"### {L['decisions']}", ""]
        for d in r["decisions"]:
            basis = L.get(d.get("basis", "inferred"), d.get("basis", ""))
            line = f"- **{d['decision']}** _({basis})_: {d.get('why', '').strip()}"
            if d.get("alternatives"):
                line += f" {L['alternatives']}: {d['alternatives']}"
            out.append(line)
        out.append("")

    if include_hunks and model["hunks"]:
        out += [f"### {L['key_changes']}", ""]
        for h in model["hunks"]:
            note = " ".join(h["note"].split())
            out += [f"<details><summary><code>{html.escape(h['file'])}</code>: {html.escape(note)}</summary>", "",
                    fence(h["text"], "diff"), "", "</details>"]
        out.append("")

    out += [f"### {L['files']}", "", "| | |", "|---|---|"]
    for key, note, fs in grouped_files(model):
        name = f"`{key}`" if len(fs) == 1 and fs[0]["path"] == key else f"`{key}` ({L['files_count'].format(n=len(fs))})"
        out.append(f"| {name} | {' '.join(note.split())} |")
    out.append("")

    if r.get("try_it"):
        out += [f"### {L['try_it']}", ""] + [f"{i}. {s}" for i, s in enumerate(r["try_it"], 1)] + [""]
    if r.get("unverified"):
        out += [f"### {L['unverified']}", ""] + [f"- {s}" for s in r["unverified"]] + [""]

    return "\n".join(out)


# ---------- entry point ----------


def render(report_path: Path, repo: Path | None = None,
           pr_md: bool = False) -> tuple[Path, Path | None, list[str]]:
    report_path = report_path.resolve()
    report_dir = report_path.parent
    if repo is None:
        repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    report = json.loads(report_path.read_text(encoding="utf-8"))
    model, warnings = build(report, report_dir, repo)
    L = LABELS.get(report.get("lang", "en"), LABELS["en"])

    html_path = report_dir / "showcase.html"
    html_path.write_text(render_html(model, L), encoding="utf-8")
    size = html_path.stat().st_size
    if size > MAX_HTML_BYTES:
        warnings.append(f"showcase.html is {size / 1e6:.1f} MB; GitHub attachments cap at 25 MB. Use JPEG/WebP screenshots or fewer of them.")

    if not pr_md:
        return html_path, None, warnings
    md = render_md(model, L)
    if len(md) > MAX_PR_CHARS:
        md = render_md(model, L, include_hunks=False)
        warnings.append("pr.md exceeded the GitHub comment limit; key-change diffs were left to showcase.html")
    if len(md) > MAX_PR_CHARS:
        raise ReportError(f"pr.md is {len(md)} characters even without diffs; GitHub allows 65536. "
                          "Trim the text evidence to the lines that show the result.")
    md_path = report_dir / "pr.md"
    md_path.write_text(md, encoding="utf-8")
    return html_path, md_path, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="Render report.json into showcase.html beside it.")
    ap.add_argument("report", type=Path)
    ap.add_argument("--repo", type=Path, help="repository root (default: the repo containing the current directory)")
    ap.add_argument("--pr-md", action="store_true",
                    help="also write pr.md, the image-free text to paste into a PR")
    args = ap.parse_args()
    try:
        html_path, md_path, warnings = render(args.report, args.repo, pr_md=args.pr_md)
    except ReportError as e:
        print("showcase: report not rendered\n" + str(e), file=sys.stderr)
        return 1
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    print(html_path)
    if md_path:
        print(md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
