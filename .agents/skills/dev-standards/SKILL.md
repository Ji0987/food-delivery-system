---
name: dev-standards
description: 讀取 /doc/requirements.md、/doc/architecture.md 與 /doc/data-model.md，建立供 AI 開發代理與開發者共同遵守的專案規範（AGENTS.md、project-memory.md）與待辦清單（todo.md）。當使用者要「建立開發規範」、「產生 AGENTS.md」或前三份文件已完成要開始開發時使用。
---

# 開發規範 Skill

你現在的角色是**專案規範制定者**，任務是把前三份文件（需求、架構、資料模型）落地成一套所有 AI 工具與開發者都要遵守的協作規範，並排出可執行的待辦清單。

## 前置條件

- 讀取 `/doc/requirements.md`、`/doc/architecture.md`、`/doc/data-model.md`。
- 若任一份找不到，**停止執行**並告知使用者缺少哪些文件，不要自行補足繼續往下做。

## 技術基準（除非需求/架構文件另有指定，否則採用此組合）

- 後端：FastAPI；前端：React（若專案規模小、需求文件指定純 HTML+JS，則以需求文件為準）
- 本地開發資料庫：SQLite；正式部署：Render.com；正式資料庫：Render PostgreSQL

## 必須遵守的規範內容

1. **機密資訊管理**：規範必須明確禁止將 API Key、密碼、Token、連線字串及其他機密資訊提交至 Git 或硬編碼於程式中；須使用環境變數，並提供 `.env.example` 說明所需設定項目（僅列變數名稱與用途，不含真實值），將 `.env` 加入 `.gitignore`。
2. **AGENTS.md**：在專案根目錄建立，作為所有 AI 工具遵循的開發與協作規範。內容應涵蓋：專案技術棧、目錄結構慣例、程式風格、commit 規範、**Git 分支與 PR 規範**（見第5點）、禁止事項（如機密資訊）、如何執行測試/建置。若專案需要相容 Codex，額外建立 `AGENTS.md`，內容應指向或同步 `AGENTS.md` 的規範，不要重複維護兩份不一致的內容。
3. **project-memory.md**：建立於 `/doc/project-memory.md`，用於記錄長期有效的專案決策、技術選型、重要限制與已確認的業務規則。文件必須包含明確的更新規則：僅在確認新決策、修改既有決策或發現重要限制時才更新；每次更新必須記錄日期、原因與影響範圍（以條列或表格呈現的變更紀錄）。
4. **todo.md**：讀取 `/doc/architecture.md`，建立 `/doc/todo.md`，列出所有待開發需求、相依關係、驗收條件與優先級，並依優先級排序。每個項目需包含欄位：**owner（負責組員）**、**對應 branch 名稱**、狀態（Todo / In Progress / Done）。原則上一項待辦對應一位 owner、一個 branch、一個 PR，避免多人同時改同一項目造成不必要衝突。**不得**把需求文件或架構文件中標示為「待確認事項」的內容直接列為可開發項目——這類項目應另外標註「等待確認」，待確認事項釐清後才能轉為正式待辦。
5. **Git 協作規範**：AGENTS.md 必須明確納入以下規則（若專案已有其他既定 Git 流程，以既定流程為準，不強制覆蓋）：
   - **分支角色**：`main` 是可展示／發布的穩定版本，禁止直接 push；`dev` 是整合測試分支，彙集已完成功能等待驗收；所有開發工作一律從 `dev` 建立 `feature/<scope>`（新功能）或 `fix/<scope>`（修正）分支，使用小寫 kebab-case 命名，一個 branch 對應一個可合併的小任務。
   - **PR 規則**：`feature/* → dev` 與 `dev → main` 一律經 Pull Request，禁止直接合併或 force push；PR 內容須說明目的、影響檔案、驗收方式（測試結果或操作截圖）；review 應由非作者的組員執行，`dev → main` 的發布 PR 只由專案整合者／組長建立。
   - **合併前準備**：分支作者負責在發 PR 前將 `dev` 最新變更同步進自己的 feature 分支並解決衝突，不應把衝突留給 reviewer 或整合者處理；PR 避免夾帶與任務無關的格式化或大範圍重排。
   - **課堂／小型專案例外**：分支保護的 required approvals 可先設為 0，方便個人或初期示範操作，待熟悉流程或組員到齊後再調高。
   - **完成定義（Done）**：一項待辦視為完成，須同時滿足——PR 已 review（或依例外規則直接可合併）、已合併進 dev（或 main）、功能可實際操作、驗收結果已記錄、`todo.md` 對應項目狀態已更新。
   - **可追溯性**：每位組員的貢獻應可從 branch、commit、PR、review、merge 紀錄追溯；不得由少數人代為 push 全部程式碼。

## 輸出檔案位置

- `AGENTS.md`（專案根目錄）
- `AGENTS.md`（專案根目錄，若需要相容 Codex）
- `/doc/project-memory.md`
- `/doc/todo.md`

全文以繁體中文撰寫。完成後告知使用者各檔案已產生的位置，並簡短說明 todo.md 中優先級最高的待辦項目是什麼。
