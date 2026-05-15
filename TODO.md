# MAS 修復與驗收 TODO

> 目標：把目前研究型原型整理成可重現、可 Demo、可移植到實驗室環境的穩定版本。

## P0 - Demo / 移植前必做

- [ ] 建立乾淨 Python 3.11 venv，不能依賴目前 Windows 版 `venv311`。
  - [ ] 在新 venv 內執行 `pip install -r requirements.txt`。
  - [ ] 確認 `python --version` 為 3.11.x。
  - [ ] 在 venv 內跑通 `python test_system.py`。
  - [ ] 在 venv 內跑通 `python test_rag_system.py`。
  - [ ] 記錄完整啟動步驟，確保可移植到實驗室主機。

- [ ] 修復前端建置環境。
  - [ ] 清理不相容的 `frontend/node_modules`。
  - [ ] 在目前平台重新執行 `npm install`。
  - [ ] 跑通 `npm run build`。
  - [ ] 確認 `frontend/src/App.jsx` 無 JSX 編譯錯誤。

- [ ] 驗證語音辨識多國語言支援。
  - [ ] 確認 STT 引擎實際載入路徑：SenseVoice 優先，Whisper fallback。
  - [ ] 驗收語言至少包含：繁體中文、英文、日文、韓文、越南文、泰文、印尼文。
  - [ ] 對每種語言準備固定測試音檔或錄音句。
  - [ ] 記錄每種語言的辨識文字、語言判斷、延遲與失敗原因。
  - [ ] 若 SenseVoice 不支援或效果不足的語言，明確指定 fallback 策略。

- [ ] 驗證文字多代理輸入輸出語言一致性。
  - [ ] Traditional Chinese in -> Traditional Chinese out。
  - [ ] English in -> English out。
  - [ ] Japanese in -> Japanese out。
  - [ ] 覆蓋路由：`chat`、`sop`、`safety`、`troubleshoot`、`robot`、`mcp`。
  - [ ] 檢查 `utils/language.py` 是否支援日文偵測與回覆保持。
  - [ ] 若目前只支援 `zh/en/vi/id`，補齊日文語言偵測與 prompt language hint。

- [ ] 修 Robot action contract。
  - [ ] 決定是否支援 `retract`。
  - [ ] 若支援，補上 `RobotAction.RETRACT`、action map、controller 執行分支、Modbus value、測試案例。
  - [ ] 若不支援，從 `TOOLS_DEFINITION`、router、help text、文件移除 `retract`。
  - [ ] 統一「散熱風扇 / 主機板 / 工件」用語，避免 tool schema、Modbus 訊息、SOP 文件互相矛盾。

- [ ] 修 RAG 索引生命週期。
  - [ ] 移除或改寫 `main.py` 結束時刪除 `data/faiss_index.pkl` 的行為。
  - [ ] 確認文件修改時會重建索引，文件未修改時會載入既有索引。
  - [ ] 文件同步說明索引是可重建快取，不是必提交資產。

- [ ] 統一真正執行路徑。
  - [ ] 決定 `agents/` 是否保留。
  - [ ] 若保留，讓 `graph/nodes.py` 調用 agents。
  - [ ] 若不保留，標註 deprecated 或移除與現行流程衝突的 agents。
  - [ ] 修正 `agents/safety_agent.py` 呼叫不存在的 `safety_query_tool.query()` 問題。

## P1 - 穩定性與部署品質

- [ ] 移除前端硬編碼 `localhost:8000`。
  - [ ] 改用 Vite env，例如 `VITE_API_BASE_URL` / `VITE_WS_BASE_URL`。
  - [ ] 支援同源部署、不同主機部署、HTTPS/WSS。

- [ ] 收斂 API 安全設定。
  - [ ] 移除 production 下的 CORS `*`。
  - [ ] 將 Neo4j 預設密碼從文件與預設設定改成必填或安全 placeholder。
  - [ ] 確認 `.env` 不會被提交或展示。

- [ ] 同步喚醒詞設定。
  - [ ] 決定正式喚醒詞是「嘿 CoinAI」或「你好」。
  - [ ] 同步 `config/settings.py`、`data/wake_config.json`、README、SDD、UI 顯示。

- [ ] 建立固定 Demo 驗收腳本。
  - [ ] 文字路由：robot / sop / safety / troubleshoot / mcp / chat。
  - [ ] RAG：SOP、安全、troubleshooting 查詢。
  - [ ] Checklist：完整 8 項流程、否定回答、姓名身高解析、profile A/B/C。
  - [ ] Robot mock：伸出、夾取、放置、速度、收回策略。
  - [ ] WebSocket：`/ws/chat`、`/ws/voice`、`/ws/wake`。
  - [ ] 語音：可選測試，避免沒有麥克風環境阻斷 CI。

## P2 - 專案整理與文件

- [ ] 外部化大型與環境產物。
  - [ ] 移除或忽略 `models/SenseVoiceSmall/model.pt`。
  - [ ] 移除或忽略 `frontend/node_modules`、`frontend/dist`、`venv311`、`__pycache__`。
  - [ ] 移除或忽略 `test_tts.mp3`、`data/faiss_index.pkl`，除非明確作為測試 fixture。
  - [ ] 補模型下載或模型路徑設定說明。

- [ ] 修復 Git repository 狀態。
  - [ ] 目前 `.git` 是空殼，`git status` 無法使用。
  - [ ] 重新初始化或恢復正確 Git metadata。
  - [ ] 補 `.gitignore`，避免大型資產與環境產物進版控。

- [ ] 更新文件。
  - [ ] README 對齊目前目錄：`mcp_servers/` 而不是舊 `mcp/`。
  - [ ] RAG 報告對齊現行 `tools/sop_query_rag.py` 純 context 檢索邏輯。
  - [ ] SDD 補上目前 API/UI/voice 實際流程。
  - [ ] SETUP 補實驗室移植流程與 venv 驗收命令。

