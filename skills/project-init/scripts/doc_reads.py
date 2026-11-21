"""量 repo 的文件實際被 agent 讀了幾次：掃對話紀錄（Claude Code 與 Antigravity），數每個文件被幾個 session 讀過。

    python doc_reads.py <repo> [--since YYYY-MM-DD] [--transcripts <目錄>] [--harness auto|claude|antigravity]

算進這個 repo 的 session：工作目錄（或工具存取的路徑）是 <repo>、它底下的目錄，或路徑含 `/workspaces/<repo 名>/`
的 worktree（Orca 開的子 session）。子代理的讀取算在開它的 session 上。只列 Markdown 文件。
算兩種讀法：
- 讀檔工具：Claude Code 的 `Read`（分整份與帶 offset / limit 的局部）、Antigravity 的 `read_file`
  （分整份與帶 StartLine / EndLine / ByteOffset 的局部）。
- shell 工具：Claude Code 的 `Bash`、Antigravity 的 `run_command` 指令裡出現那個檔的路徑
  （`cat`、`sed`、`grep` 這類；寫檔的指令也會算進來，所以這一欄是上限）。
輸出一張表，每列：碰過的 session 數、佔全部 session 的比例、整份讀、局部讀、shell 提到的次數、路徑；
最後列出 docs/、根目錄與 .scratch/*/spec.md 裡一次都沒被讀的文件。
預設目錄：Claude Code 在 `$CLAUDE_CONFIG_DIR/projects`（沒設就是 `~/.claude/projects`），
Antigravity 在 `$ANTIGRAVITY_DIR/brain`（沒設就是 `~/.gemini/antigravity-cli/brain`）；
`--harness auto`（預設）掃兩者中存在的目錄。只用標準函式庫。
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

MD_PATH = re.compile(r"[\w./@~+-]+\.md\b")
ABS_PATH = re.compile(r"(?:^|[\s'\"=])(/[^\s'\"`;|&<>]+)")
AGY_PATH_KEYS = ("Path", "TargetFile", "DirectoryPath", "SearchPath", "AbsolutePath", "Cwd")
AGY_PARTIAL_KEYS = ("StartLine", "EndLine", "ByteOffset")


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


def _unquote_arg(val) -> str:
    """Antigravity 的 transcript.jsonl 會把工具參數再包一層 JSON 字串；兩種寫法都解。"""
    if not isinstance(val, str):
        return str(val) if val is not None else ""
    if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
        try:
            decoded = json.loads(val)
            if isinstance(decoded, str):
                return decoded
        except ValueError:
            pass
    return val


def _record_shell(command: str, cwd: str, repo: Path, session, reads: dict) -> None:
    for token in set(MD_PATH.findall(command)):
        rel = relative(token, cwd, repo) if token.startswith("/") else token.removeprefix("./")
        if rel and (repo / rel).is_file():
            reads[rel]["sessions"].add(session)
            reads[rel]["shell"] += 1


def _scan_claude(transcripts: Path, repo: Path, since: str, sessions: set, reads: dict) -> None:
    for file in sorted(transcripts.rglob("*.jsonl")):
        if file.name in ("transcript.jsonl", "transcript_full.jsonl"):
            continue
        # 子代理的紀錄在 <session>/subagents/ 底下，歸到那個 session
        parts = file.relative_to(transcripts).parts
        session = ("claude", parts[0], parts[1].removesuffix(".jsonl")) if len(parts) > 1 else ("claude", parts[0])
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
                    _record_shell(str(given.get("command", "")), cwd, repo, session, reads)
                    continue
                if block.get("name") != "Read":
                    continue
                rel = relative(str(given.get("file_path", "")), cwd, repo)
                if not rel.lower().endswith(".md"):
                    continue
                reads[rel]["sessions"].add(session)
                reads[rel]["part" if ("offset" in given or "limit" in given) else "full"] += 1


def _agy_files(transcripts: Path, strict: bool) -> list:
    found = sorted(p for p in transcripts.rglob("transcript.jsonl") if p.is_file())
    if found or strict:
        return found
    return sorted(p for p in transcripts.rglob("*.jsonl") if p.is_file() and p.name != "transcript_full.jsonl")


def _scan_antigravity(transcripts: Path, repo: Path, since: str, sessions: set, reads: dict, strict: bool = False) -> None:
    for file in _agy_files(transcripts, strict=strict):
        parts = file.relative_to(transcripts).parts
        session = ("antigravity", parts[0]) if len(parts) > 1 else ("antigravity", file.stem)
        try:
            lines = file.read_text(encoding="utf-8", errors="replace").split("\n")
        except OSError:
            continue
        in_repo = False
        session_cwd = ""
        file_reads = []
        commands = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            ts = str(entry.get("created_at") or entry.get("timestamp") or "")
            if since and ts[:10] < since:
                continue
            cwd = entry.get("cwd", "")
            if belongs(cwd, repo):
                in_repo = True
                session_cwd = session_cwd or cwd
            tool_calls = entry.get("tool_calls")
            for tc in tool_calls if isinstance(tool_calls, list) else []:
                if not isinstance(tc, dict):
                    continue
                name = tc.get("name")
                given = tc.get("args") or {}
                if not isinstance(given, dict):
                    continue
                for key in AGY_PATH_KEYS:
                    if key in given:
                        p = _unquote_arg(given[key])
                        if belongs(p, repo):
                            in_repo = True
                if name == "read_file":
                    p = _unquote_arg(given.get("Path", ""))
                    if p:
                        partial = any(k in given for k in AGY_PARTIAL_KEYS)
                        file_reads.append((p, partial))
                elif name == "run_command":
                    cmd = _unquote_arg(given.get("CommandLine", ""))
                    if cmd:
                        for match in ABS_PATH.findall(cmd):
                            if belongs(match, repo):
                                in_repo = True
                        commands.append(cmd)
        if not in_repo:
            continue
        sessions.add(session)
        for path_str, partial in file_reads:
            rel = relative(path_str, session_cwd, repo)
            if not rel.lower().endswith(".md"):
                continue
            reads[rel]["sessions"].add(session)
            reads[rel]["part" if partial else "full"] += 1
        for cmd in commands:
            _record_shell(cmd, session_cwd, repo, session, reads)


def _scan_into(transcripts: Path, repo: Path, since: str, harness: str, sessions: set, reads: dict) -> None:
    if harness in ("auto", "claude"):
        _scan_claude(transcripts, repo, since, sessions, reads)
    if harness in ("auto", "antigravity"):
        _scan_antigravity(transcripts, repo, since, sessions, reads, strict=(harness == "auto"))


def scan(transcripts: Path, repo: Path, since: str = "", harness: str = "auto") -> tuple:
    """(session 數, {相對路徑: {"sessions": set, "full": int, "part": int, "shell": int}})"""
    reads = defaultdict(lambda: {"sessions": set(), "full": 0, "part": 0, "shell": 0})
    sessions = set()
    _scan_into(transcripts, repo, since, harness, sessions, reads)
    return len(sessions), dict(reads)


def default_sources(harness: str) -> list:
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    agy = Path(os.environ.get("ANTIGRAVITY_DIR") or Path.home() / ".gemini" / "antigravity-cli") / "brain"
    if harness == "claude":
        return [("claude", claude)]
    if harness == "antigravity":
        return [("antigravity", agy)]
    return [("claude", claude), ("antigravity", agy)]


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
    parser.add_argument("--harness", choices=("auto", "claude", "antigravity"), default="auto")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"找不到目錄：{repo}", file=sys.stderr)
        return 1
    if args.transcripts:
        if not args.transcripts.is_dir():
            print(f"找不到目錄：{args.transcripts}", file=sys.stderr)
            return 1
        total, reads = scan(args.transcripts, repo, args.since, harness=args.harness)
    else:
        sources = default_sources(args.harness)
        existing = [(h, d) for h, d in sources if d.is_dir()]
        if not existing:
            print("找不到目錄：" + "、".join(str(d) for _, d in sources), file=sys.stderr)
            return 1
        reads = defaultdict(lambda: {"sessions": set(), "full": 0, "part": 0, "shell": 0})
        sessions = set()
        for h, d in existing:
            _scan_into(d, repo, args.since, h, sessions, reads)
        total, reads = len(sessions), dict(reads)
    print(report(repo, total, reads))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
