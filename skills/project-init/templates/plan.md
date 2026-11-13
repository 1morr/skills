# {{PROJECT}} 實作計劃

> 狀態：骨架。brief 的〈範圍與順序〉定案後再寫。里程碑的順序與範圍在 `docs/roadmap.md`，這裡只寫架構。

## 0. 工程慣例

## 1. 架構總覽

### 1.1 執行形態

### 1.2 目錄結構

### 1.3 依賴規則【決定】

寫明模組之間誰能 import 誰、用什麼工具強制，並在 M0 票 01 接上。

### 1.4 主要依賴

每個依賴寫明版本、用途、選它的理由。

## 2. 模組

每個模組一節：介面、資料流、狀態。

## 3. 測試策略

## 4. 開發環境與閘門

M0 票 01 要交付：

- `docs/development.md`〈全部檢查〉補上這個技術棧的 lint、format、typecheck 與 test，跑在 pre-commit 與 CI（`.github/workflows/ci.yml`）。
- §1.3 依賴規則的強制工具與它的測試。

已經就位（project-init 建的）：`scripts/check_docs.py`（progress、spec、票的格式）、`scripts/check_commit_msg.py` 與 commit-msg hook。

## 5. 風險與回寫點

實作中發現與 brief 不符時要回寫的地方。
