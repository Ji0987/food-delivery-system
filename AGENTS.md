# AGENTS.md｜餐點外送系統開發規範

本檔案是所有 AI 開發代理（Claude Code、Codex、GitHub Copilot 等）與人類開發者共同遵守的專案規範。設計依據：`/doc/requirements.md`、`/doc/architecture.md`、`/doc/data-model.md`。修改本專案任何程式碼前，請先確認這三份文件與 `/doc/project-memory.md` 的最新內容。

## 專案技術棧

| 層級 | 技術 |
|---|---|
| 前端 | 純 HTML + JavaScript（不使用 React/Vue 等框架） |
| 後端 | FastAPI（Python） |
| 本機開發資料庫 | SQLite |
| 正式部署資料庫 | Render PostgreSQL |
| 部署平台 | Render.com |
| 定位/地圖 | 瀏覽器 Geolocation API + OpenStreetMap（Leaflet.js） |
| 即時更新機制 | 前端輪詢（REST API），非 WebSocket |

技術選型理由與細節見 `/doc/architecture.md`。**不得**在未與使用者確認的情況下更換上述技術棧（例如把前端改成 React、把即時位置改成 WebSocket）。

## 目錄結構慣例

```
/
├── AGENTS.md, CLAUDE.md          # 本規範
├── doc/                           # 專案文件（需求、架構、資料模型、待辦、測試計畫、專案記憶）
├── backend/                       # FastAPI 後端
│   ├── main.py                    # 應用進入點
│   ├── models/                    # 資料模型（對應 data-model.md 各實體）
│   ├── routers/                   # API 路由（依 architecture.md 模組劃分：auth/menu/cart/orders/delivery/admin）
│   ├── schemas/                   # Pydantic 請求/回應模型
│   ├── services/                  # 業務邏輯（訂單狀態機、付款模擬、配送搶單等）
│   ├── requirements.txt
│   ├── render.yaml
│   └── .env.example
└── frontend/                       # 純 HTML+JS 前端，依角色分頁（consumer/restaurant/courier/admin）
```

新增檔案時比照上述慣例放置；如需調整目錄結構，先更新本節並記錄於 `/doc/project-memory.md`。

## 程式風格

- Python：遵循 PEP 8，FastAPI 路由與 Pydantic schema 分離，善用型別提示（型別提示是 FastAPI 的核心價值，不可省略）。
- JavaScript：使用原生 ES6+ 語法即可，不引入額外前端框架或建置工具鏈（維持「純 HTML+JS」的教學定位）。
- 金額一律使用 `Decimal`／`NUMERIC`，不得用浮點數 `float` 直接運算價格（避免浮點誤差，呼應 `data-model.md` 待確認事項）。
- 訂單狀態轉換邏輯集中在後端 service 層（對應 architecture.md 的「訂單服務」模組），不得在多處各自實作狀態判斷邏輯。

## Commit 規範

- Commit message 說明「做了什麼」，不描述「怎麼做」（例如：`新增訂單狀態轉換 API`，而非 `修改 routers/orders.py 加上 PATCH`）。
- 不直接 push 到 `main` 分支，除非使用者明確要求。
- 不執行破壞性操作（`git reset --hard`、`git push --force`），除非使用者確認。

## 機密資訊管理（強制規則）

- **禁止**將 API Key、密碼、Token、資料庫連線字串等機密資訊提交至 Git 或硬編碼於程式碼中。
- 所有機密設定一律透過環境變數管理，專案根目錄／`backend/` 需提供 `.env.example`，僅列出所需變數名稱與用途說明，**不含任何真實值**：

  ```
  # .env.example
  DATABASE_URL=          # 本機留空使用 SQLite，正式環境填 Render PostgreSQL 連線字串
  JWT_SECRET_KEY=        # JWT 簽章密鑰，正式環境需為高強度隨機字串
  JWT_ALGORITHM=HS256
  ```

- `.env` 必須加入 `.gitignore`，不得提交至版本控制。
- 若在程式碼審查或除錯過程中發現硬編碼機密，須立即提醒使用者並改用環境變數。

## 如何執行測試／建置

- 本機啟動後端：`cd backend && uvicorn main:app --reload`
- 本機安裝依賴：`pip install -r backend/requirements.txt`
- 測試策略與測試案例見 `/doc/test-plan.md`（由 `test-plan` skill 產生後補上）。
- 正式部署：推送至 GitHub → Render Web Service 依 `render.yaml`／Build & Start Command 自動建置，見 `/doc/architecture.md` 第 9 節部署方式。

## 禁止事項

- 禁止將機密資訊寫入程式碼或提交至 Git（見上）。
- 禁止未經確認就把 `/doc/requirements.md`／`/doc/architecture.md`／`/doc/data-model.md` 中標示為「待確認事項」的內容當作已定案直接實作。
- 禁止繞過已核准的訂單狀態機邏輯（例如讓消費者端 API 直接把訂單改成 `delivered`）。
- 禁止在未告知使用者的情況下更換技術棧或架構設計。

## 與 CLAUDE.md 的關係

`CLAUDE.md` 內容同步指向本檔案，不重複維護規範內容。若兩者出現不一致，以本檔案（`AGENTS.md`）為準。
