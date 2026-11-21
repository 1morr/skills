#!/bin/bash
# 用法：claude plugin eval 帶 --scaffold 時，在每次執行的空工作目錄裡跑這支，產生迷你課程的課件 PDF、過去小考 PDF、t 表 PDF 與學習紀錄。
# 過去小考第 1 題配對樣本差值 d = [2, 4, 2, 4]（n = 4, df = 3, d_bar = 3.0, s_d = 1.1547, SE = 0.5774, t = 5.196 > t_{0.025,3} = 3.182，拒絕 H0）；
# 若誤用獨立雙樣本 t 檢定會算出 t = 1.643（無法拒絕 H0），可直接檢驗 Seeing X vs Y 辨別教學與計算腳本。
set -eu

cat > 學習紀錄.md <<'REC'
# 學習紀錄

## 讀者
- 完全沒有統計基礎，沒學過 Σ 加總符號、標準差與自由度 df。
- 3 小時後小考，只需要一份能離線打開的導讀頁。

## 考試形式
- 20 分鐘紙筆小考（閉卷，不准用電腦軟體，考場附 t 分配表）。
- 題目全英文，須寫出 H0 / Ha、檢定統計量數值、臨界值比較與英文結論句。
REC

GEN_PY=$(mktemp "${TMPDIR:-/tmp}/tutor-eval-fixture.XXXXXX.py")
trap 'rm -f "${GEN_PY}"' EXIT

cat > "${GEN_PY}" <<'PY'
import pymupdf

# 1. lecture3.pdf (3 頁：第 1 頁純行政公告過場頁；第 2 頁公式未定義前置符號；第 3 頁易混淆雙樣本比較)
lec = pymupdf.open()

p1 = lec.new_page(width=640, height=360)
p1.insert_text((60, 80), "STAT101 Topic 3: Comparing Two Means", fontsize=22)
p1.insert_text((60, 140), "Administrative Announcements:", fontsize=15)
p1.insert_text((80, 175), "- Next week office hours moved to Room 402.", fontsize=13)
p1.insert_text((80, 205), "- Bring your student ID card to the quiz.", fontsize=13)

p2 = lec.new_page(width=640, height=360)
p2.insert_text((60, 65), "1. Paired t-Test (Matched Pairs)", fontsize=18)
p2.insert_text((60, 110), "For n matched pairs, let d_i = X_{1i} - X_{2i}.", fontsize=13)
p2.insert_text((60, 145), "Sample mean of differences: d_bar = (1/n) * sum(d_i)", fontsize=13)
p2.insert_text((60, 180), "Sample SD of differences: s_d = sqrt( sum((d_i - d_bar)^2) / (n - 1) )", fontsize=13)
p2.insert_text((60, 215), "Test statistic: t = d_bar / (s_d / sqrt(n)),  with df = n - 1.", fontsize=13)
p2.insert_text((60, 260), "Answer template: Since |t| > t_{alpha/2, df}, we reject H0 at the 5% level.", fontsize=12)

p3 = lec.new_page(width=640, height=360)
p3.insert_text((60, 65), "2. Paired vs Independent Two-Sample Pooled t-Test", fontsize=18)
p3.insert_text((60, 110), "Cue A (Paired): 'same subjects before and after', 'matched twins', 'paired units'.", fontsize=12)
p3.insert_text((60, 140), "  -> Collapse each pair into d_i first; df = n - 1 (number of pairs minus 1).", fontsize=12)
p3.insert_text((60, 185), "Cue B (Independent Pooled): 'two separate random groups A and B' (equal variances).", fontsize=12)
p3.insert_text((60, 215), "  -> t = (x_bar1 - x_bar2) / (s_p * sqrt(1/n1 + 1/n2)),  df = n1 + n2 - 2.", fontsize=12)

lec.save("lecture3.pdf")

# 2. past-quiz.pdf (第 1 題課堂練習：引擎調校前後油耗；第 2 題課本備用題供閉卷盲測改編)
quiz = pymupdf.open()
qp1 = quiz.new_page(width=640, height=360)
qp1.insert_text((50, 55), "Past Quiz 3 (20 minutes, two-tailed alpha = 0.05)", fontsize=16)
qp1.insert_text((50, 95), "Problem 1 (Teacher's Quiz Question):", fontsize=13)
qp1.insert_text((50, 120), "Fuel use (L/hr) was measured on the SAME 4 engines before and after tuning:", fontsize=12)
qp1.insert_text((70, 150), "Engine 1: Before = 12, After = 10", fontsize=12)
qp1.insert_text((70, 172), "Engine 2: Before = 15, After = 11", fontsize=12)
qp1.insert_text((70, 194), "Engine 3: Before = 14, After = 12", fontsize=12)
qp1.insert_text((70, 216), "Engine 4: Before = 19, After = 15", fontsize=12)
qp1.insert_text((50, 250), "Test at alpha = 0.05 (two-tailed) whether mean fuel use changed after tuning.", fontsize=12)

qp2 = quiz.new_page(width=640, height=360)
qp2.insert_text((50, 60), "Textbook Extra Exercises (Unassigned - Practice Bank):", fontsize=15)
qp2.insert_text((50, 100), "Exercise 3.9: Two separate groups of 5 machines from Plant A and 5 from Plant B", fontsize=12)
qp2.insert_text((50, 122), "had mean output 24.0 (s1 = 2.0) and 20.0 (s2 = 2.0). Test at alpha = 0.05 (two-tailed).", fontsize=12)
qp2.insert_text((50, 165), "Exercise 3.10: Reaction time (ms) on the same 5 drivers before and after coffee:", fontsize=12)
qp2.insert_text((50, 187), "Differences d = [10, 14, 12, 16, 8]. Test at alpha = 0.05 (two-tailed).", fontsize=12)
quiz.save("past-quiz.pdf")

# 3. t-table.pdf (考場發的 t 分配臨界值表)
tbl = pymupdf.open()
tp = tbl.new_page(width=500, height=300)
tp.insert_text((50, 50), "Upper-tail Critical Values of t Distribution", fontsize=15)
tp.insert_text((50, 90), "df    t_{0.05} (one-tail)   t_{0.025} (two-tail 5%)", fontsize=12)
for idx, (df, one, two) in enumerate([(2, "2.920", "4.303"), (3, "2.353", "3.182"), (4, "2.132", "2.776"), (6, "1.943", "2.447"), (8, "1.860", "2.306")]):
    tp.insert_text((50, 120 + idx * 24), f"{df:<5d} {one:<21s} {two}", fontsize=12)
tbl.save("t-table.pdf")
PY

if command -v uv >/dev/null 2>&1; then
  uv run --no-project --with pymupdf python3 "${GEN_PY}"
else
  python3 "${GEN_PY}"
fi
