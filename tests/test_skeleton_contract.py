"""project-init 骨架範本、共用單一 Parser 與 1morr-skel 四個子命令（check / next / notes / dashboard）的整合契約測試。

    python3 -m unittest discover -s tests

用 project-init 範本搭一個 repo，走完里程碑全生命週期（開工、粗體 Blocked by 阻塞、等使用者、做票、notes --archive 自動封存、
無進行中時切換 `排在 <已結束> 之後` 佇列），每一站都驗證：
- `check` 通過且 `dashboard` 無 missing / unreadable / unlisted；
- `dashboard` 與 `next` 由同一顆 `skeleton_parser` 驅動，算出的下一張票與待決問題在所有狀態下 100% 一致。
"""

import contextlib
import importlib.util
import io
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/project-init/scripts"
TEMPLATES = ROOT / "skills/project-init/templates"
PLACEHOLDERS = {"PROJECT": "Demo", "ONE_LINE": "示範專案。", "DATE": "2026-01-02", "MAIN_BRANCH": "main"}

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


skeleton_parser = load("skeleton_parser")
check_docs = load("check_docs")
dashboard = load("dashboard")
ticket_notes = load("ticket_notes")
next_step = load("next_step")
skel = load("skel")


def fill(name: str) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: PLACEHOLDERS[m.group(1)], text)


def spec_doc() -> str:
    body = {
        "目標": "端到端跑通第一條路徑。",
        "範圍": "- 閘門\n- 第一條路徑",
        "共同規則": "無。",
        "驗收": "### Agent 驗\n\n- [ ] 全部檢查綠燈\n\n### 使用者試\n\n- 啟動後打一個字。",
        "票序": "01 → 02",
    }
    return "# spec\n\n" + "".join(f"## {title}\n\n{body[title]}\n\n" for title in check_docs.SPEC_SECTIONS)


def make_ticket(number: str, title: str, done: bool = False, decision: str = "", blocked: str = "None", bold_blocked: bool = False) -> str:
    text = fill("ticket.md").replace("# NN: <標題>", f"# {number}: {title}")
    blocked_line = f"**Blocked by:** {blocked}" if bold_blocked else f"Blocked by: {blocked}"
    text = text.replace("Blocked by: None", blocked_line)
    if not done:
        return text
    notes = f"\n{check_docs.SESSION_NOTE}2026-01-04 做完{title}\n" + (f"{check_docs.DECISION_NOTE}{decision}\n" if decision else "")
    return text.replace("Status: ready-for-agent", "Status: done").replace("- [ ]", "- [x]") + notes


