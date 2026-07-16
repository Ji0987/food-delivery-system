# 專案記憶｜餐點外送系統

記錄長期有效的專案決策、技術選型、重要限制與已確認的業務規則。

**更新規則**：僅在確認新決策、修改既有決策，或發現重要限制時才更新本文件；每次更新須記錄日期、原因與影響範圍。不記錄暫時性的任務進度（那屬於 `/doc/todo.md`）。

---

## 決策紀錄

### 2026-07-16｜技術棧與部署方式確定

- **決策**：後端 FastAPI、前端純 HTML+JS（不用框架）、本機 SQLite、正式部署 Render.com + Render PostgreSQL。
- **原因**：課程教學情境，需降低前端學習門檻，優先教會 Web 三層架構觀念而非框架操作。
- **影響範圍**：所有後續架構、資料模型、開發規範文件皆以此技術棧為基準；若後續要導入前端框架或更換部署平台，需重新評估 `architecture.md`。

### 2026-07-16｜訂單狀態生命週期確定（經 Plan Mode 核准）

- **決策**：訂單採主狀態機（主線為 `pending`→`accepted`→`preparing`→`ready_for_pickup`→`picked_up`→`delivering`→`delivered`→`completed`；另有 `pending`→`cancelled` 與 `accepted`→`rejected` 終止路徑）+ 付款子狀態（`unpaid`/`paid`/`refunded`）分離設計。詳見 `/doc/requirements.md` 訂單狀態生命週期章節。
- **原因**：訂單牽涉消費者/餐廳/外送員三方與付款/出餐/配送三個子系統，線性單一狀態會混淆各方視角，故拆分主狀態與付款子狀態。
- **影響範圍**：`orders.status`、`payments.status` 欄位設計（`data-model.md`）與所有狀態轉換 API（`architecture.md` 第 6 節）皆依此狀態機實作，不得任意增減狀態值而未同步更新三份文件。

### 2026-07-16｜付款採模擬付款，不串真實金流

- **決策**：系統不整合真實第三方金流服務，僅記錄付款狀態（`unpaid`/`paid`/`refunded`），不實際扣款。
- **原因**：教學情境，避免觸及真實金流的合規與費用問題；使用者於需求訪談階段明確選擇此方案。
- **影響範圍**：`payments` 資料表不儲存卡號等真實金流敏感資訊；若未來要接真金流，需重新設計付款模組並補充安全性規範。

### 2026-07-16｜配送需即時位置追蹤，採輪詢而非 WebSocket

- **決策**：外送員配送時需即時回報位置，消費者可查詢；技術上採短週期輪詢（REST API，建議 5-10 秒），非 WebSocket。
- **原因**：教學情境優先考量實作簡單度與 Render 免費方案相容性，WebSocket 需額外處理連線管理與 Render 免費方案閒置行為，複雜度顯著提高。
- **影響範圍**：`architecture.md` 資料流章節、`data-model.md` 的 `delivery_locations` 表設計；若未來效能或即時性要求提高，可替換為 WebSocket 屬後續優化項目，需重新評估架構。

### 2026-07-16｜外送員採自行搶單機制

- **決策**：外送員從待配送訂單列表中自行搶單，非系統自動指派。
- **原因**：使用者於架構設計待確認事項回覆中明確選擇，優先考量實作簡單度。
- **影響範圍**：新增 `GET /orders/available`、`POST /orders/{id}/claim` API；`delivery_assignments.order_id` 需唯一約束防止重複搶單競態，見 `data-model.md` 第 2 節說明。

### 2026-07-16｜地圖視覺化採用 OpenStreetMap

- **決策**：地圖顯示使用 OpenStreetMap 圖資搭配 Leaflet.js（開源前端套件）。
- **原因**：免費、不需第三方地圖 API 金鑰與費用，符合純 HTML+JS 前端與教學情境。
- **影響範圍**：`architecture.md` 技術選型章節；前端配送位置顯示頁面需引入 Leaflet.js。

### 2026-07-16｜通知機制僅需網頁內即時提醒

