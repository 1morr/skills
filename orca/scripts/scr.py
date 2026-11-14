# 用法：python3 scr.py <handle> [行數，預設 20]  —— 讀子 session 畫面：修 mojibake、壓縮分隔線
# 先印一行 status: <終端狀態>，再印畫面最後幾行非空的；orca 讀不到時印它回的 JSON、exit 1
# 環境變數 SCR_SCREEN_FILE：selftest.sh 用，不叫 orca，把這個檔的內容當畫面
import json, os, re, subprocess, sys
h = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
fake = os.environ.get('SCR_SCREEN_FILE')
if fake:
    d = {'ok': True, 'result': {'terminal': {'status': 'running', 'tail': open(fake, encoding='utf-8').read().splitlines()}}}
else:
    out = subprocess.run(['orca', 'terminal', 'read', '--terminal', h, '--json'], capture_output=True).stdout
    d = json.loads(out.decode('utf-8', errors='replace'))
if not d.get('ok'): print(json.dumps(d, ensure_ascii=False)[:1500]); sys.exit(1)
t = d['result']['terminal']
def fix(s):
    try: s = s.encode('utf-8', 'surrogateescape').decode('utf-8')
    except Exception: pass
    return re.sub(r'[─━]{4,}', '───', s).rstrip()
lines = [l for l in (fix(x) for x in t['tail']) if l.strip()]
sys.stdout.reconfigure(encoding='utf-8', newline='\n')  # Windows 預設寫 \r\n，bash 那邊每行會多一個 \r
print('status:', t['status'])
print('\n'.join(lines[-n:]))
