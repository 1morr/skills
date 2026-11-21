# 交給使用者

交付單一自包含 HTML 頁時照這份非阻塞流程：不替使用者開瀏覽器或分頁，也不停下來等使用者看完才結束或關 server。路徑一律寫從根目錄算起的完整絕對路徑（worktree 與暫存目錄也一樣，避免相對路徑被對到使用者主目錄）。

- **本機桌面環境（預設）**：直接在對話給檔案的完整路徑，使用者可直接離線打開。若使用者要求網址或環境不便直接開本機檔，才走下方背景 server。
- **遠端／無桌面環境**（SSH、容器、遠端工作站，需透過本機 port forwarding 檢視）：在背景起 `http.server` 綁 `127.0.0.1`，在對話同時給網址 `http://127.0.0.1:<port>/<檔名>`（中文或空白做 URL 編碼）與完整路徑：
  - **在瀏覽器 `localStorage` 存進度與筆跡的頁**（如 `tutor` 的導讀頁、練習頁、模擬卷）：`localStorage` 綁定 origin（含 port），隨機換 port 會讓既有進度與筆跡讀不到。以頁面所在資料夾規範化絕對路徑算 deterministic hash port（例如 `python3 -c 'import hashlib,os,sys; p=os.path.realpath(sys.argv[1]); print(40000 + int(hashlib.sha256(p.encode()).hexdigest()[:8], 16) % 20000)' "<資料夾>"`），該 port 已在服務同一資料夾就直接沿用，否則背景執行 `python3 -u -m http.server <port> --bind 127.0.0.1 --directory <資料夾>`（Windows 無 `python3` 用 `python`）。
  - **不存 `localStorage` 進度的檢視頁**（如 `diff`、`dashboard` 靜態頁）：同樣可用 deterministic port，或傳 `0` 由系統挑空埠並從輸出取 `port <n>`。
- 頁面所在資料夾將被移除前（例如清理 worktree），先把對應的背景 server 停掉，再從新位置交付。

完成條件：檔案已寫出且對話裡有完整絕對路徑；若起了背景 server，`curl -sI <網址>` 回 200 且對話裡附有網址。給出即完成。
