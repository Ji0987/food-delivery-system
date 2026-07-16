# CLAUDE.md｜餐點外送系統

本專案的開發與協作規範統一維護於 [AGENTS.md](AGENTS.md)，請先閱讀該檔案。

Claude Code 在本專案中應遵循 `AGENTS.md` 的全部規範（技術棧、目錄結構、程式風格、commit 規範、機密資訊管理、禁止事項）。本檔案不重複內容，僅作為 Claude Code 的進入點指引。

補充：本專案另設有 `/doc/project-memory.md` 記錄長期決策異動，以及 `.claude/skills/` 下的專案 skill 鏈（`requirements-interview` → `architecture-design` → `data-model-design` → `dev-standards` → `test-plan`，另有 `vibe-debug-coach`）。修改需求、架構或資料模型層級的決策時，應透過對應 skill 更新 `/doc/` 下的文件，而非只改程式碼。
