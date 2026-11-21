"""tools/doc_reads.py 的測試：分開統計 Read 工具與真實 shell 讀取命令，排除 git add/commit/diff/mv/rm 灌水。

    python3 -m unittest discover -s tools/tests -v
"""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "doc_reads.py"
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

    def scan_summary(self, since="", harness="auto"):
        total, reads = m.scan(self.logs, self.repo, since, harness=harness)
        return total, {
            k: (len(v["read_sessions"]), v["full"], v["part"], len(v["shell_sessions"]), v["shell"])
            for k, v in reads.items()
        }

    def test_counts_read_tool_and_shell_separately(self):
        self.log("-main/a.jsonl", self.repo, ("docs/progress.md", False), ("docs/progress.md", True), ("src/main.rs", False))
        self.log("-main/b.jsonl", self.repo, shell=("cat docs/progress.md", "head -n 20 docs/roadmap.md"))
        self.log("-ws-t01/c.jsonl", self.work, ("docs/roadmap.md", True), (".scratch/m1/spec.md", False))
        self.assertEqual(self.scan_summary(), (3, {
            "docs/progress.md": (1, 1, 1, 1, 1),
            "docs/roadmap.md": (1, 0, 1, 1, 1),
            ".scratch/m1/spec.md": (1, 1, 0, 0, 0),
        }))

    def test_non_read_shell_commands_are_excluded(self):
        self.log("-main/a.jsonl", self.repo, shell=(
            "git add docs/progress.md && git commit -m 'update docs/progress.md'",
            "git diff HEAD -- docs/roadmap.md",
            "git status docs/progress.md",
            "mv docs/progress.md docs/roadmap.md",
            "rm -f docs/progress.md",
            "sed -i '' 's/a/b/' docs/progress.md",
            "cat .scratch/m1/spec.md > docs/roadmap.md",
        ))
        # 只有最後一條 `cat .scratch/m1/spec.md` 的輸入檔算讀取；重導向目標 `> docs/roadmap.md` 與前面所有 git/mv/rm/sed -i 均不算！
        self.assertEqual(self.scan_summary(), (1, {
            ".scratch/m1/spec.md": (0, 0, 0, 1, 1),
        }))

    def test_real_shell_read_commands_count(self):
        self.log("-main/a.jsonl", self.repo, shell=(
            "sed -n 1,40p docs/progress.md | head",
            f"cat {self.repo}/docs/roadmap.md ./docs/progress.md",
            "rg '目標' .scratch/m1/spec.md",
            "git grep TODO docs/roadmap.md",
            "grep -rn TODO src/ docs/missing.md",
            "cargo test",
        ))
        self.assertEqual(self.scan_summary(), (1, {
            "docs/progress.md": (0, 0, 0, 1, 2),
            "docs/roadmap.md": (0, 0, 0, 1, 2),
            ".scratch/m1/spec.md": (0, 0, 0, 1, 1),
        }))

    def test_subagent_reads_count_for_the_session_that_spawned_them(self):
        self.log("-main/a.jsonl", self.repo, ("docs/progress.md", False))
        self.log("-main/a/subagents/agent-1.jsonl", self.repo, ("docs/progress.md", False), ("docs/roadmap.md", False))
        self.assertEqual(self.scan_summary(), (1, {
            "docs/progress.md": (1, 2, 0, 0, 0),
            "docs/roadmap.md": (1, 1, 0, 0, 0),
        }))

    def test_other_repos_other_tools_and_earlier_dates_are_left_out(self):
        other = self.root / "projects" / "DemoTwo"
        self.log("-other/a.jsonl", other, ("docs/progress.md", False))
        self.log("-main/grep.jsonl", self.repo, ("docs/progress.md", False), tool="Grep")
        self.log("-main/old.jsonl", self.repo, ("docs/roadmap.md", False), date="2025-12-01")
        self.assertEqual(self.scan_summary(since="2026-01-01"), (1, {}))
        self.assertEqual(self.scan_summary(), (2, {"docs/roadmap.md": (1, 1, 0, 0, 0)}))

    def test_report_lists_separate_columns_and_never_read_files(self):
        self.log("-main/a.jsonl", self.repo, ("docs/progress.md", False), shell=("git add docs/roadmap.md",))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(m.main([str(self.repo), "--transcripts", str(self.logs)]), 0)
        text = out.getvalue()
        self.assertIn("| Read session | 比例 | 整份 | 局部 | shell session | shell | 文件 |", text)
        self.assertIn("| 1 | 100% | 1 | 0 | 0 | 0 | docs/progress.md |", text)
        never = text.split("一次都沒被讀過的文件")[1]
        self.assertNotIn("AGENTS.md", never)
        # docs/roadmap.md 只有被 git add 碰過，沒被讀過，所以必須出現在未讀清單！
        for rel in ("- docs/roadmap.md", "- .scratch/m1/spec.md"):
            self.assertIn(rel, never)
        self.assertNotIn("docs/archive/M0.md", never)
        self.assertNotIn("- docs/progress.md", never)

    def test_antigravity_and_harness_flag(self):
        self.log("-main/a.jsonl", self.repo, ("docs/progress.md", False))
        self.agy_log("conv-1", self.repo, ("docs/progress.md", False), ("docs/roadmap.md", True),
                     shell=("sed -n 1,20p .scratch/m1/spec.md", "git commit -m 'docs/roadmap.md'"))
        full_copy = self.logs / "conv-1" / ".system_generated" / "logs" / "transcript_full.jsonl"
        full_copy.write_text((full_copy.parent / "transcript.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(self.scan_summary(harness="claude"), (1, {"docs/progress.md": (1, 1, 0, 0, 0)}))
        self.assertEqual(self.scan_summary(harness="antigravity"), (1, {
            "docs/progress.md": (1, 1, 0, 0, 0),
            "docs/roadmap.md": (1, 0, 1, 0, 0),
            ".scratch/m1/spec.md": (0, 0, 0, 1, 1),
        }))
        self.assertEqual(self.scan_summary(harness="auto"), (2, {
            "docs/progress.md": (2, 2, 0, 0, 0),
            "docs/roadmap.md": (1, 0, 1, 0, 0),
            ".scratch/m1/spec.md": (0, 0, 0, 1, 1),
        }))


if __name__ == "__main__":
    unittest.main()
