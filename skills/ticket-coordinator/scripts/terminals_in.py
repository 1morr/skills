# 用法：orca terminal list --json | W=<worktree 路徑> python3 terminals_in.py  —— 印 worktree 路徑完全等於 $W 的終端 handle
import json, os, sys


def handles(listing, worktree):
    norm = lambda p: os.path.normpath(p.replace("\\", "/"))
    return [t["handle"] for t in listing["result"]["terminals"] if norm(t.get("worktreePath") or "") == norm(worktree)]


if __name__ == "__main__":
    print("\n".join(handles(json.load(sys.stdin), os.environ["W"])))
