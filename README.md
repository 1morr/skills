# skills

給 [Claude Code](https://code.claude.com) 用的 skills，打包成一個 plugin。

| Skill | 叫用 | 做什麼 |
|---|---|---|
| [showcase](skills/showcase/SKILL.md) | `/1morr:showcase [commit \| 範圍 \| PR# \| 分支] [no-run] [post] [auto]`，或直接說「展示這個改動」。預設實跑擷取、不提問；`post` 貼成 PR 留言，`auto` 全程不問（適合接在自己的流程後面） | 把一次改動展示給沒寫它的人，不必問 agent、不必自己跑：實跑修改前後兩版，擷取截圖、錄影、輸出與測試結果，產出內嵌證據的 HTML 報告（貼到 PR 時另有純文字版），說明改了什麼、為什麼、做了哪些決策 |
| [tutor](skills/tutor/SKILL.md) | `/1morr:tutor [作業 \| topic \| 考試] [rush \| learn]`，或說「教我」「看不懂」「複習」 | 把大學課程、作業或考試教給沒上過課、零基礎的人：以老師課件為唯一標準，把要看的那塊課件截進來圈好，產出單一 HTML 講解頁；作業另出照老師格式寫的答案紙。`rush`（兩天內要交 / 考）不提問、不出練習；`learn` 一次一小課、有回想題和學習紀錄 |
| [ticket-coordinator](skills/ticket-coordinator/SKILL.md) | `/1morr:ticket-coordinator <票目錄> [順序]`（只能手動叫用） | 當協調者，用 [Orca](https://www.onorca.dev) 為每張票開一個子 Claude Code session 解票、代答提問、驗收、合併，逐張跑完隊列。需要 Orca |

## 安裝

在 Claude Code 裡：

```
/plugin marketplace add 1morr/skills
/plugin install 1morr@1morr-skills
```

plugin 不釘版本，`/plugin update 1morr@1morr-skills` 會更新到最新 commit；也可以在 `/plugin` 的 Marketplaces 分頁打開自動更新。

## 開發

把 clone 下來的目錄加成 marketplace，plugin 會直接從這個目錄載入：改完檔案，開新 session 或執行 `/reload-plugins` 就生效，不用 push、不用重裝。

```
claude plugin marketplace add <clone 的路徑>
claude plugin install 1morr@1morr-skills
```

新增 skill：建 `skills/<名稱>/SKILL.md`，plugin 會自動載入；同時在上面的表格加一列。

測試（CI 跑的就是這三條）：

```
python -m unittest discover -s skills/showcase/tests
bash skills/ticket-coordinator/scripts/selftest.sh
python -m unittest discover -s skills/tutor/tests
```

檢查 manifest：`claude plugin validate .`。manifest 刻意不寫 `version`（寫了會把使用者釘在那個版本），所以 validator 會提醒缺 `version`，那條可以忽略。

## 授權

MIT