class SkeletonContractTest(unittest.TestCase):
    def setUp(self):
        dashboard.clear_worktree_cache()
        self.repo = Path(tempfile.mkdtemp(prefix="contract-")).resolve()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        for name, rel in (
            ("instructions.md", "AGENTS.md"),
            ("design-brief.md", "docs/design-brief.md"),
            ("architecture.md", "ARCHITECTURE.md"),
            ("roadmap.md", "docs/roadmap.md"),
            ("progress.md", "docs/progress.md"),
            ("decisions.md", "docs/decisions.md"),
            ("development.md", "docs/development.md"),
        ):
            self.write(rel, fill(name))

    def write(self, rel: str, text: str):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def read(self, rel: str) -> str:
        return (self.repo / rel).read_text(encoding="utf-8")

    def sub(self, rel: str, old: str, new: str):
        text = self.read(rel)
        self.assertEqual(text.count(old), 1, f"{rel} 裡要剛好有一處 {old!r}")
        self.write(rel, text.replace(old, new))

    def append(self, rel: str, line: str):
        self.write(rel, self.read(rel).rstrip("\n") + "\n" + line + "\n")

    def roadmap_row(self, name: str) -> str:
        return next(l for l in self.read("docs/roadmap.md").split("\n") if l.startswith(f"| {name} "))

    def set_state(self, name: str, state: str):
        row = self.roadmap_row(name)
        self.sub("docs/roadmap.md", row, " | ".join(row.split(" | ")[:-1]) + f" | {state} |")

    def fill_gates(self):
        self.write("docs/development.md", self.read("docs/development.md").replace("| 待定 |", "| `make check` |"))

    def check(self) -> dict:
        """驗證 check_docs 綠燈，且 dashboard 與 next_step 100% 一致。"""
        self.assertEqual(check_docs.run(self.repo), [])
        data = dashboard.collect(self.repo, worktree_ttl=0)
        self.assertEqual((data["missing"], data["unreadable"], data["unlisted"]), ([], [], []))
        self.assertNotIn(dashboard.UNMARKED, [d["decider"] for d in data["decisions"]])
        step = next_step.report(self.repo)
        self.assertEqual(len(step["waiting"]), len(data["waiting_all"]))
        for line, asked in zip(step["waiting"], data["waiting_all"]):
            self.assertIn(asked["text"], line)
        if data["next_ticket"]:
            self.assertEqual(step["command"], data["next_ticket"]["command"])
        elif not data["waiting"]:
            self.assertIn(step["command"] or "沒有指令", data["next"] or "沒有指令")
        return data

    def test_bold_blocked_by_and_queued_milestone_stay_in_sync(self):
        """回歸測試：① 粗體 `**Blocked by:** 01` 不會被當成未阻塞票推薦；② 無 `進行中` 時兩邊一致切換到 `排在 <已結束> 之後` 佇列。"""
        self.set_state("M0 骨架", "進行中，已拆 3 張票")
        self.write(".scratch/m0/spec.md", spec_doc())
        # 00 號（排序在 01 前面！）但寫了粗體 **Blocked by:** 01 -> 絕不能被推薦為第一張票！
        self.write(".scratch/m0/issues/00-dependent.md", make_ticket("00", "依賴 01 的下游票", blocked="01", bold_blocked=True))
        self.write(".scratch/m0/issues/01-gates.md", make_ticket("01", "閘門"))
        self.write(".scratch/m0/issues/02-m0-acceptance.md", make_ticket("02", "M0 驗收", blocked="00, 01", bold_blocked=True))

        data = self.check()
        self.assertEqual(data["next_ticket"]["file"], "01-gates.md")
        self.assertEqual(next_step.report(self.repo)["command"], "/implement .scratch/m0/issues/01-gates.md")

        # 01 完成後，粗體 **Blocked by:** 01 的 00 號票自動解鎖，而 02 仍被 00 擋住
        self.fill_gates()
        self.write(".scratch/m0/issues/01-gates.md", make_ticket("01", "閘門", done=True, decision="用 POSIX sh(Agent 定)"))
        data = self.check()
        self.assertEqual(data["next_ticket"]["file"], "00-dependent.md")

        # M0 全部完成並封存，此時沒有任何「進行中」里程碑，但 docs-diet 排在已驗收的 M0 之後 -> next 與 dashboard 一致切到 docs-diet！
        self.write(".scratch/m0/issues/00-dependent.md", make_ticket("00", "依賴 01 的下游票", done=True))
        self.write(".scratch/m0/issues/02-m0-acceptance.md", make_ticket("02", "M0 驗收", done=True))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skel.main(["notes", "--archive", "m0", str(self.repo), "--user-trial", "- 啟動後打一個字：通過。"]), 0)
        self.append("docs/progress.md", "| 2026-01-05 | M1 準備 | M0 已驗收封存 | 新 session 下 `/to-tickets docs/roadmap.md 拆 M1 的票` |")
        self.set_state("M0 骨架", "已驗收，封存在 [docs/archive/M0.md](archive/M0.md)")
        self.sub(
            "docs/roadmap.md",
            self.roadmap_row("M0 骨架"),
            self.roadmap_row("M0 骨架") + "\n| docs-diet 文件瘦身 | 文件變短 | — | 未開工，排在 M0 之後 |",
        )
        self.write(".scratch/docs-diet/spec.md", spec_doc())
        self.write(".scratch/docs-diet/issues/01-trim.md", make_ticket("01", "瘦身"))

        data = self.check()
        self.assertEqual(data["next_ticket"]["command"], "/implement .scratch/docs-diet/issues/01-trim.md")
        self.assertEqual(next_step.report(self.repo)["command"], "/implement .scratch/docs-diet/issues/01-trim.md")

    def test_every_station_of_a_milestone_and_archive_cli(self):
        # 1. 剛搭好
        data = self.check()
        self.assertEqual([(m["name"], m["state"], len(m["tickets"])) for m in data["milestones"]], [("M0 骨架", "todo", 0)])
        self.assertEqual((len(data["decisions"]), len(data["sessions"])), (1, 1))
        self.assertIn("/grill-with-docs", data["next"])

        # 2. M0 開工
        self.set_state("M0 骨架", "進行中，已拆 3 張票")
        self.write(".scratch/m0/spec.md", spec_doc())
        self.write(".scratch/m0/issues/01-gates.md", make_ticket("01", "閘門"))
        self.write(".scratch/m0/issues/02-dropped.md", make_ticket("02", "不做的").replace("Status: ready-for-agent", "Status: wontfix"))
        self.write(".scratch/m0/issues/03-m0-acceptance.md", make_ticket("03", "M0 驗收"))
        self.append("docs/progress.md", "| 2026-01-03 | M0 開工 | 拆了 3 張票 | 新 session 下 `/implement .scratch/m0/issues/01-gates.md` |")
        m0 = self.check()["milestones"][0]
        self.assertEqual((m0["state"], m0["detail"], m0["scope"]), ("active", "端到端跑通第一條路徑。", ["閘門", "第一條路徑"]))

        # 3. 票停在等使用者，回答後關閉問題
        self.append(".scratch/m0/issues/01-gates.md", f"{check_docs.WAITING}埠要寫死還是讓系統挑？")
        data = self.check()
        self.assertEqual(([a["text"] for a in data["waiting_all"]], data["next_ticket"]["file"]), (["埠要寫死還是讓系統挑？"], "03-m0-acceptance.md"))
        self.append(".scratch/m0/issues/01-gates.md", f"{check_docs.DECISION_NOTE}讓系統挑（使用者定）")
        data = self.check()
        self.assertEqual((data["waiting_all"], data["next_ticket"]["file"]), ([], "01-gates.md"))

        # 4. 完成票並用 skel notes --archive 自動寫出封存檔
        self.fill_gates()
        self.write(".scratch/m0/issues/01-gates.md", make_ticket("01", "閘門", done=True, decision="用 X 不用 Y（Agent 定）"))
        self.write(".scratch/m0/issues/03-m0-acceptance.md", make_ticket("03", "M0 驗收", done=True))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skel.main(["notes", "--archive", "m0", str(self.repo), "--user-trial", "- 啟動後打一個字：可以。"]), 0)
        self.assertTrue((self.repo / "docs/archive/M0.md").is_file())
        self.append("docs/progress.md", "| 2026-01-05 | M1 準備 | M0 已驗收並封存 | 新 session 下 `/to-tickets docs/roadmap.md 拆 M1 的票` |")
        self.append("docs/decisions.md", "- 2026-01-05 M1（使用者定）：下一個先做核心。")
        self.set_state("M0 骨架", "已驗收，封存在 [docs/archive/M0.md](archive/M0.md)")
        self.sub("docs/roadmap.md", self.roadmap_row("M0 骨架"), self.roadmap_row("M0 骨架") + "\n| M1 核心 | 第一個功能 | brief §4 | 進行中 |")

        data = self.check()
        self.assertEqual([(m["name"], m["state"]) for m in data["milestones"]], [("M0 骨架", "done"), ("M1 核心", "active")])
        self.assertEqual(
            [(d["milestone"], d["label"], d["decider"], d["archived"]) for d in data["decisions"]],
            [("M1", "M1", "使用者定", False), ("M0", "M0 票 01", "Agent 定", True), ("M0", "框架", "Agent 定", True)],
        )
        self.assertEqual([(a["milestone"], [r["ticket"] for r in a["rows"]]) for a in data["archived_sessions"]],
                         [("M0", ["M0 03", "M0 01", "M0 開工", "框架"])])

    def test_changelog_entries_accept_halfwidth_and_fullwidth_pipes(self):
        self.write("CHANGELOG.md", fill("changelog.md"))
        self.fill_gates()
        self.set_state("M0 骨架", "進行中，已拆 2 張票")
        self.write(".scratch/m0/spec.md", spec_doc())
        self.write(
            ".scratch/m0/issues/01-gates.md",
            make_ticket("01", "閘門", done=True) + "變更：Added | 閘門 | 半形分隔符也通。\n變更：Fixed｜閘門｜全形分隔符也通。\n",
        )
        self.write(".scratch/m0/issues/02-m0-acceptance.md", make_ticket("02", "M0 驗收", done=True) + "變更：無\n")
        entries = self.check()["changelog"][0]["entries"]
        self.assertEqual(
            [(e["kind"], e["feature"], e["text"], e["pending"]) for e in entries],
            [("Added", "閘門", "半形分隔符也通。", "M0 01"), ("Fixed", "閘門", "全形分隔符也通。", "M0 01")],
        )
        self.append("CHANGELOG.md", "\n" + "\n".join(ticket_notes.changelog(self.repo, "m0")))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skel.main(["notes", "--archive", "m0", str(self.repo), "--user-trial", "無。"]), 0)
        self.append("docs/progress.md", "| 2026-01-05 | M1 準備 | M0 封存 | 新 session 下 `/to-tickets docs/roadmap.md 拆 M1 的票` |")
        self.set_state("M0 骨架", "已驗收，封存在 [docs/archive/M0.md](archive/M0.md)")
        entries = self.check()["changelog"][0]["entries"]
        self.assertEqual([(e["kind"], e["feature"], e["pending"]) for e in entries], [("Added", "閘門", ""), ("Fixed", "閘門", "")])


if __name__ == "__main__":
    unittest.main()
