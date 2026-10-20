# 用法：python scr.py <handle> [行數]  —— 讀子 session 畫面：修 mojibake、壓縮分隔線、只印非空行
import json, re, subprocess, sys
h = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
out = subprocess.run(['orca', 'terminal', 'read', '--terminal', h, '--json'], capture_output=True).stdout
d = json.loads(out.decode('utf-8', errors='replace'))
if not d.get('ok'): print(json.dumps(d, ensure_ascii=False)[:1500]); sys.exit(1)
t = d['result']['terminal']
def fix(s):
    try: s = s.encode('utf-8', 'surrogateescape').decode('utf-8')
    except Exception: pass
    return re.sub(r'[─━]{4,}', '───', s).rstrip()
lines = [l for l in (fix(x) for x in t['tail']) if l.strip()]
sys.stdout.reconfigure(encoding='utf-8')
print('status:', t['status'])
print('\n'.join(lines[-n:]))
