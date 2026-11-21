# 用法：python3 headsup.py [--summary] (--worktree <worktree 路徑> | <jsonl 路徑或 session id>)
# 僅限 Claude Code worker：從內建 mod「You should know」的狀態檔讀目前掛著的 Heads up，不用讀畫面、不用按 1 展開。
#   exit 0  有一則掛著。--summary 只印摘要一行；否則印 summary= / tag= / shown= / kind=，再一行 text:，後面是全文
#           （就是按 1 Learn more 看到的內容；mod 沒存全文時 text: 後面是空的，要照 TUI.md 展開讀畫面）
#   exit 1  狀態檔讀得到，這個 session（或該 worktree 下所有 session）沒有掛著的 Heads up（包括按 0 收起後那約 20 秒的「Dismissed.」）
#   exit 2  讀不到或格式不認得（mod 沒開、CLI 改了格式）：呼叫端視需要改看畫面
# 狀態檔是 mod 的內部格式（CLI 2.1.322 讀程式碼得出），沒有公開文件。只讀不寫：檔案歸 Claude Code 管，它記憶體裡也有一份。
# 檔案位置：$HEADSUP_STORE，否則 ${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/store/cc-plugin-you-should-know_builtin-*.json（取最新的）
import glob, json, os, re, sys, time


def claude_base():
    return os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')


def store_path():
    if os.environ.get('HEADSUP_STORE'):
        return os.environ['HEADSUP_STORE']
    found = glob.glob(os.path.join(claude_base(), 'plugins', 'store', 'cc-plugin-you-should-know_builtin-*.json'))
    return max(found, key=os.path.getmtime) if found else None


def worktree_sids(worktree):
    wt = worktree.replace('\\', '/')
    if len(wt) > 1:
        wt = wt.rstrip('/')
    pdir = os.path.join(claude_base(), 'projects', re.sub(r'[^A-Za-z0-9]', '-', wt))
    found = glob.glob(os.path.join(pdir, '*.jsonl'))
    found.sort(key=os.path.getmtime, reverse=True)
    return [os.path.basename(f)[:-len('.jsonl')] for f in found]


def inspect_entry(entry):
    view = entry.get('view') if entry else None
    if view is None:
        return 1, None
    if not isinstance(view, dict) or not isinstance(view.get('kind'), str):
        return 2, None
    # 只有 offer（剛跳出來）與 explained（有人按過 1）帶內容；asked（按 0 之後）、explaining 等都不算掛著
    if view['kind'] == 'offer':
        text = view.get('explanation')
    elif view['kind'] == 'explained':
        text = view.get('text')
    else:
        return 1, None
    line = view.get('line')
    if not isinstance(line, str) or not line.strip():
        return 2, None
    return 0, (entry, view, line.strip(), text)


def main(argv):
    summary_only = False
    worktree = None
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == '--summary':
            summary_only = True
            i += 1
        elif argv[i] == '--worktree':
            if i + 1 >= len(argv):
                print('用法：python3 headsup.py [--summary] (--worktree <worktree 路徑> | <jsonl 路徑或 session id>)', file=sys.stderr)
                return 2
            worktree = argv[i + 1]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    if (worktree is None) == (len(args) != 1):
        print('用法：python3 headsup.py [--summary] (--worktree <worktree 路徑> | <jsonl 路徑或 session id>)', file=sys.stderr)
        return 2

    p = store_path()
    try:
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
    except (TypeError, OSError, ValueError):
        return 2
    sessions = data.get('sessions') if isinstance(data, dict) else None
    if not isinstance(sessions, list):
        return 2

    if worktree is not None:
        sids = worktree_sids(worktree)
    else:
        sid = os.path.basename(args[0])
        if sid.endswith('.jsonl'):
            sid = sid[:-len('.jsonl')]
        sids = [sid]

    by_id = {s.get('id'): s for s in sessions if isinstance(s, dict) and s.get('id')}
    bad = False
    hit = None
    for sid in sids:
        rc, res = inspect_entry(by_id.get(sid))
        if rc == 0:
            hit = res
            break
        if rc == 2:
            bad = True
    if hit is None:
        return 2 if bad else 1

    entry, view, line, text = hit
    sys.stdout.reconfigure(encoding='utf-8')
    if summary_only:
        print(line)
        return 0
    shown = view.get('shownAt')
    shown = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(shown / 1000)) if isinstance(shown, (int, float)) else ''
    print(f'summary={line}')
    print(f"tag={entry.get('tag') or ''}")
    print(f'shown={shown}')
    print(f"kind={view['kind']}")
    print('text:')
    if isinstance(text, str) and text.strip():
        print(text.rstrip())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
