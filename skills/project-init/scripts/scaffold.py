"""把 project-init 的範本與工程護欄寫進專案：零 Python 腳本拷貝，已存在的檔不動並列出來。

    python3 scaffold.py --list [--with-scratch]
    python3 scaffold.py <專案目錄> --project <名稱> --one-line <一句話，句號結尾> --main-branch <預設分支> [--date YYYY-MM-DD] [--with-scratch] [--with-changelog]

預設寫入「通用基礎工程層」（共 12 個檔案，支援 GitHub Issues / Linear 等任意 tracker，業務 repo 內 0 行 Python 腳本與測試）：
  AGENTS.md、ARCHITECTURE.md、docs/design-brief.md、docs/development.md、docs/roadmap.md、docs/progress.md、
  docs/decisions.md、.gitignore、.gitattributes、.github/workflows/ci.yml、.githooks/commit-msg、.githooks/pre-commit。
加 `--with-scratch` 額外寫入選配 `.scratch/` 本機跑票與變更紀錄範本（docs/agents/* 與 CHANGELOG.md）。
佔位：{{PROJECT}}、{{ONE_LINE}}、{{DATE}}（預設今天）、{{MAIN_BRANCH}}。`.githooks/` 的檔設為可執行（0755）。
只用標準函式庫。
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]

# 通用基礎工程層（預設寫入，精確 12 個檔案，0 行 Python 腳本）
TEMPLATES = {
    "instructions.md": "AGENTS.md",
    "architecture.md": "ARCHITECTURE.md",
    "design-brief.md": "docs/design-brief.md",
    "development.md": "docs/development.md",
    "roadmap.md": "docs/roadmap.md",
    "progress.md": "docs/progress.md",
    "decisions.md": "docs/decisions.md",
    "gitignore": ".gitignore",
    "gitattributes": ".gitattributes",
    "ci.yml": ".github/workflows/ci.yml",
    "commit-msg": ".githooks/commit-msg",
    "pre-commit": ".githooks/pre-commit",
}

# 選配 `.scratch/` 跑票與封存層
SCRATCH_TEMPLATES = {
    "milestone.md": "docs/agents/milestone.md",
    "ticket.md": "docs/agents/ticket-template.md",
    "issue-tracker.md": "docs/agents/issue-tracker.md",
    "triage-labels.md": "docs/agents/triage-labels.md",
    "domain.md": "docs/agents/domain.md",
    "changelog.md": "CHANGELOG.md",
}

# 下游業務 repo 零 Python 腳本拷貝
GATES: dict[str, str] = {}
KEPT_DIRS: tuple[str, ...] = ()
PLACEHOLDER = re.compile(r"\{\{(PROJECT|ONE_LINE|DATE|MAIN_BRANCH)\}\}")


def sources(with_scratch: bool = False, with_changelog: bool = False) -> list:
    """[(範本路徑, 專案相對路徑, 要不要填佔位)]"""
    selected = dict(TEMPLATES)
    if with_scratch:
        selected.update(SCRATCH_TEMPLATES)
    elif with_changelog:
        selected["changelog.md"] = SCRATCH_TEMPLATES["changelog.md"]
    return [(SKILL / "templates" / name, rel, True) for name, rel in selected.items()]


def scaffold(root: Path, values: dict, with_scratch: bool = False, with_changelog: bool = False) -> list:
    """[(寫入或已存在, 相對路徑, 範本路徑)]"""
    out = []
    for source, rel, fill in sources(with_scratch=with_scratch, with_changelog=with_changelog):
        target = root / rel
        if target.exists():
            out.append(("已存在", rel, source))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8")
        if fill:
            text = PLACEHOLDER.sub(lambda m: values[m.group(1)], text)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        if rel.startswith(".githooks/"):
            target.chmod(0o755)
        out.append(("寫入", rel, source))
    return out


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="把 project-init 的範本與工程護欄寫進專案")
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--with-scratch", action="store_true", help="額外寫入選配 .scratch/ 跑票層與 CHANGELOG 範本")
    parser.add_argument("--with-changelog", action="store_true", help="額外寫入 CHANGELOG.md 範本")
    parser.add_argument("--project")
    parser.add_argument("--one-line")
    parser.add_argument("--main-branch")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args(argv)
    if args.list:
        for source, rel, _ in sources(with_scratch=args.with_scratch, with_changelog=args.with_changelog):
            print(f"{source}\t{rel}")
        return 0
    if not (args.root and args.project and args.one_line and args.main_branch):
        parser.error("要給專案目錄、--project、--one-line、--main-branch")
    if not args.root.is_dir():
        print(f"找不到目錄：{args.root}", file=sys.stderr)
        return 1
    values = {"PROJECT": args.project, "ONE_LINE": args.one_line, "DATE": args.date, "MAIN_BRANCH": args.main_branch}
    for state, rel, source in scaffold(args.root, values, with_scratch=args.with_scratch, with_changelog=args.with_changelog):
        print("\t".join([state, rel] + ([str(source)] if state == "已存在" else [])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
