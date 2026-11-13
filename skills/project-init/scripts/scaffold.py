"""把 project-init 的範本與閘門寫進專案：新檔照抄並填好佔位，已存在的檔不動、列出來。

    python scaffold.py --list                                   # 印對照表：範本<TAB>專案裡的路徑
    python scaffold.py <專案目錄> --project <名稱> --one-line <一句話，句號結尾> --main-branch <預設分支> [--date YYYY-MM-DD]

佔位：{{PROJECT}}、{{ONE_LINE}}、{{DATE}}（預設今天）、{{MAIN_BRANCH}}。`.githooks/` 的檔設成可執行；
docs/adr、docs/research、docs/archive、scripts/experiments 不存在時各建一個 .gitkeep。
每個檔印一行：`寫入<TAB><路徑>`，或 `已存在<TAB><路徑><TAB><範本的完整路徑>`（內容沒有動，缺的段落要另外補）。
範本裡的 `<!-- -->` 註解與標了「只在…時保留」的段落照樣寫進去，留給呼叫的人照專案的情況刪。
只用標準函式庫。
"""

import argparse
import datetime
import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "instructions.md": "AGENTS.md",
    "design-brief.md": "docs/design-brief.md",
    "architecture.md": "ARCHITECTURE.md",
    "roadmap.md": "docs/roadmap.md",
    "progress.md": "docs/progress.md",
    "decisions.md": "docs/decisions.md",
    "development.md": "docs/development.md",
    "ticket.md": "docs/agents/ticket-template.md",
    "issue-tracker.md": "docs/agents/issue-tracker.md",
    "triage-labels.md": "docs/agents/triage-labels.md",
    "domain.md": "docs/agents/domain.md",
    "milestone.md": "docs/agents/milestone.md",
    "gitattributes": ".gitattributes",
    "ci.yml": ".github/workflows/ci.yml",
    "commit-msg": ".githooks/commit-msg",
    "pre-commit": ".githooks/pre-commit",
}
# 照抄、不填佔位的閘門
GATES = {
    "scripts/check_docs.py": "scripts/check_docs.py",
    "scripts/check_commit_msg.py": "scripts/check_commit_msg.py",
    "scripts/docs_moved_lines.py": "scripts/docs_moved_lines.py",
    "scripts/ticket_notes.py": "scripts/ticket_notes.py",
    "tests/test_check_docs.py": "scripts/tests/test_check_docs.py",
    "tests/test_check_commit_msg.py": "scripts/tests/test_check_commit_msg.py",
    "tests/test_docs_moved_lines.py": "scripts/tests/test_docs_moved_lines.py",
    "tests/test_ticket_notes.py": "scripts/tests/test_ticket_notes.py",
}
KEPT_DIRS = ("docs/adr", "docs/research", "docs/archive", "scripts/experiments")
PLACEHOLDER = re.compile(r"\{\{(PROJECT|ONE_LINE|DATE|MAIN_BRANCH)\}\}")


def sources() -> list:
    """[(範本的路徑, 專案裡的相對路徑, 要不要填佔位)]"""
    return ([(SKILL / "templates" / name, rel, True) for name, rel in TEMPLATES.items()]
            + [(SKILL / name, rel, False) for name, rel in GATES.items()])


def scaffold(root: Path, values: dict) -> list:
    """[(寫入或已存在, 相對路徑, 範本路徑)]"""
    out = []
    for source, rel, fill in sources():
        target = root / rel
        if target.exists():
            out.append(("已存在", rel, source))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if fill:
            with open(target, "w", encoding="utf-8", newline="\n") as f:  # hook 在 Windows 也要是 LF
                f.write(PLACEHOLDER.sub(lambda m: values[m.group(1)], source.read_text(encoding="utf-8")))
        else:
            shutil.copyfile(source, target)
        if rel.startswith(".githooks/"):
            target.chmod(0o755)
        out.append(("寫入", rel, source))
    for rel in KEPT_DIRS:
        if not (root / rel).exists():
            (root / rel).mkdir(parents=True)
            (root / rel / ".gitkeep").write_text("", encoding="utf-8")
            out.append(("寫入", f"{rel}/.gitkeep", None))
    return out


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="把 project-init 的範本與閘門寫進專案")
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--one-line")
    parser.add_argument("--main-branch")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args(argv)
    if args.list:
        for source, rel, _ in sources():
            print(f"{source}\t{rel}")
        return 0
    if not (args.root and args.project and args.one_line and args.main_branch):
        parser.error("要給專案目錄、--project、--one-line、--main-branch")
    if not args.root.is_dir():
        print(f"找不到目錄：{args.root}", file=sys.stderr)
        return 1
    values = {"PROJECT": args.project, "ONE_LINE": args.one_line, "DATE": args.date, "MAIN_BRANCH": args.main_branch}
    for state, rel, source in scaffold(args.root, values):
        print("\t".join([state, rel] + ([str(source)] if state == "已存在" else [])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
