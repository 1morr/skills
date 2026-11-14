# 用法：python3 ask.py <子 session 的 jsonl 路徑>  —— 印出它停著的那次 AskUserQuestion 的全部題目與選項
# 每題一行「[第幾題/共幾題] <分頁標題>（單選|複選）：<題目>」，下面每個選項一行「  <編號>. <label> —— <description>」；
# 編號和畫面上的一樣（畫面在最後多出的 Type something. / Chat about this 不在 transcript 裡）。
# transcript 最後一則不是 AskUserQuestion 就什麼都不印、exit 1。waitbg.sh 在 state=asking 時會呼叫它。
import json, sys


def pending(path):
    last = None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try: d = json.loads(line)
            except ValueError: continue
            if d.get('type') in ('assistant', 'user'):
                last = d
    if not last or last.get('type') != 'assistant':
        return []
    for c in (last.get('message') or {}).get('content') or []:
        if isinstance(c, dict) and c.get('type') == 'tool_use' and c.get('name') == 'AskUserQuestion':
            return (c.get('input') or {}).get('questions') or []
    return []


if __name__ == '__main__':
    qs = pending(sys.argv[1])
    if not qs: sys.exit(1)
    sys.stdout.reconfigure(encoding='utf-8', newline='\n')  # Windows 預設寫 \r\n，bash 那邊會多一個 \r
    for i, q in enumerate(qs, 1):
        kind = '複選' if q.get('multiSelect') else '單選'
        print(f"[{i}/{len(qs)}] {q.get('header', '')}（{kind}）：{q.get('question', '')}")
        for n, o in enumerate(q.get('options') or [], 1):
            desc = o.get('description')
            print(f"  {n}. {o.get('label', '')}" + (f" —— {desc}" if desc else ''))
