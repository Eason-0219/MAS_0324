# MAS 專案環境安裝指南

## 系統需求

- Windows 10/11 (64-bit)
- Python 3.11（必須，3.13 有套件相容性問題）
- Node.js 18+（前端用）
- Ollama（本地 LLM 路由器）

---

## Step 1 — 安裝 Python 3.11

用 winget 從終端直接安裝，不需要手動下載：

```powershell
winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
```

確認安裝成功：

```powershell
py -3.11 --version
# 應顯示 Python 3.11.x
```

---

## Step 2 — 建立虛擬環境

在專案根目錄執行：

```powershell
py -3.11 -m venv venv311
```

---

## Step 3 — 安裝 Python 套件

```powershell
# 升級 pip
.\venv311\Scripts\pip.exe install --upgrade pip

# 安裝 PyTorch（CPU 版，不需要 GPU）
.\venv311\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 安裝 SenseVoice STT 引擎
.\venv311\Scripts\pip.exe install funasr modelscope

# 安裝專案其他相依套件
.\venv311\Scripts\pip.exe install -r requirements.txt
```

> 注意：torch 約 114MB，funasr 相依套件較多，首次安裝需要幾分鐘。

---

## Step 4 — 下載 SenseVoice 模型

從 HuggingFace 下載到本地（約 944MB），避免 ModelScope SSL 問題：

```powershell
.\venv311\Scripts\pip.exe install huggingface_hub
.\venv311\Scripts\python.exe -c "
from huggingface_hub import snapshot_download
path = snapshot_download(repo_id='FunAudioLLM/SenseVoiceSmall', local_dir='./models/SenseVoiceSmall')
print('下載完成:', path)
"
```

模型會存放在 `models/SenseVoiceSmall/`，系統啟動時自動從此路徑載入。

---

## Step 5 — 安裝前端套件

```powershell
cd frontend
npm install
npm run build
```

---

## Step 6 — 設定 .env

複製 `.env` 範本並填入 API Key：

```
OPENAI_API_KEY=sk-or-v1-...        # OpenRouter API Key
OPENAI_MODEL=openai/gpt-5-mini
OPENAI_BASE_URL=https://openrouter.ai/api/v1

OLLAMA_ROUTER_MODEL=qwen3:0.6b     # 需先用 ollama pull qwen3:0.6b

TAVILY_API_KEY=tvly-...            # Tavily 搜尋 API Key
OPENWEATHER_API_KEY=...            # OpenWeatherMap API Key
ELEVENLABS_API_KEY=...             # ElevenLabs（可選，免費版有限制）
```

---

## Step 7 — 安裝 Ollama 並下載路由模型

```powershell
# 安裝 Ollama
winget install Ollama.Ollama

# 下載路由器模型
ollama pull qwen3:0.6b
```

---

## 啟動專案

```powershell
# 啟動後端（使用虛擬環境）
.\venv311\Scripts\python.exe main.py

# 或直接執行 bat（需先修改 bat 內的 python 路徑）
start_web.bat
```

---

## 常見問題

### editdistance 在 Python 3.13 編譯失敗

這是已知問題，Python 3.13 上 `editdistance` 沒有預編譯 wheel。
解法：使用 Python 3.11 虛擬環境（如本指南所述）。

### SenseVoice 下載很慢

模型從中國 ModelScope 伺服器下載，速度視網路而定。
下載一次後會快取，之後啟動不需重新下載。

### ElevenLabs TTS 回傳 402

免費帳號無法透過 API 使用 Voice Library 的聲音。
系統已自動降級使用 Edge TTS（微軟免費 TTS），無需額外設定。
