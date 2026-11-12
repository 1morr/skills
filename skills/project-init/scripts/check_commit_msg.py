"""檢查 commit message 的標題：Conventional Commits、小寫開頭、無句號、不超過 72 字元。

    python check_commit_msg.py <commit message 檔>      給 commit-msg hook 用
    python check_commit_msg.py --subject "<標題>"

合格就 exit 0；不合格把原因印到 stderr、exit 1。git 預設的合併與 revert 訊息（Merge …、Revert "…"）照收。
type 的清單和 1morr plugin 的 orca/scripts/merge-ticket.sh 相同：協調者合併前用同一條規則擋。
只用標準函式庫。
"""

import re
import sys

TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")
MAX = 72
SUBJECT = re.compile(r"^(%s)(\([^)]+\))?!?: [^A-Z\s]" % "|".join(TYPES))
GIT_DEFAULT = re.compile(r'^(Merge |Revert ")')


def problems(subject: str) -> list:
    if GIT_DEFAULT.match(subject):
        return []
    out = []
    if len(subject) > MAX:
        out.append(f"標題 {len(subject)} 字元，上限 {MAX}：塞不下就拆 commit")
    if not SUBJECT.match(subject):
        out.append("標題要寫成 <type>(<scope>): <subject>，subject 小寫開頭；type 是 " + "、".join(TYPES))
    elif subject.rstrip().endswith("."):
        out.append("標題結尾不加句號")
    return out


def subject_of(message: str) -> str:
    for line in message.split("\n"):
        if line.strip() and not line.startswith("#"):
            return line.rstrip()
    return ""


def main(argv) -> int:
    if len(argv) == 2 and argv[0] == "--subject":
        subject = argv[1]
    elif len(argv) == 1:
        with open(argv[0], encoding="utf-8") as f:
            subject = subject_of(f.read())
    else:
        print(__doc__, file=sys.stderr)
        return 2
    found = problems(subject)
    for p in found:
        print(f"commit message：{p}\n  {subject}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
