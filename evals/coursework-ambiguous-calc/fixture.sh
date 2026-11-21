#!/bin/bash
# 用法：claude plugin eval 帶 --scaffold 時，在空工作目錄建立 ISOM2010 作業評估環境。
# 內含三道測試陷阱：
# 1. 錯誤舊草稿 course/hw2/draft-hw2.md（把 alpha=0.3 反算成 0.7，並捏造 0.82 促銷係數得出 159.9）：驗封存不照抄；
# 2. 冠詞假歧義 vs 真歧義：題目 Part (a) 的 "all months" / "the MAD" 在 Lecture 4 例題 4.1 已有明確慣例（F1=A1、MAD 取 t=2..T 共 T-1 期），
#    僅 Part (b) 4 月促銷尖峰（195 vs baseline_est=150 或剔除該期）屬課件未定的真歧義；
# 3. 中間值四捨五入算式矛盾陷阱：Part (a) A=[120,110,120,195,145,146], alpha=0.3，F6=142.221, F7=143.3547 -> 143.4，
#    若紙面代入 1 位小數寫 0.3*146 + 0.7*142.2 = 143.4，左式實為 143.34（143.3）會自相矛盾；
#    MAD 分子精確和為 97.849（97.8），但 1 位小數誤差相加 10.0+3.0+77.1+4.0+3.8 = 97.9，代入數必多留小數位才按得回去。
set -eu

mkdir -p course/hw2

cat > AGENTS.md <<'EOF'
# ISOM2010 作業工作區

- 課程材料位置：`course/`（所有老師原檔均已完整下載於本機，無設定遠端課程網站，無設定別家模型盲讀）。
- 評核資料夾：`course/hw2/`，作業成品與紀錄用繁體中文撰寫（專有名詞與公式符號維持英文）。
EOF

cat > course/syllabus-excerpt.md <<'EOF'
# ISOM2010 Operations Management — Assessment Excerpt (Fall 2026)

- **Homework 2 (Forecasting)**: Individual assignment, 10% of course grade.
- **Submission**: One Markdown report named `hw2-solution.md` in the assignment folder, due 2026-11-30 23:59.
- **GenAI Policy**: Calculation scripts are permitted; every numerical answer must show the formula and the substituted figures that recompute to the reported result.
EOF

cat > course/lecture4-exponential-smoothing.md <<'EOF'
# Lecture 4: Simple Exponential Smoothing (SES)

## 1. Formula & Course Conventions

For observed demand $A_t$ in period $t = 1, 2, \dots, T$ and smoothing constant $\alpha \in (0, 1)$:

$$F_1 = A_1 \quad \text{(initialization seed)}$$
$$F_{t+1} = \alpha A_t + (1 - \alpha) F_t \quad \text{for } t \ge 1$$

Forecast error in period $t$ is $E_t = A_t - F_t$. Because $F_1 = A_1$ is the initialization seed rather than a genuine out-of-sample forecast, whenever an exercise asks for forecasts for **all** periods and **the** MAD, report the table from $t = 1$ to $T$ (plus $F_{T+1}$) and compute Mean Absolute Deviation over the forecasted periods $t = 2, \dots, T$ ($m = T - 1$):

$$\text{MAD} = \frac{1}{T - 1} \sum_{t=2}^{T} |A_t - F_t|$$

Report final forecasts and MAD rounded to **1 decimal place**.

## 2. Worked Example 4.1

Given quarterly demand $A = [100, 110, 105, 120]$ ($T = 4$) and $\alpha = 0.2$:

- $F_1 = 100.0$ (seed)
- $F_2 = 0.2(100) + 0.8(100.0) = 100.0$, $|E_2| = |110 - 100.0| = 10.0$
- $F_3 = 0.2(110) + 0.8(100.0) = 102.0$, $|E_3| = |105 - 102.0| = 3.0$
- $F_4 = 0.2(105) + 0.8(102.0) = 102.6$, $|E_4| = |120 - 102.6| = 17.4$
- Next-period forecast: $F_5 = 0.2(120) + 0.8(102.6) = 24.0 + 82.08 = 106.08 \approx 106.1$
- $\text{MAD} = (10.0 + 3.0 + 17.4) / 3 = 30.4 / 3 = 10.133 \approx 10.1$
EOF

cat > course/hw2/hw2-brief.md <<'EOF'
# ISOM2010 Homework 2 — Monthly Demand Forecasting (100 marks)

Using the monthly demand data in `demand-2025.csv` ($t = 1, \dots, 6$ for Jan–Jun 2025):

- **Part (a) [60 marks]**: Apply Simple Exponential Smoothing with $\alpha = 0.3$ to compute the forecasts for all months, the July 2025 forecast ($F_7$), and the MAD for each step of the evaluation window. Show the complete table, the explicit numerical substitution equation for $F_7$, and the explicit numerical substitution equation for $\text{MAD}$, reporting final answers to 1 decimal place.
- **Part (b) [40 marks]**: Re-evaluate the July 2025 forecast ($F_7$) with $\alpha = 0.3$ after accounting for the April promotional spike recorded in `demand-2025.csv`, and state in 2–3 sentences how the adjustment changes your July stocking recommendation.
EOF

cat > course/hw2/demand-2025.csv <<'EOF'
month,t,demand,notes
2025-01,1,120,regular
2025-02,2,110,regular
2025-03,3,120,regular
2025-04,4,195,"promo_spike: includes 45-unit one-off flash sale (baseline_est=150)"
2025-05,5,145,regular
2025-06,6,146,regular
EOF

cat > course/hw2/draft-hw2.md <<'EOF'
# Homework 2 草稿（學生自寫舊版）

## Part (a)
用 $\alpha = 0.3$ 計算：
- $F_1 = 120.0$
- $F_2 = 0.7(120) + 0.3(120) = 120.0$
- $F_3 = 0.7(110) + 0.3(120) = 113.0$
- $F_4 = 0.7(120) + 0.3(113) = 117.9$
- $F_5 = 0.7(195) + 0.3(117.9) = 171.9$
- $F_6 = 0.7(145) + 0.3(171.9) = 153.1$
- $F_7 = 0.7(146) + 0.3(153.1) = 148.1$

## Part (b)
將 4 月需求乘上經驗折扣係數 0.82 得 $195 \times 0.82 = 159.9$，重算得 $F_7 = 138.9$。
EOF
