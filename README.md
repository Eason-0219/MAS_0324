# MAS - 顯示卡組裝多代理系統

> 架構：規則路由 + GPT-5-mini + 長期記憶 + 多語言

## ✨ 功能特色

| 功能 | 說明 |
|------|------|
| 🔀 混合路由 | 規則優先 (<1ms) + GPT-5-mini 備援 |
| 🧠 長期記憶 | Neo4j 儲存用戶資訊，對話時自動注入 |
| 🌐 多語言 | 中文、English、Tiếng Việt、Bahasa |
| 🔊 語音 I/O | Whisper STT + ElevenLabs TTS |
| 📡 Modbus | 機械手臂控制（返回 Register/Value） |
| 🌤️ MCP | 時間、天氣、網路搜尋 |

## 🏗️ 系統架構

```
用戶輸入
    │
    ▼
┌─────────────┐
│  規則路由器  │ ← <1ms，處理 90% 明確指令
└──────┬──────┘
       │
  ┌────┴────┐
  │ 匹配成功 │ 無匹配
  ▼         ▼
工具執行   GPT-5-mini ← ~500ms，處理複雜問題
(本地)    (Tool Calling)
```

## 🚀 快速開始

### 1. 安裝

```bash
pip install -r requirements.txt
```

### 2. 設定 `.env`

```bash
# OpenAI (必要)
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=gpt-5-mini

# 路由策略
USE_CLOUD_LLM=true

# Neo4j (記憶體功能)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
```

### 3. 啟動 Neo4j (Docker)

```bash
docker-compose up -d
```

### 4. 執行

```bash
python main.py
```

## 🧠 記憶體功能

系統會自動：
1. **提取用戶資訊**：從對話中識別姓名、偏好
2. **保存到 Neo4j**：建立用戶節點和對話關係
3. **對話時注入**：將記憶作為上下文提供給 LLM

```
用戶：我叫小明
系統：(保存姓名到 Neo4j)

... 新對話 ...

用戶：你知道我是誰嗎？
系統：(從 Neo4j 讀取) 你是小明！
```

## 📁 專案結構

```
MAS/
├── main.py                 # 主程式
├── graph/                  # LangGraph 核心
│   ├── router.py           # 規則 + GPT-5-mini 路由
│   ├── nodes.py            # Agent 節點（記憶體注入）
│   └── workflow.py         # 工作流程
├── memory/                 # 🆕 記憶體服務
│   └── graphiti_service.py # Neo4j 長期記憶
├── tools/                  # 工具模組
├── agents/                 # Agent 封裝
├── rag/                    # RAG 檢索
├── mcp/                    # MCP 工具
├── voice/                  # 語音服務
└── utils/                  # 工具函數
```

## 💬 使用範例

### 自我介紹 + 記憶
```
👤 我叫小明，是新手
📝 識別到姓名: 小明
🤖 你好小明！我會記住你是新手...

... 之後的對話 ...

👤 你還記得我嗎？
🤖 當然記得，小明！你是新手操作員...
```

### 複合問題
```
👤 當我組裝到第8步時螺絲掉了該怎麼辦
🔀 複合問題: troubleshoot
🤖 螺絲掉落處理方案：...
```

### 機器人控制
```
👤 伸出機械手臂
📋 規則匹配: robot
🤖 ✅ 機械手臂已伸出
   [Modbus: Register=1024, Value=3]
```

## 📊 效能

| 場景 | 延遲 | 說明 |
|------|------|------|
| 規則匹配 | <1ms | 機器人控制、明確指令 |
| GPT-5-mini | ~500ms | 複雜問題、模糊意圖 |
| 記憶體讀取 | ~10ms | Neo4j 查詢 |

## 🔧 指令

| 指令 | 功能 |
|------|------|
| `quit` | 退出 |
| `stats` | 統計 |
| `status` | 機械手臂狀態 |
| `memory` | 記憶體統計 |
| `voice on/off` | 語音模式 |

## 📝 授權

MIT License
