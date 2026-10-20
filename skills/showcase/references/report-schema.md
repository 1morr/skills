# report.json

文字欄位接受簡易 Markdown：段落、`- ` 與 `1. ` 清單、`` `code` ``、`**粗體**`、`[文字](https://…)`。路徑相對於報告目錄。

```json
{
  "title": "搜尋結果返回時保留捲動位置",
  "lang": "zh-Hant",
  "range": { "base": "a1b2c3d", "head": "e4f5a6b", "head_ref": "fix/scroll" },
  "summary": "從搜尋結果返回列表時，會回到原本的位置。",
  "why": {
    "text": "長列表每點一次結果，使用者就找不到剛剛看到哪裡。",
    "sources": ["#212", "commit e4f5a6b"]
  },
  "how": "列表在打開結果時記下捲動位置，返回時還原。",
  "decisions": [
    {
      "decision": "位置存在記憶體，不放進網址",
      "why": "放進網址會讓分享出去的連結也帶著位置。",
      "alternatives": "網址參數；session storage",
      "basis": "stated",
      "source": "#212 的討論"
    }
  ],
  "files": {
    "src/search/ResultList.tsx": "記下並還原捲動位置。",
    "src/search/ResultList.test.tsx": "涵蓋還原。",
    "*.lock": "測試輔助套件帶進來的依賴升級。"
  },
  "hunks": [
    { "file": "src/search/ResultList.tsx", "match": "scrollTop", "note": "等列表渲染完才還原，那時位置才存在。" }
  ],
  "evidence": {
    "level": "before-after",
    "items": [
      { "kind": "compare", "caption": "從第 40 筆返回", "before": "before-back.jpg", "after": "after-back.jpg" },
      { "kind": "image", "caption": "沒有結果時", "after": "after-empty.jpg" },
      { "kind": "output", "caption": "單元測試", "command": "npm test -- ResultList", "before_file": "tests-before.txt", "after_file": "tests-after.txt" }
    ]
  },
  "try_it": ["`npm run dev`，搜尋 `test`，打開第 40 筆，按返回"],
  "unverified": ["Safari", "超過一萬筆的列表"]
}
```

| 欄位 | 必填 | 意義 |
|---|---|---|
| `title` | 是 | 讀者會怎麼稱呼這個改動。 |
| `lang` | 否 | 標籤語言：`en`（預設）或 `zh-Hant`。 |
| `range.base` | 是 | 任何 git revision。 |
| `range.head` | 是 | git revision，或 `null` 代表工作區（含未追蹤檔案）。 |
| `range.base_ref`、`range.head_ref` | 否 | 顯示在 SHA 旁的分支名。只有當該分支正指向那個 commit 時才顯示，否則捨棄並警告。 |
| `summary` | 是 | 使用者感受到的效果。 |
| `why.text`、`why.sources` | 否 | `sources` 為空時顯示「待作者補充」，`text` 若有則標為推斷。 |
| `how` | 否 | 做法。 |
| `decisions[]` | 否 | `decision`、`why`、選填 `alternatives`、`basis`（`stated` 有來源或 `inferred` 推斷，預設 `inferred`）、選填 `source`。 |
| `files` | 是 | 改動的路徑或 glob → 說明。diff 裡的每個路徑都需要一則，點開頭的目錄也算。鍵比對完整的 repo 相對路徑；精確路徑優先於 glob；`*` 會跨過 `/`。 |
| `hunks[]` | 否 | `file`、選填 `match`（保留文字含它的 hunk；不給就是全部）、`note`。 |
| `evidence.level` | 是 | `before-after`、`after`、`tests` 或 `static`。 |
| `evidence.why_not_higher` | 低於 `before-after` 時 | 障礙是什麼。 |
| `evidence.items[]` | 否 | 種類見下。 |
| `try_it[]`、`unverified[]` | 否 | 每個字串一個步驟或一個缺口。 |

證據種類：

- `image`：`after` 圖片路徑。只有 head 的截圖。
- `compare`：`before` 與 `after` 圖片路徑。並排顯示，兩張尺寸相同時另有滑桿。
- `output`：選填 `command`、`after` 文字或 `after_file`、選填 `before` 文字或 `before_file`（同一指令在 base 的結果）。沒有 `command` 時原樣顯示一個檔案，例如為 showcase 寫的重現。文字也會出現在 `pr.md`。

圖片：`.png`、`.jpg`、`.jpeg`、`.webp`、`.gif`、`.svg`。

渲染器會對 `report.json` 與文字證據裡的家目錄路徑、像秘密的值發出警告。它讀不到圖片裡的字；截圖要自己遮蔽。
