# 用法：python3 last.py <子 session 的 jsonl 路徑>  —— 印出它最後一則回覆的全文（計畫、做完的回報、文字提問）
# 最後一則回覆 = transcript 裡最後一筆 user 行（含 tool_result）之後，assistant 寫的所有文字，段落之間空一行。
# 那之後沒有文字（還在跑工具、剛收到通知還沒回話）就什麼都不印、exit 1。waitbg.sh 在 state=done / done-bg 時會呼叫它：
# 畫面只有最後幾十行，長的回覆會被截掉，捲動模式下還可能是舊的。
import json, sys


def last_reply(path):
    parts = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try: d = json.loads(line)
            except ValueError: continue
            if not isinstance(d, dict) or d.get('isSidechain'): continue
            if d.get('type') == 'user':
                parts = []
            elif d.get('type') == 'assistant':
                for c in (d.get('message') or {}).get('content') or []:
                    if isinstance(c, dict) and c.get('type') == 'text' and (c.get('text') or '').strip():
                        parts.append(c['text'].strip())
    return '\n\n'.join(parts)


if __name__ == '__main__':
    text = last_reply(sys.argv[1])
    if not text: sys.exit(1)
    sys.stdout.reconfigure(encoding='utf-8', newline='\n')  # Windows 預設寫 \r\n，bash 那邊每行會多一個 \r
    print(text)
