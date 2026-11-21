"""從 repo 現在的檔案算出下一步：等使用者決定的事、現在要下的指令、後面還排著什麼（共用 skeleton_parser）。

    python3 next_step.py [repo 根目錄，預設目前目錄]

只讀不寫，永遠 exit 0。只用標準函式庫。
"""

import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import skeleton_parser as sp  # noqa: E402


def _path_of(work: dict, t: dict) -> str:
    return f"{sp.SCRATCH_DIR}/{work['dir']}/issues/{t['file']}"


def later(listed: list, now, ready: list) -> list:
    out = []
    if now and sp.open_tickets(now):
        rest = len(sp.open_tickets(now)) - (1 if ready else 0)
        last = now["tickets"][-1]
        accept = bool(sp.MILESTONE_DIR_RE.match(now["dir"])) and last["file"].endswith(sp.ACCEPTANCE_SUFFIXES) and not last["closed"]
        if rest > 0:
            out.append(f"{now['label']} 還有 {rest} 張票" + ("，最後一張是驗收票（含試用與決策追認）" if accept else ""))
        elif accept:
            out.append(f"這張是 {now['label']} 的驗收票（含試用與決策追認）")
    for w in listed:
        if w is now or w["state"] in sp.CLOSED_STATES:
            continue
        rem = sp.open_tickets(w)
        if rem:
            out.append(
                f"{w['name']}：{len(rem)} 張票，"
                + (f"排在 {w['after_name']} 之後" if w["after"] else f"{sp.ROADMAP_REL} 沒寫它排在誰之後")
            )
        elif not w["tickets"]:
            out.append(f"{w['name']}：還沒拆票")
    return out


def report(root: Path) -> dict:
    listed, _ = sp.parse_milestones(root)
    step, last_row, _ = sp.last_progress_step(root)
    date = last_row.get("日期", "") if last_row else ""
    held = step.startswith(sp.WAITING)

    waiting = [
        f"{w['label']} 票 {t['number']}：{q}（{_path_of(w, t)}）"
        for w in listed if w["state"] not in sp.CLOSED_STATES
        for t in w["tickets"] for q in t["waiting_raw"]
    ]
    if held:
        waiting.append(f"{step[len(sp.WAITING):].strip()}（{sp.PROGRESS_REL} 最後一列，{date}）")

    now = sp.current_milestone(listed)
    ready = sp.doable_tickets(now) if now else []
    command, why = "", ""
    if ready:
        t = ready[0]
        command = f"/implement {_path_of(now, t)}"
        why = f"{now['label']} 票 {t['number']} {t['bare_title']}。開一個新的 session 貼上這條指令。"
        if now["state"] != "active":
            why += f"\n先把 {sp.ROADMAP_REL} 里程碑表裡 {now['label']} 那一列的狀態改成「{sp.ACTIVE_WORD}」。"
        if len(ready) > 1:
            why += f"\n同時做得了的有 {len(ready)} 張，要整批跑：/1morr:ticket-coordinator {sp.SCRATCH_DIR}/{now['dir']}/issues"
        if held:
            why = f"先回答上面 {sp.PROGRESS_REL} 那一題；答完之後才是這條指令。\n" + why
    elif now and sp.open_tickets(now):
        stuck = sp.open_tickets(now)
        asked = [t for t in stuck if t["waiting"]]
        why = (
            f"{now['label']} 剩下的票都在等你回答上面的題。"
            if len(asked) == len(stuck)
            else f"{now['label']} 還有 {len(stuck)} 張票沒做完，但每一張不是在等你回答，就是被還沒做完的票擋著："
            + "、".join(f"票 {t['number']}（擋它的：{'、'.join(t['blocked']) or '無'}）" for t in stuck if not t["waiting"])
        )
    elif held:
        why = "先回答上面那一題；開一個新的 session 回答。"
    elif step:
        found = sp.COMMAND_RE.search(step)
        command = found.group(1) if found else ""
        why = f"{sp.PROGRESS_REL} 最後一列（{date}）寫的下一步" + ("。開一個新的 session 貼上這條指令。" if found else f"：{step}")
    else:
        why = f"{sp.PROGRESS_REL} 還沒有 session 紀錄，也沒有可以做的票。"

    return {"waiting": waiting, "command": command, "why": why, "later": later(listed, now, ready)}


def render(found: dict) -> str:
    out = []
    if found["waiting"]:
        out += [f"等你決定（{len(found['waiting'])}）", *(f"  - {w}" for w in found["waiting"])]
    out.append("現在")
    if found["command"]:
        out.append(f"  {found['command']}")
    out += [f"  {line}" for line in found["why"].split("\n")]
    if found["later"]:
        out += ["之後", *(f"  - {l}" for l in found["later"])]
    return "\n".join(out)


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    print(render(report(Path(argv[0]) if argv else Path.cwd())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
