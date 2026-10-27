# 用法：python3 state.py <子 session 的 jsonl 路徑>  —— 從 transcript 判斷子 session 的狀態，印一個字並以 exit code 回報
#   0 done     回合結束（最後是 turn_duration），而且沒有還沒回來的背景工作
#   1 busy     60 秒內有寫入、工具還在跑（含並行工具只回來一部分），或回合結束但在等自己的背景 shell / 子代理（印 waiting-bg）
#   2 asking   停在 AskUserQuestion，等協調者回答
#   3 unknown  其他（額度用完、API 錯誤、被中斷）：讀畫面判斷
# 以 transcript 為準而不是畫面：終端停在捲動模式時畫面不會更新，只看畫面會把還在跑的票當成做完
import json, os, re, sys, time

LAUNCH = re.compile(r'running in background with ID: (\w+)|agentId: (\w+)')
FINISH = re.compile(r'<task-id>(\w+)</task-id>.*?<status>(\w+)</status>', re.S)
STOPPED = re.compile(r'Successfully stopped task: (\w+)')  # 它自己用 TaskStop 停掉的，不會再有通知


def state(path, now=None):
    now = time.time() if now is None else now
    launched, finished, last = set(), set(), None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try: d = json.loads(line)
            except ValueError: continue
            if d.get('type') == 'user':
                for c in (d.get('message') or {}).get('content') or []:
                    if isinstance(c, dict) and c.get('type') == 'tool_result':
                        for m in LAUNCH.finditer(json.dumps(c.get('content'), ensure_ascii=False)):
                            launched.add(m.group(1) or m.group(2))
            for m in FINISH.finditer(line.replace('\\n', '\n')):
                if m.group(2) != 'running': finished.add(m.group(1))
            finished.update(STOPPED.findall(line))
            if d.get('type') in ('assistant', 'user') or d.get('subtype') == 'turn_duration':
                last = d
    m = (last or {}).get('message') or {}
    uses = [c for c in m.get('content') or [] if isinstance(c, dict) and c.get('type') == 'tool_use']
    if last and last.get('type') == 'assistant' and any(u.get('name') == 'AskUserQuestion' for u in uses):
        return 'asking'
    if now - os.path.getmtime(path) < 60:
        return 'busy'
    if last and last.get('subtype') == 'turn_duration':
        return 'waiting-bg' if launched - finished else 'done'
    if last and last.get('type') == 'assistant' and m.get('stop_reason') == 'tool_use':
        return 'busy'
    # 最後一行是 tool_result：回合還沒結束（並行的工具先回來一個、其他還在跑，或模型正要接著寫）
    if last and last.get('type') == 'user' and any(
            isinstance(c, dict) and c.get('type') == 'tool_result' for c in m.get('content') or []):
        return 'busy'
    return 'unknown'


if __name__ == '__main__':
    s = state(sys.argv[1])
    print(s)
    sys.exit({'done': 0, 'busy': 1, 'waiting-bg': 1, 'asking': 2}.get(s, 3))
