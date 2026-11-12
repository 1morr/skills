# 用法：python3 headsup.py [--summary] <子 session 的 jsonl 路徑>
# 從 Claude Code 內建 mod「You should know」的狀態檔讀這個 session 目前掛著的 Heads up，不用讀畫面、不用按 1 展開。
#   exit 0  有一則掛著。--summary 只印摘要一行；否則印 summary= / tag= / shown= / kind=，再一行 text:，後面是全文
#           （就是按 1 Learn more 看到的內容；mod 沒存全文時 text: 後面是空的，要照 TUI.md 展開讀畫面）
#   exit 1  狀態檔讀得到，這個 session 沒有掛著的 Heads up（包括按 0 收起後那約 20 秒的「Dismissed.」）
#   exit 2  讀不到或格式不認得（mod 沒開、CLI 改了格式）：呼叫端退回讀畫面
# 狀態檔是 mod 的內部格式（CLI 2.1.322 讀程式碼得出），沒有公開文件。只讀不寫：檔案歸 Claude Code 管，它記憶體裡也有一份。
# 檔案位置：$HEADSUP_STORE，否則 ${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/store/cc-plugin-you-should-know_builtin-*.json（取最新的）
import glob, json, os, sys, time

def store_path():
    if os.environ.get('HEADSUP_STORE'):
        return os.environ['HEADSUP_STORE']
    base = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')
    found = glob.glob(os.path.join(base, 'plugins', 'store', 'cc-plugin-you-should-know_builtin-*.json'))
    return max(found, key=os.path.getmtime) if found else None

def main(argv):
    summary_only = '--summary' in argv
    args = [a for a in argv if a != '--summary']
    if len(args) != 1:
        print('用法：python3 headsup.py [--summary] <jsonl 路徑>', file=sys.stderr); return 2
    sid = os.path.basename(args[0])
    if sid.endswith('.jsonl'): sid = sid[:-len('.jsonl')]

    p = store_path()
    try:
        with open(p, encoding='utf-8') as f: data = json.load(f)
    except (TypeError, OSError, ValueError):
        return 2
    sessions = data.get('sessions') if isinstance(data, dict) else None
    if not isinstance(sessions, list):
        return 2
    entry = next((s for s in sessions if isinstance(s, dict) and s.get('id') == sid), None)
    view = entry.get('view') if entry else None
    if view is None:
        return 1
    if not isinstance(view, dict) or not isinstance(view.get('kind'), str):
        return 2
    # 只有 offer（剛跳出來）與 explained（有人按過 1）帶內容；asked（按 0 之後）、explaining 等都不算掛著
    if view['kind'] == 'offer':
        text = view.get('explanation')
    elif view['kind'] == 'explained':
        text = view.get('text')
    else:
        return 1
    line = view.get('line')
    if not isinstance(line, str) or not line.strip():
        return 2

    sys.stdout.reconfigure(encoding='utf-8')
    if summary_only:
        print(line.strip()); return 0
    shown = view.get('shownAt')
    shown = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(shown / 1000)) if isinstance(shown, (int, float)) else ''
    print(f'summary={line.strip()}')
    print(f"tag={entry.get('tag') or ''}")
    print(f'shown={shown}')
    print(f"kind={view['kind']}")
    print('text:')
    if isinstance(text, str) and text.strip():
        print(text.rstrip())
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
