"""doc_reads.py 的測試：數得出誰讀了什麼，別的 repo、別的工具、日期之前的不算。

    python -m unittest discover -s skills/project-init/tests
"""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "doc_reads.py"
spec = importlib.util.spec_from_file_location("doc_reads", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DocReadsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="doc-reads-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.repo = self.root / "projects" / "Demo"
        self.work = self.root / "workspaces" / "Demo" / "t01"
        self.logs = self.root / "transcripts"
        for rel in ("AGENTS.md", "docs/progress.md", "docs/roadmap.md", "docs/archive/M0.md", ".scratch/m1/spec.md"):
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# x\n", encoding="utf-8")

    def log(self, name, cwd, *reads, date="2026-01-05", tool="Read", shell=()):
        """reads：(相對 cwd 的路徑, 有沒有帶 offset)。"""
        p = self.logs / name
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({"cwd": str(cwd), "timestamp": f"{date}T01:00:00Z", "type": "user", "message": {"content": "做票"}})]
        for rel, partial in reads:
            given = {"file_path": str(Path(cwd) / rel), **({"offset": 10, "limit": 5} if partial else {})}
            lines.append(json.dumps({"cwd": str(cwd), "timestamp": f"{date}T01:01:00Z", "type": "assistant",
                                     "message": {"content": [{"type": "tool_use", "name": tool, "input": given}]}}))
        for command in shell:
            lines.append(json.dumps({"cwd": str(cwd), "timestamp": f"{date}T01:02:00Z", "type": "assistant",
                                     "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]}}))
        p.write_text("\n".join(lines) + "\nnot json\n", encoding="utf-8")

    def agy_log(self, conv_id, cwd, *reads, date="2026-01-05", tool="read_file", shell=(), quoted=True):
        """寫一份 Antigravity 的 transcript.jsonl；reads：(相對 cwd 的路徑, 有沒有帶 StartLine/EndLine)。"""
        p = self.logs / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        encode = (lambda s: json.dumps(s)) if quoted else (lambda s: s)
        tool_calls = []
        for rel, partial in reads:
            given = {"Path": encode(str(Path(cwd) / rel))}
            if partial:
                given.update({"StartLine": "1", "EndLine": "40"})
            tool_calls.append({"name": tool, "args": given})
        for command in shell:
            tool_calls.append({"name": "run_command", "args": {"CommandLine": encode(command)}})
        lines = [
            json.dumps({"step_index": 0, "type": "USER_INPUT", "created_at": f"{date}T01:00:00Z", "content": "做票"}),
            json.dumps({"step_index": 1, "type": "PLANNER_RESPONSE", "created_at": f"{date}T01:01:00Z", "tool_calls": tool_calls}),
        ]
        p.write_text("\n".join(lines) + "\nnot json\n", encoding="utf-8")

    def scan(self, since="", harness="auto"):
        total, reads = m.scan(self.logs, self.repo, since, harness=harness)
        return total, {k: (len(v["sessions"]), v["full"], v["part"]) + ((v["shell"],) if v["shell"] else ()) for k, v in reads.items()}

    def test_counts_sessions_full_and_partial_reads(self):
        self.log("-main/a.jsonl", self.repo, ("docs/progress.md", False), ("docs/progress.md", True), ("src/main.rs", False))
        self.log("-main/b.jsonl", self.repo, ("docs/progress.md", False))
        self.log("-ws-t01/c.jsonl", self.work, ("docs/roadmap.md", True), (".scratch/m1/spec.md", False))
        self.assertEqual(self.scan(), (3, {"docs/progress.md": (2, 2, 1), "docs/roadmap.md": (1, 0, 1), ".scratch/m1/spec.md": (1, 1, 0)}))

    def test_subagent_reads_count_for_the_session_that_spawned_them(self):
        self.log("-main/a.jsonl", self.repo, ("docs/progress.md", False))
        self.log("-main/a/subagents/agent-1.jsonl", self.repo, ("docs/progress.md", False), ("docs/roadmap.md", False))
        self.assertEqual(self.scan(), (1, {"docs/progress.md": (1, 2, 0), "docs/roadmap.md": (1, 1, 0)}))

    def test_other_repos_other_tools_and_earlier_dates_are_left_out(self):
        other = self.root / "projects" / "DemoTwo"
        self.log("-other/a.jsonl", other, ("docs/progress.md", False))
        self.log("-main/grep.jsonl", self.repo, ("docs/progress.md", False), tool="Grep")
        self.log("-main/old.jsonl", self.repo, ("docs/roadmap.md", False), date="2025-12-01")
        self.assertEqual(self.scan(since="2026-01-01"), (1, {}))
        self.assertEqual(self.scan(), (2, {"docs/roadmap.md": (1, 1, 0)}))

    def test_shell_commands_that_name_a_doc_count_too(self):
        self.log("-main/a.jsonl", self.repo, shell=("sed -n 1,40p docs/progress.md | head", f"cat {self.repo}/docs/roadmap.md ./docs/progress.md",
                                                     "grep -rn TODO src/ docs/missing.md", "cargo test"))
        self.assertEqual(self.scan(), (1, {"docs/progress.md": (1, 0, 0, 2), "docs/roadmap.md": (1, 0, 0, 1)}))

    def test_report_lists_what_was_never_read(self):
        self.log("-main/a.jsonl", self.repo, ("docs/progress.md", False))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(m.main([str(self.repo), "--transcripts", str(self.logs)]), 0)
        text = out.getvalue()
        self.assertIn("| 1 | 100% | 1 | 0 | 0 | docs/progress.md |", text)
        never = text.split("一次都沒被碰過的文件")[1]
        self.assertNotIn("AGENTS.md", never)
        for rel in ("- docs/roadmap.md", "- .scratch/m1/spec.md"):
            self.assertIn(rel, never)
        self.assertNotIn("docs/archive/M0.md", never)
        self.assertNotIn("- docs/progress.md", never)

    def test_antigravity_counts_reads_partial_worktree_and_run_command(self):
        self.agy_log("conv-1", self.repo, ("docs/progress.md", False), ("docs/progress.md", True), ("src/main.rs", False),
                     shell=("sed -n 1,20p docs/roadmap.md", f"cat {self.repo}/docs/progress.md"))
        self.agy_log("conv-2", self.work, (".scratch/m1/spec.md", False), quoted=False)
        # transcript_full.jsonl 不重算
        full_copy = self.logs / "conv-1" / ".system_generated" / "logs" / "transcript_full.jsonl"
        full_copy.write_text((full_copy.parent / "transcript.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(self.scan(harness="antigravity"),
                         (2, {"docs/progress.md": (1, 1, 1, 1), "docs/roadmap.md": (1, 0, 0, 1), ".scratch/m1/spec.md": (1, 1, 0)}))

    def test_antigravity_leaves_out_other_repos_and_earlier_dates(self):
        other = self.root / "projects" / "DemoTwo"
        self.agy_log("conv-other", other, ("docs/progress.md", False), shell=("cat docs/roadmap.md",))
        self.agy_log("conv-old", self.repo, ("docs/roadmap.md", False), date="2025-12-01")
        self.agy_log("conv-edit", self.repo, ("src/main.rs", False), tool="edit_file", date="2026-01-05")
        self.assertEqual(self.scan(since="2026-01-01", harness="antigravity"), (1, {}))
        self.assertEqual(self.scan(harness="antigravity"), (2, {"docs/roadmap.md": (1, 1, 0)}))

    def test_harness_flag_filters_or_combines_claude_and_antigravity(self):
        self.log("-main/a.jsonl", self.repo, ("docs/progress.md", False))
        self.agy_log("conv-1", self.repo, ("docs/progress.md", False), ("docs/roadmap.md", True))
        self.assertEqual(self.scan(harness="claude"), (1, {"docs/progress.md": (1, 1, 0)}))
        self.assertEqual(self.scan(harness="antigravity"), (1, {"docs/progress.md": (1, 1, 0), "docs/roadmap.md": (1, 0, 1)}))
        self.assertEqual(self.scan(harness="auto"), (2, {"docs/progress.md": (2, 2, 0), "docs/roadmap.md": (1, 0, 1)}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(m.main([str(self.repo), "--transcripts", str(self.logs), "--harness", "antigravity"]), 0)
        self.assertIn("Demo：1 個 session", out.getvalue())
        self.assertIn("| 1 | 100% | 0 | 1 | 0 | docs/roadmap.md |", out.getvalue())


if __name__ == "__main__":
    unittest.main()
