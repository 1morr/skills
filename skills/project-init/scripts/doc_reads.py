"""量 repo 的文件實際被 agent 讀了幾次：掃 Claude Code 的對話紀錄，數每個文件被幾個 session 讀過。

    python doc_reads.py <repo> [--since YYYY-MM-DD] [--transcripts <目錄>]

算進這個 repo 的 session：工作目錄是 <repo>、它底下的目錄，或路徑含 `/workspaces/<repo 名>/` 的 worktree
（Orca 開的子 session）。子代理的讀取算在開它的 session 上。只列 Markdown 文件。
算兩種讀法：Read 工具（分整份與帶 offset / limit 的局部），以及 Bash 指令裡出現那個檔的路徑
（`cat`、`sed`、`grep` 這類；寫檔的指令也會算進來，所以這一欄是上限）。
輸出一張表，每列：碰過的 session 數、佔全部 session 的比例、整份讀、局部讀、shell 提到的次數、路徑；
最後列出 docs/、根目錄與 .scratch/*/spec.md 裡一次都沒被讀的文件。對話紀錄預設在
`$CLAUDE_CONFIG_DIR/projects`（沒設就是 `~/.claude/projects`）。只用標準函式庫。
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

MD_PATH = re.compile(r"[\w./@~+-]+\.md\b")


def belongs(cwd: str, repo: Path) -> bool:
    if not cwd:
        return False
    path = Path(cwd)
    return path == repo or repo in path.parents or f"/workspaces/{repo.name}/" in cwd.replace("\\", "/") + "/"


def relative(file_path: str, cwd: str, repo: Path) -> str:
    """讀的檔相對 repo 的路徑；不在 repo 或 worktree 裡的回傳空字串。"""
    for base in (cwd, str(repo)):
        if base and file_path.startswith(base.rstrip("/") + "/"):
            return file_path[len(base.rstrip("/")) + 1:]
    marker = f"/workspaces/{repo.name}/"
    if marker in file_path:
        rest = file_path.split(marker, 1)[1]
        return rest.split("/", 1)[1] if "/" in rest else ""
    return ""


def scan(transcripts: Path, repo: Path, since: str = "") -> tuple:
    """(session 數, {相對路徑: {"sessions": set, "full": int, "part": int, "shell": int}})"""
    reads = defaultdict(lambda: {"sessions": set(), "full": 0, "part": 0, "shell": 0})
    sessions = set()
    for file in sorted(transcripts.rglob("*.jsonl")):
        # 子代理的紀錄在 <session>/subagents/ 底下，歸到那個 session
        parts = file.relative_to(transcripts).parts
        session = (parts[0], parts[1].removesuffix(".jsonl")) if len(parts) > 1 else (parts[0],)
        try:
            lines = file.read_text(encoding="utf-8", errors="replace").split("\n")
        except OSError:
            continue
        for line in lines:
            if '"cwd"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            cwd = entry.get("cwd", "")
            if not belongs(cwd, repo) or (since and entry.get("timestamp", "")[:10] < since):
                continue
            sessions.add(session)
            content = (entry.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                given = block.get("input") or {}
                if block.get("name") == "Bash":
                    for token in set(MD_PATH.findall(str(given.get("command", "")))):
                        rel = relative(token, cwd, repo) if token.startswith("/") else token.removeprefix("./")
                        if rel and (repo / rel).is_file():
                            reads[rel]["sessions"].add(session)
                            reads[rel]["shell"] += 1
                    continue
                if block.get("name") != "Read":
                    continue
                rel = relative(str(given.get("file_path", "")), cwd, repo)
                if not rel.lower().endswith(".md"):
                    continue
                reads[rel]["sessions"].add(session)
                reads[rel]["part" if ("offset" in given or "limit" in given) else "full"] += 1
    return len(sessions), dict(reads)


def unread(repo: Path, reads: dict) -> list:
    found = list(repo.glob("*.md")) + list((repo / "docs").rglob("*.md")) + list((repo / ".scratch").glob("*/spec.md"))
    skip = ("docs/archive/", "docs/audit/")
    rels = sorted(p.relative_to(repo).as_posix() for p in found)
    auto = ("AGENTS.md", "CLAUDE.md")  # 每個 session 自動載入，不靠工具讀
    return [r for r in rels if r not in reads and not r.startswith(skip) and r not in auto]


def report(repo: Path, total: int, reads: dict) -> str:
    out = [f"{repo.name}：{total} 個 session", "", "| session | 比例 | 整份 | 局部 | shell | 文件 |", "| ---: | ---: | ---: | ---: | ---: | --- |"]
    for rel, r in sorted(reads.items(), key=lambda kv: (-len(kv[1]["sessions"]), kv[0])):
        n = len(r["sessions"])
        out.append(f"| {n} | {100 * n // total if total else 0}% | {r['full']} | {r['part']} | {r['shell']} | {rel} |")
    never = unread(repo, reads)
    out += ["", f"一次都沒被碰過的文件（{len(never)} 個；封存、審計快照與自動載入的指令檔不列）："] + [f"- {r}" for r in never]
    return "\n".join(out)


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="量 repo 的文件被 agent 讀了幾次")
    parser.add_argument("repo", type=Path)
    parser.add_argument("--since", default="")
    parser.add_argument("--transcripts", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    transcripts = args.transcripts or config / "projects"
    if not repo.is_dir() or not transcripts.is_dir():
        print(f"找不到目錄：{repo if not repo.is_dir() else transcripts}", file=sys.stderr)
        return 1
    total, reads = scan(transcripts, repo, args.since)
    print(report(repo, total, reads))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
