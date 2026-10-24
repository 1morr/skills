# 給其他腳本 source：選一個跑得起來的 Python 3 放進 $PY，並提供跨平台的 age()。
# macOS 只有 python3；Windows 的 python3 可能是 Microsoft Store 的空殼（跑了只印訊息、不是 0），所以每個都實際跑一次。
PY=
for c in python3 python; do
  "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1 && { PY=$c; break; }
done
[ -n "$PY" ] || { echo "找不到可用的 Python 3（試過 python3、python）" >&2; exit 1; }
# age <檔>：距離最後修改幾秒。GNU `stat -c` 與 BSD `stat -f` 不通用，交給 Python
age() { "$PY" -c 'import os, sys, time; print(int(time.time() - os.path.getmtime(sys.argv[1])))' "$1"; }
