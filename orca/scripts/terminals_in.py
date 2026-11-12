# 用法：orca terminal list --json | W=<worktree 路徑> python3 terminals_in.py  —— 印 worktree 路徑完全等於 $W 的終端 handle
import json, os, sys


def norm(p):
    # 斜線統一；Windows 的磁碟代號不分大小寫（Orca 可能回 c: 或 C:）
    p = os.path.normpath(p.replace("\\", "/")).replace("\\", "/")
    return p[0].lower() + p[1:] if len(p) > 1 and p[1] == ":" else p


def handles(listing, worktree):
    return [t["handle"] for t in listing["result"]["terminals"] if norm(t.get("worktreePath") or "") == norm(worktree)]


if __name__ == "__main__":
    print("\n".join(handles(json.load(sys.stdin), os.environ["W"])))
