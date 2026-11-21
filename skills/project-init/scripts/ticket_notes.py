"""印出與封存一個里程碑各張票留在 `## Comments` 之後的紀錄（共用 skeleton_parser）。

    python3 ticket_notes.py <里程碑目錄名，如 m0> [repo 根目錄]
    python3 ticket_notes.py --archive <里程碑目錄名> [repo 根目錄] [-o <輸出檔>] [--user-trial <文字>] [--stdout]
    python3 ticket_notes.py --changelog <里程碑目錄名> [repo 根目錄]

`--archive` 預設直接把 `docs/progress.md`、`docs/decisions.md` 裡屬於該里程碑（及首個封存時的「框架」）的紀錄連同票面紀錄彙整寫出至
`docs/archive/<M>.md`（並從原檔移走已封存的列），取代手動剪貼；加 `--stdout` 則只印出封存區塊不改檔。
只用標準函式庫。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import skeleton_parser as sp  # noqa: E402

SESSION_NOTE = sp.SESSION_NOTE
DECISION_NOTE = sp.DECISION_NOTE
CHANGE_NOTE = sp.CHANGE_NOTE
WAITING = sp.WAITING
KINDS = sp.KINDS
label_of = sp.label_of


def ticket_notes(path: Path) -> dict:
    t = sp.parse_ticket(path, git_date_fallback=True)
    return {
        "number": t["number"],
        "title": t["bare_title"],
        "date": t["date"],
        "sessions": t["sessions"],
        "decisions": [(said, "" if decider == sp.UNMARKED else decider) for said, decider, _ in t["decisions"]],
        "changes": t["changes"],
        "waiting": t["open_questions_even_if_closed"],
    }


def notes(root: Path, name: str) -> list:
    issues = root / sp.SCRATCH_DIR / name / "issues"
    if not issues.is_dir():
        return []
    found = [ticket_notes(p) for p in sorted(issues.glob("*.md"))]
    return sorted(
        (t for t in found if t["sessions"] or t["decisions"] or t["changes"] or t["waiting"]),
        key=lambda t: (t["date"], t["number"]),
    )


def archive(root: Path, name: str) -> tuple:
    """回傳 (票面 session 表格列, 票面〈決定〉條目)。"""
    label, rows, decided = label_of(name), [], []
    for t in notes(root, name):
        for said in t["sessions"]:
            rows.append("| %s | %s %s | %s | |" % (t["date"], label, t["number"], said.replace("|", "\\|")))
        for said, decider in t["decisions"]:
            decided.append("- %s %s 票 %s%s：%s" % (t["date"], label, t["number"], f"（{decider}）" if decider else "", said))
    return rows, decided


def _belongs_to_milestone(tag: str, label: str, include_framework: bool) -> bool:
    clean = sp.plain(tag)
    if not clean:
        return False
    first = re.split(r"[\s（(]", clean)[0]
    if first.lower() == label.lower():
        return True
    if include_framework and first == "框架":
        return True
    return False


def write_archive(root: Path, name: str, output: Path | None = None, user_trial: str = "", stdout_only: bool = False) -> tuple:
    """彙整 progress.md、decisions.md 與票面紀錄，產生 docs/archive/<Label>.md（stdout_only=True 時不寫檔）。"""
    label = label_of(name)
    archive_dir = root / "docs" / "archive"
    target = output or (archive_dir / f"{label}.md")
    existing_archives = [p for p in archive_dir.glob("*.md") if p.resolve() != target.resolve()] if archive_dir.is_dir() else []
    include_framework = len(existing_archives) == 0

    ticket_rows, ticket_decisions = archive(root, name)
    if stdout_only and not (root / sp.PROGRESS_REL).is_file() and not (root / sp.DECISIONS_REL).is_file():
        text = "\n".join([f"## {sp.SESSIONS_HEADING}", *ticket_rows, "", f"## {sp.ARCHIVED_DECISIONS_HEADING}", *ticket_decisions])
        return target, text

    # 1. 擷取並過濾 docs/progress.md
    table_header = ["| 日期 | 票 | 結果 | 下一步 |", "| --- | --- | --- | --- |"]
    moved_rows = []
    progress_path = root / sp.PROGRESS_REL
    new_progress_text = None
    if progress_path.is_file():
        prog_text = sp.read_text(progress_path)
        secs = sp.numbered_sections(prog_text)
        rows = sp.table_rows(secs.get(sp.SESSIONS_HEADING, []), unescape_pipe=False)
        if len(rows) >= 2:
            head = rows[0][1]
            ticket_col = head.index("票") if "票" in head else 1
            table_header = [
                "| " + " | ".join(head) + " |",
                "| " + " | ".join("---" for _ in head) + " |",
            ]
            remove_line_nos = set()
            for line_no, cells in rows[1:]:
                if sp.is_separator_row("|" + "|".join(cells) + "|"):
                    continue
                tag = cells[ticket_col] if len(cells) > ticket_col else ""
                if _belongs_to_milestone(tag, label, include_framework):
                    moved_rows.append("| " + " | ".join(cells) + " |")
                    remove_line_nos.add(line_no)
            if remove_line_nos:
                kept_lines = [l for i, l in enumerate(prog_text.split("\n"), 1) if i not in remove_line_nos]
                new_progress_text = "\n".join(kept_lines)

    # 避免已存在於 progress.md 的票重複列入
    existing_tickets = set()
    for r in moved_rows:
        parts = sp.split_cells(r)
        if len(parts) >= 2:
            existing_tickets.add(sp.plain(parts[1]).upper())
    dedup_ticket_rows = []
    for r in ticket_rows:
        parts = sp.split_cells(r)
        if len(parts) < 2 or sp.plain(parts[1]).upper() not in existing_tickets:
            dedup_ticket_rows.append(r)

    # 2. 擷取並過濾 docs/decisions.md
    moved_decisions = []
    decisions_path = root / sp.DECISIONS_REL
    new_decisions_text = None
    if decisions_path.is_file():
        dec_text = sp.read_text(decisions_path)
        secs = sp.numbered_sections(dec_text)
        remove_dec_nos = set()
        for line_no, line in secs.get(sp.DECISIONS_HEADING, []):
            m = re.match(r"^- \d{4}-\d{2}-\d{2}\s+(.*)$", line)
            if not m:
                continue
            head_part = m.group(1).partition("：")[0]
            if _belongs_to_milestone(sp.strip_decider(head_part), label, include_framework):
                moved_decisions.append(line)
                remove_dec_nos.add(line_no)
        if remove_dec_nos:
            kept_lines = [l for i, l in enumerate(dec_text.split("\n"), 1) if i not in remove_dec_nos]
            new_decisions_text = "\n".join(kept_lines)

    # 3. 決定〈使用者試〉內容
    trial_body = user_trial.strip()
    if not trial_body and target.is_file():
        old_secs = sp.sections(sp.read_text(target))
        existing_trial = "\n".join(old_secs.get(sp.USER_TRIAL_HEADING, [])).strip()
        if existing_trial:
            trial_body = existing_trial
    if not trial_body:
        trial_body = "- 待填寫試用結果。"

    session_block = "\n".join(table_header + moved_rows + dedup_ticket_rows)
    decision_block = "\n".join(moved_decisions + ticket_decisions)
    blocks = [
        f"# {label} 封存",
        f"## {sp.SESSIONS_HEADING}\n\n{session_block}",
        f"## {sp.ARCHIVED_DECISIONS_HEADING}" + (f"\n\n{decision_block}" if decision_block else ""),
        f"## {sp.USER_TRIAL_HEADING}\n\n{trial_body}",
    ]
    archive_content = "\n\n".join(blocks) + "\n"

    if not stdout_only:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(archive_content, encoding="utf-8")
        if new_progress_text is not None:
            progress_path.write_text(new_progress_text, encoding="utf-8")
        if new_decisions_text is not None:
            decisions_path.write_text(new_decisions_text, encoding="utf-8")
    return target, archive_content


def changelog(root: Path, name: str) -> list:
    found = [change for t in notes(root, name) for change in t["changes"]]
    out = []
    for kind in KINDS:
        entries = [f"- **{feature}**：{said}" for k, feature, said in found if k == kind]
        if entries:
            out += ([""] if out else []) + [f"### {kind}", *entries]
    return out


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="查詢或封存里程碑各張票的 Comments 紀錄")
    parser.add_argument("milestone", help="里程碑目錄名（例如 m0）")
    parser.add_argument("repo", nargs="?", type=Path, default=Path.cwd(), help="repo 根目錄（預設目前目錄）")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--archive", action="store_true", help="彙整票面與進度／決策紀錄至 docs/archive/<M>.md")
    group.add_argument("--changelog", action="store_true", help="印出要併入 CHANGELOG.md [Unreleased] 的條目")
    parser.add_argument("-o", "--output", type=Path, help="封存輸出路徑（預設 docs/archive/<M>.md）")
    parser.add_argument("--user-trial", default="", help="封存檔〈使用者試〉段落內容")
    parser.add_argument("--stdout", action="store_true", help="搭配 --archive 時只印出內容、不寫入檔案")
    return parser


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2

    name, root = args.milestone, args.repo
    if not (root / sp.SCRATCH_DIR / name / "issues").is_dir():
        print(f"找不到 .scratch/{name}/issues/", file=sys.stderr)
        return 1
    if args.changelog:
        print("\n".join(changelog(root, name)))
        return 0
    if args.archive:
        target, content = write_archive(root, name, output=args.output, user_trial=args.user_trial, stdout_only=args.stdout)
        if args.stdout:
            print(content, end="" if content.endswith("\n") else "\n")
        else:
            try:
                shown = target.relative_to(root.resolve())
            except ValueError:
                shown = target
            print(shown)
        return 0

    found = notes(root, name)
    for t in found:
        print(f"{label_of(name)} {t['number']} {t['title']}（{t['date']}）")
        for said in t["sessions"]:
            print(f"  {SESSION_NOTE}{said}")
        for said, decider in t["decisions"]:
            print(f"  {DECISION_NOTE}{said}" + (f"（{decider}）" if decider else ""))
        for change in t["changes"]:
            print(f"  {CHANGE_NOTE}" + "｜".join(change))
        for asked in t["waiting"]:
            print(f"  {WAITING}{asked}")
    if not found:
        print(f"{label_of(name)} 的票還沒有留紀錄")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
