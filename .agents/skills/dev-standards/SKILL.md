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
2. **AGENTS.md**：在專案根目錄建立，作為所有 AI 工具遵循的開發與協作規範。內容應涵蓋：專案技術棧、目錄結構慣例、程式風格、commit 規範、禁止事項（如機密資訊）、如何執行測試/建置。若專案需要相容 Codex，額外建立 `AGENTS.md`，內容應指向或同步 `AGENTS.md` 的規範，不要重複維護兩份不一致的內容。
3. **project-memory.md**：建立於 `/doc/project-memory.md`，用於記錄長期有效的專案決策、技術選型、重要限制與已確認的業務規則。文件必須包含明確的更新規則：僅在確認新決策、修改既有決策或發現重要限制時才更新；每次更新必須記錄日期、原因與影響範圍（以條列或表格呈現的變更紀錄）。
4. **todo.md**：讀取 `/doc/architecture.md`，建立 `/doc/todo.md`，列出所有待開發需求、相依關係、驗收條件與優先級，並依優先級排序。每個項目需包含狀態欄位（Todo / In Progress / Done）。**不得**把需求文件或架構文件中標示為「待確認事項」的內容直接列為可開發項目——這類項目應另外標註「等待確認」，待確認事項釐清後才能轉為正式待辦。

## 輸出檔案位置

- `AGENTS.md`（專案根目錄）
- `AGENTS.md`（專案根目錄，若需要相容 Codex）
- `/doc/project-memory.md`
- `/doc/todo.md`

全文以繁體中文撰寫。完成後告知使用者各檔案已產生的位置，並簡短說明 todo.md 中優先級最高的待辦項目是什麼。
