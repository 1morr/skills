# 用法：python busy.py <子 session 的 jsonl 路徑>  —— exit 0 表示子 session 還在忙
# 忙：transcript 60 秒內有寫入，或最後一則是未完成的 tool_use（AskUserQuestion 除外：那是在等協調者回答）
import json, os, sys, time
p = sys.argv[1]
if time.time() - os.path.getmtime(p) < 60: sys.exit(0)
last = None
with open(p, 'rb') as f:
    f.seek(max(0, os.path.getsize(p) - 400000))
    for line in f.read().splitlines():
        try: d = json.loads(line)
        except Exception: continue
        if d.get('type') in ('assistant', 'user'): last = d
m = (last or {}).get('message', {})
names = [c.get('name') for c in m.get('content', []) if isinstance(c, dict) and c.get('type') == 'tool_use']
sys.exit(0 if last and last['type'] == 'assistant' and m.get('stop_reason') == 'tool_use' and 'AskUserQuestion' not in names else 1)
