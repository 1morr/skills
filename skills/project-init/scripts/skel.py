"""共用專案骨架統一 CLI 入口（暴露為 console script `1morr-skel`）。

    1morr-skel check [repo]
    1morr-skel next [repo]
    1morr-skel notes [--archive] [--changelog] <milestone> [repo] [-o <path>] [--user-trial <text>] [--stdout]
    1morr-skel dashboard [repo...] [--serve] [--host 127.0.0.1] [--port 8765] [-o <output.html>]

亦可直接以 `python3 skills/project-init/scripts/skel.py <subcommand> ...` 呼叫。只用標準函式庫。
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import check_docs  # noqa: E402
import dashboard  # noqa: E402
import next_step  # noqa: E402
import ticket_notes  # noqa: E402

SUBCOMMANDS = {
    "check": check_docs.main,
    "next": next_step.main,
    "notes": ticket_notes.main,
    "dashboard": dashboard.main,
}

USAGE = """用法：1morr-skel <check|next|notes|dashboard> [參數...]

子命令：
  check [repo]                             檢查狀態機與工程閘門硬契約（字元上限僅印 WARN）
  next [repo]                              查詢目前待決問題、下一張可做的票與後續佇列
  notes [--archive|--changelog] <M> [repo] 查看里程碑票面紀錄，或直接封存寫出至 docs/archive/<M>.md
  dashboard [repo...] [--serve] [-o FILE]  產生靜態專案總覽頁，或啟動每 3 秒自動重讀的本機伺服器
"""


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE.strip())
        return 0
    cmd, rest = argv[0], argv[1:]
    fn = SUBCOMMANDS.get(cmd)
    if fn is None:
        print(f"未知的子命令：{cmd}\n\n{USAGE.strip()}", file=sys.stderr)
        return 2
    return fn(rest)


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
