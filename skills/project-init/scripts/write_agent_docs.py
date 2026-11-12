"""替新專案寫 docs/agents/ 的三個檔：做的事和 mattpocock 的 /setup-matt-pocock-skills 選「local markdown、
預設標籤、單一名詞表」時一樣，再把票的慣例換成里程碑的版本。

    python write_agent_docs.py <專案根目錄> [--source <setup-matt-pocock-skills 的資料夾>]

種子範本不放在這個 skill 裡，執行時從已安裝的 mattpocock-skills 讀，內容才會是使用者裝的那一版。
找的順序：--source；Claude Code 的 plugins/installed_plugins.json 記的安裝路徑（最近更新的優先）；
plugins/cache/*/mattpocock-skills/*/ 底下；~/.claude/skills 與 ~/.agents/skills 裡連結過來的。
設定目錄是 $CLAUDE_CONFIG_DIR，沒設就是 ~/.claude。

  exit 0  寫好了。每個檔印一行「寫了」或「已存在，沒動」，最後印種子來自哪裡
  exit 2  做不到，什麼都沒寫：找不到種子範本，或它的格式變了（沒有 `## Conventions` 段）。
          這時請使用者自己執行 /setup-matt-pocock-skills，再照 SKILL.md 第 4 步的退路做
只用標準函式庫。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKILL = "setup-matt-pocock-skills"
PLUGIN = "mattpocock-skills"
# 種子檔名 → 寫到專案的 docs/agents/ 底下叫什麼
SEEDS = {"issue-tracker-local.md": "issue-tracker.md", "triage-labels.md": "triage-labels.md", "domain.md": "domain.md"}
CONVENTIONS = Path(__file__).resolve().parents[1] / "templates" / "issue-tracker-conventions.md"
# 〈Conventions〉標題到下一個 ## 之間的清單
LIST = re.compile(r"(^## Conventions[ \t]*\n)(.*?)(?=^## )", re.S | re.M)
PUBLISH = ("`.scratch/<feature-slug>/` (creating", "`.scratch/<milestone>/issues/` (creating")


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def complete(d: Path) -> bool:
    return all((d / name).is_file() for name in SEEDS)


def candidates(config: Path, home: Path):
    """可能放著 setup skill 的資料夾，照可信度排。"""
    try:
        plugins = json.loads((config / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))["plugins"]
        entries = [e for key, value in plugins.items() if key.split("@")[0] == PLUGIN for e in value if isinstance(e, dict)]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        entries = []
    for e in sorted(entries, key=lambda e: str(e.get("lastUpdated") or ""), reverse=True):
        if e.get("installPath"):
            yield from sorted(Path(e["installPath"]).glob(f"skills/*/{SKILL}"))
    cached = sorted((config / "plugins" / "cache").glob(f"*/{PLUGIN}/*/skills/*/{SKILL}"), key=lambda p: p.stat().st_mtime, reverse=True)
    yield from cached
    yield config / "skills" / SKILL
    yield home / ".agents" / "skills" / SKILL


def locate(config=None, home=None):
    for d in candidates(config or config_dir(), home or Path.home()):
        if complete(d):
            return d
    return None


def conventions() -> str:
    text = CONVENTIONS.read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->\n?", "", text, flags=re.S).strip() + "\n"


def issue_tracker(seed: str):
    """把種子的〈Conventions〉清單換成里程碑的慣例；種子沒有那一段就回傳 None。"""
    if not LIST.search(seed):
        return None
    out = LIST.sub(lambda m: m.group(1) + "\n" + conventions() + "\n", seed, count=1)
    return out.replace(*PUBLISH)


def write(project: Path, source: Path):
    """回傳 (訊息清單, 做不到的原因或 None)。先算好全部內容再寫，做不到時一個檔都不寫。"""
    if not complete(source):
        return [], f"{source} 裡沒有 {'、'.join(SEEDS)}"
    contents = {}
    for seed, target in SEEDS.items():
        text = (source / seed).read_text(encoding="utf-8")
        if target == "issue-tracker.md":
            text = issue_tracker(text)
            if text is None:
                return [], f"{source / seed} 沒有 `## Conventions` 段：種子範本的格式變了"
        contents[target] = text
    out = []
    agents = project / "docs" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    for target, text in contents.items():
        dest = agents / target
        if dest.exists():
            out.append(f"已存在，沒動：docs/agents/{target}")
        else:
            dest.write_text(text, encoding="utf-8")
            out.append(f"寫了：docs/agents/{target}")
    return out, None


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # Windows 終端機預設不是 UTF-8
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project", type=Path)
    ap.add_argument("--source", type=Path)
    a = ap.parse_args(argv)
    source = a.source or locate()
    if source is None:
        print(f"找不到已安裝的 {PLUGIN}（{SKILL} 的種子範本）：什麼都沒寫", file=sys.stderr)
        return 2
    lines, problem = write(a.project, source)
    if problem:
        print(f"{problem}：什麼都沒寫", file=sys.stderr)
        return 2
    print("\n".join(lines))
    print(f"種子來自：{source}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