- **決策**：不建置 Email／簡訊／瀏覽器推播通知，僅需前端既有輪詢機制偵測到狀態變化時於畫面顯示提示。
- **原因**：使用者確認範圍，避免引入額外通知基礎設施的複雜度與費用。
- **影響範圍**：架構不含獨立通知模組；`architecture.md` 已移除相關待確認事項。

### 2026-07-16｜效能目標為小規模正式上線（數百人同時在線）

- **決策**：系統設計目標為同時在線約數百人的小規模正式上線，非大型系統規模。
- **原因**：使用者確認的實際使用情境。
- **影響範圍**：資料庫索引與避免 N+1 查詢是必要設計（見 `data-model.md` 索引建議），但不需要快取層、負載平衡或水平擴展等大型系統設計，避免過度工程化。

### 2026-07-16｜餐點庫存/售罄管理需求確定

- **決策**：`menu_items` 需有售罄狀態（`is_sold_out`），售罄時消費者不可加入購物車或下單。
- **原因**：使用者於架構待確認事項回覆中確認需要此功能。
- **影響範圍**：`data-model.md` 的 `menu_items` 表與訂單驗證規則（跨欄位規則：下單時檢查售罄狀態）。

### 2026-07-16｜餐廳帳號免審核

- **決策**：餐廳可自行註冊直接使用，不需管理員審核。
- **原因**：使用者於需求訪談階段確認，降低 MVP 複雜度。
- **影響範圍**：`restaurants.is_active` 欄位保留供管理員後續停權使用，但初始註冊流程不含審核步驟。

### 2026-07-16｜管理員帳號不得公開自助註冊

- **決策**：公開 `POST /auth/register` 僅允許消費者、餐廳與外送員；管理員帳號須由受控的內部建置流程建立，既有管理員仍使用一般登入端點取得 JWT。
- **原因**：避免匿名訪客自行取得 `admin` 角色，並在階段二管理員 API 上線前消除權限提升風險。獨立審查（agent-bridge food-delivery-phase1-review-2026-07-16，P1-1）發現此為公開端點缺陷，經 Codex 修正並由 Claude 側獨立驗證（另建 venv 跑 pytest/Ruff/mypy，22 passed）。
- **實作**：`backend/schemas/auth.py` 的 `field_validator` 拒絕 `role=admin` 且 `backend/routers/auth.py` 亦有 router 層檢查（縱深防禦）；新增 `backend/seed_admin.py`，透過環境變數（`INITIAL_ADMIN_EMAIL`/`INITIAL_ADMIN_PASSWORD`/`INITIAL_ADMIN_NAME`）以 `python -m backend.seed_admin` 建立初始管理員，冪等（重複執行回傳既有帳號，不報錯），不暴露 HTTP 端點。
- **影響範圍**：`UserRegister` schema、`backend/tests/test_phase_one.py`（TC-1.2-03/04）與 `todo.md` 1.2 驗收條件皆已同步；階段二若需新增更多管理員，比照 `seed_admin.py` 模式擴充，不得開放公開註冊。

### 2026-07-16｜後端時間欄位統一使用 UTC aware datetime

- **決策**：所有後端時間欄位以 UTC 為唯一基準；SQLite 因驅動限制儲存 naive UTC，但須由集中式欄位型別在 ORM 讀回時補上 UTC 時區，PostgreSQL 則使用帶時區時間。API 的 ISO 8601 回應必須帶 `Z` 或 `+00:00`。
- **原因**：SQLite 的 `DateTime(timezone=True)` 仍可能遺失時區資訊，造成前端將 UTC 誤當本地時間，顯示相差 8 小時。
- **影響範圍**：`backend/models/types.py` 的 `UTCDateTime` 與所有模型時間欄位；前端仍保留對舊版 naive ISO 字串補 `Z` 的防禦性解析。

---

## 已知限制（截至本文件建立時）

- 一位餐廳角色使用者僅能對應一間餐廳（不支援連鎖店多分店），為 `data-model.md` 待確認事項，尚未定案。
- 餐點下架的軟刪除機制（`is_active` 欄位）尚未定案，屬待確認事項。
- 購物車是否允許混合多間餐廳的餐點尚未定案，屬待確認事項。
- 多語系支援、具體時程/預算限制、即時定位輪詢確切秒數，皆為未涵蓋範圍，暫不列入現階段設計。
