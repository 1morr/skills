"""project-init 寫出來的骨架，dashboard 全部讀得到。

    python -m unittest discover -s tests

用 project-init 的範本搭一個 repo，照範本寫的規則走一輪里程碑（開工、做票、驗收、封存、下一個開工），
每一站都要：通得過 check_docs.py，而且 dashboard 把每個里程碑、每張票、每條決定、每列 session 紀錄讀出來，
「讀不到」的清單是空的。兩邊任一邊改了格式而另一邊沒跟上，這裡會紅。
"""

import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "skills/project-init/templates"
PLACEHOLDERS = {"PROJECT": "Demo", "ONE_LINE": "示範專案。", "DATE": "2026-01-02", "MAIN_BRANCH": "main"}


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check_docs = load("check_docs", "skills/project-init/scripts/check_docs.py")
dashboard = load("dashboard", "skills/dashboard/scripts/dashboard.py")


def fill(name: str) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: PLACEHOLDERS[m.group(1)], text)


def spec() -> str:
    body = {"目標": "端到端跑通第一條路徑。", "範圍": "- 閘門\n- 第一條路徑", "共同規則": "無。",
            "驗收": "### Agent 驗\n\n- [ ] 全部檢查綠燈\n\n### 使用者試\n\n- 啟動後打一個字。", "票序": "01 → 02"}
    return "# spec\n\n" + "".join(f"## {title}\n\n{body[title]}\n\n" for title in check_docs.SPEC_SECTIONS)


def ticket(number: str, title: str, done: bool = False, decision: str = "") -> str:
    text = fill("ticket.md").replace("# NN: <標題>", f"# {number}: {title}")
    if not done:
        return text
    notes = f"\n{check_docs.SESSION_NOTE}做完{title}\n" + (f"{check_docs.DECISION_NOTE}{decision}\n" if decision else "")
    return text.replace("Status: ready-for-agent", "Status: done").replace("- [ ]", "- [x]") + notes


class SkeletonContractTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="contract-")).resolve()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        for name, rel in (("instructions.md", "AGENTS.md"), ("design-brief.md", "docs/design-brief.md"),
                          ("architecture.md", "ARCHITECTURE.md"), ("roadmap.md", "docs/roadmap.md"),
                          ("progress.md", "docs/progress.md"), ("decisions.md", "docs/decisions.md"),
                          ("development.md", "docs/development.md")):
            self.write(rel, fill(name))

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def read(self, rel):
        return (self.repo / rel).read_text(encoding="utf-8")

    def sub(self, rel, old, new):
        text = self.read(rel)
        self.assertEqual(text.count(old), 1, f"{rel} 裡要剛好有一處 {old!r}")
        self.write(rel, text.replace(old, new))

    def append(self, rel, line):
        self.write(rel, self.read(rel).rstrip("\n") + "\n" + line + "\n")

    def roadmap_row(self, name):
        return next(l for l in self.read("docs/roadmap.md").split("\n") if l.startswith(f"| {name} "))

    def set_state(self, name, state):
        row = self.roadmap_row(name)
        self.sub("docs/roadmap.md", row, " | ".join(row.split(" | ")[:-1]) + f" | {state} |")

    def check(self):
        """兩邊都過，回傳 dashboard 讀到的資料。"""
        self.assertEqual(check_docs.run(self.repo), [])
        data = dashboard.collect(self.repo)
        self.assertEqual((data["missing"], data["unreadable"], data["unlisted"]), ([], [], []))
        self.assertNotIn(dashboard.UNMARKED, [d["decider"] for d in data["decisions"]])
        return data

    def test_every_station_of_a_milestone_is_read(self):
        # 剛搭好
        data = self.check()
        self.assertEqual([(m["name"], m["state"], len(m["tickets"])) for m in data["milestones"]], [("M0 骨架", "todo", 0)])
        self.assertEqual((len(data["decisions"]), len(data["sessions"])), (1, 1))
        self.assertIn("/grill-with-docs", data["next"])

        # M0 開工：spec、票、狀態
        self.set_state("M0 骨架", "進行中，已拆 3 張票")
        self.write(".scratch/m0/spec.md", spec())
        self.write(".scratch/m0/issues/01-gates.md", ticket("01", "閘門"))
        self.write(".scratch/m0/issues/02-dropped.md", ticket("02", "不做的").replace("Status: ready-for-agent", "Status: wontfix"))
        self.write(".scratch/m0/issues/03-m0-acceptance.md", ticket("03", "M0 驗收"))
        self.append("docs/progress.md", "| 2026-01-03 | M0 開工 | 拆了 3 張票 | 新 session 下 `/implement .scratch/m0/issues/01-gates.md` |")
        m0 = self.check()["milestones"][0]
        self.assertEqual((m0["state"], m0["detail"], m0["scope"]), ("active", "端到端跑通第一條路徑。", ["閘門", "第一條路徑"]))
        self.assertEqual([(t["title"], t["done"], t["dropped"], t["boxes"]) for t in m0["tickets"]],
                         [("01: 閘門", False, False, 2), ("02: 不做的", False, True, 2), ("03: M0 驗收", False, False, 2)])

        # 做完一張票，合併的人抄兩種行
        self.write(".scratch/m0/issues/01-gates.md", ticket("01", "閘門", done=True, decision="用 X 不用 Y（Agent 定）"))
        self.append("docs/progress.md", "| 2026-01-04 | M0 01 | 做完閘門 | 新 session 下 `/implement .scratch/m0/issues/03-m0-acceptance.md` |")
        self.append("docs/decisions.md", "- 2026-01-04 M0 票 01（Agent 定）：用 X 不用 Y。見票 01")
        data = self.check()
        self.assertEqual([(t["done"], t["checked"]) for t in data["milestones"][0]["tickets"]], [(True, 2), (False, 0), (False, 0)])
        self.assertEqual([(d["milestone"], d["decider"], d["archived"]) for d in data["decisions"]],
                         [("M0", "Agent 定", False), ("框架", "Agent 定", False)])
        self.assertEqual(len(data["sessions"]), 3)

        # 驗收票做完、封存，下一個里程碑開工
        self.write(".scratch/m0/issues/03-m0-acceptance.md", ticket("03", "M0 驗收", done=True))
        table = self.read("docs/progress.md").split(f"## {check_docs.SESSIONS}\n", 1)[1].strip()
        log = self.read("docs/decisions.md").split(f"## {check_docs.LOG}\n", 1)[1].strip()
        self.write("docs/archive/M0.md", f"# M0 封存\n\n## {check_docs.SESSIONS}\n\n{table}\n\n## {check_docs.ARCHIVED}\n\n{log}\n\n## {check_docs.USER_TRIAL}\n\n- 啟動後打一個字：可以。\n")
        head = "\n".join(table.split("\n")[:2])
        self.write("docs/progress.md", self.read("docs/progress.md").replace(table, head + "\n| 2026-01-05 | M1 準備 | M0 已驗收並封存 | 新 session 下 `/1morr:checkpoint M0` |"))
        self.write("docs/decisions.md", self.read("docs/decisions.md").replace(log, "- 2026-01-05 M1（使用者定）：下一個先做核心。"))
        self.set_state("M0 骨架", "已驗收，封存在 [docs/archive/M0.md](archive/M0.md)")
        self.sub("docs/roadmap.md", self.roadmap_row("M0 骨架"), self.roadmap_row("M0 骨架") + "\n| M1 核心 | 第一個功能 | brief §4 | 進行中 |")
        data = self.check()
        self.assertEqual([(m["name"], m["state"]) for m in data["milestones"]], [("M0 骨架", "done"), ("M1 核心", "active")])
        self.assertEqual([(d["milestone"], d["label"], d["decider"], d["archived"]) for d in data["decisions"]],
                         [("M1", "M1", "使用者定", False), ("M0", "M0 票 01", "Agent 定", True), ("M0", "框架", "Agent 定", True)])
        self.assertEqual((len(data["sessions"]), data["next"]), (1, "新 session 下 `/1morr:checkpoint M0`"))
        self.assertEqual([(a["milestone"], [r["ticket"] for r in a["rows"]]) for a in data["archived_sessions"]], [("M0", ["M0 01", "M0 開工", "框架"])])
        self.assertEqual((data["waiting"], data["unseen"]), ("", []))

        # 驗收票停在等使用者試
        self.append("docs/progress.md", "| 2026-01-06 | M1 02 | Agent 驗做完 | 等使用者：試用 M1 |")
        self.assertEqual(self.check()["waiting"], "試用 M1")

        # 不是里程碑的工作也在表裡佔一列
        self.write(".scratch/docs-diet/spec.md", spec())
        self.write(".scratch/docs-diet/issues/01-trim.md", ticket("01", "瘦身"))
        self.assertTrue(any("docs-diet" in v for v in check_docs.run(self.repo)))
        self.assertEqual([u["name"] for u in dashboard.collect(self.repo)["unlisted"]], ["docs-diet"])
        self.sub("docs/roadmap.md", self.roadmap_row("M1 核心"), self.roadmap_row("M1 核心") + "\n| docs-diet 文件瘦身 | 文件變短 | — | 未開工 |")
        self.assertEqual([(m["dir"], len(m["tickets"])) for m in self.check()["milestones"]][-1], ("docs-diet", 1))


if __name__ == "__main__":
    unittest.main()
