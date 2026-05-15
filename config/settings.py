# config/settings.py
"""
MAS 系統配置
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """系統配置類"""
    
    # -------------------- Ollama 配置 (本地模型) --------------------
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API 基礎 URL"
    )
    ollama_router_model: str = Field(
        default="qwen3:0.6b",
        description="路由器模型 (快速，用於意圖分類)"
    )
    ollama_executor_model: str = Field(
        default="qwen3:8b",
        description="執行器模型 (強大，用於複雜任務)"
    )
    
    # -------------------- OpenAI/OpenRouter 配置 --------------------
    openai_api_key: str = Field(
        default="",
        description="OpenRouter API Key"
    )
    openai_model: str = Field(
        default="openai/gpt-5-mini",
        description="OpenRouter 模型名稱"
    )
    openai_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API URL"
    )
    
    # -------------------- Neo4j 配置 --------------------
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j 連接 URI"
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j 用戶名"
    )
    neo4j_password: str = Field(
        default="password123",
        description="Neo4j 密碼"
    )
    
    # -------------------- Redis 配置 --------------------
    redis_host: str = Field(
        default="localhost",
        description="Redis 主機"
    )
    redis_port: int = Field(
        default=6379,
        description="Redis 端口"
    )
    redis_db: int = Field(
        default=0,
        description="Redis 資料庫編號"
    )
    
    # -------------------- 語音配置 --------------------
    elevenlabs_api_key: str = Field(
        default="",
        description="ElevenLabs API Key"
    )
    elevenlabs_voice_id: str = Field(
        default="21m00Tcm4TlvDq8ikWAM",
        description="ElevenLabs Voice ID"
    )
    whisper_model: str = Field(
        default="base",
        description="Whisper 模型大小 (tiny, base, small, medium, large)"
    )
    
    # -------------------- Modbus 配置 --------------------
    modbus_host: str = Field(
        default="192.168.50.234",
        description="Modbus TCP 主機 IP"
    )
    modbus_port: int = Field(
        default=502,
        description="Modbus TCP 端口"
    )
    modbus_mock: bool = Field(
        default=True,
        description="是否使用 Mock Modbus (測試用)"
    )
    
    # -------------------- 語音進階配置 --------------------
    wake_word: str = Field(
        default="嘿 CoinAI",
        description="喚醒詞（支援中文）"
    )
    wake_word_check_interval: float = Field(
        default=2.0,
        description="喚醒詞偵測片段長度（秒）"
    )
    wake_word_silence_timeout: float = Field(
        default=2.0,
        description="VAD 靜音判定時間（秒）"
    )
    wake_word_max_record: float = Field(
        default=15.0,
        description="喚醒後最長錄音時間（秒）"
    )
    vad_silence_duration: float = Field(
        default=2.0,
        description="VAD 靜音判定秒數"
    )
    voice_mode_type: str = Field(
        default="single",
        description="語音模式: single=單次, continuous=持續監聽"
    )
    
    # -------------------- MCP 配置 --------------------
    openweather_api_key: str = Field(
        default="",
        description="OpenWeatherMap API Key"
    )
    
    # -------------------- Tavily 配置 (AI Search) --------------------
    tavily_api_key: str = Field(
        default="",
        description="Tavily API Key (AI 搜尋)"
    )
    
    # -------------------- 系統配置 --------------------
    log_level: str = Field(
        default="INFO",
        description="日誌等級"
    )
    debug_mode: bool = Field(
        default=True,
        description="除錯模式"
    )
    default_language: str = Field(
        default="zh-TW",
        description="預設語言"
    )
    
    # -------------------- 路徑配置 --------------------
    data_dir: str = Field(
        default="data",
        description="資料目錄"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全域配置實例
settings = Settings()


# ============================================================
# 工具定義 (供 LLM 使用)
# ============================================================

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "control_robot",
            "description": "控制機械手臂執行動作，包括伸出、收回、夾取、放置、調整速度等。當用戶要求機械手臂執行物理動作時使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["extend", "retract", "grip", "release", "adjust_speed"],
                        "description": "機械手臂動作類型: extend=伸出, retract=收回, grip=夾取, release=放置, adjust_speed=調整速度"
                    },
                    "speed": {
                        "type": "string",
                        "enum": ["slow", "medium", "fast"],
                        "description": "速度設定（僅在 adjust_speed 時使用）: slow=慢速, medium=中速, fast=快速"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_sop",
            "description": "查詢顯示卡組裝的標準作業程序（SOP）步驟。當用戶詢問組裝流程、特定步驟內容、或步驟範圍時使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["all_steps", "single_step", "step_range"],
                        "description": "查詢類型: all_steps=所有步驟, single_step=單一步驟, step_range=步驟範圍"
                    },
                    "step_number": {
                        "type": "integer",
                        "description": "步驟編號 (1-12)，用於 single_step"
                    },
                    "start_step": {
                        "type": "integer",
                        "description": "起始步驟編號，用於 step_range"
                    },
                    "end_step": {
                        "type": "integer",
                        "description": "結束步驟編號，用於 step_range"
                    }
                },
                "required": ["query_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_safety_guidelines",
            "description": "查詢作業安全須知，包括開始操作前的準備事項（pre_work），以及流程中的注意事項（in_process）。當用戶詢問安全規範、注意事項、或準備工作時使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["pre_work", "in_process", "all"],
                        "description": "類別: pre_work=開始操作前須知, in_process=流程中須知, all=全部"
                    },
                    "keyword": {
                        "type": "string",
                        "description": "關鍵字搜尋（可選），如：螺絲、機械手臂、清潔"
                    }
                },
                "required": ["category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "troubleshoot",
            "description": "處理作業中遇到的問題，如螺絲掉落、工具掉落、忘記流程等。當用戶遇到問題需要解決方案時使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "enum": ["forgot_sop", "screw_dropped", "tool_dropped", "speed_issue", "other"],
                        "description": "問題類型: forgot_sop=忘記流程, screw_dropped=螺絲掉落, tool_dropped=工具掉落, speed_issue=速度問題, other=其他"
                    },
                    "description": {
                        "type": "string",
                        "description": "問題的詳細描述"
                    }
                },
                "required": ["issue_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_query",
            "description": "查詢外部資訊，包括時間、日期、天氣、網路搜尋等。當用戶詢問現在幾點、今天日期、天氣、或要求上網搜尋最新資訊時使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["time", "date", "weather", "search"],
                        "description": "查詢類型: time=時間, date=日期, weather=天氣, search=網路搜尋"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "時區（時間查詢用），例如：Asia/Taipei, Asia/Tokyo, America/New_York, Europe/London"
                    },
                    "city": {
                        "type": "string",
                        "description": "城市名稱（天氣查詢用）"
                    },
                    "query": {
                        "type": "string",
                        "description": "搜尋關鍵字（網路搜尋用）"
                    }
                },
                "required": ["query_type"]
            }
        }
    }
]

# 簡單指令列表 (由 0.6B 直接處理)
SIMPLE_ACTIONS = {
    "control_robot": ["extend", "retract", "grip", "release", "adjust_speed"]
}

# 複雜指令列表 (需要 GPT 處理)
COMPLEX_TOOLS = ["query_sop", "query_safety_guidelines", "troubleshoot"]

# MCP 本地處理（規則命中時不再經過 GPT）
LOCAL_TOOLS = ["control_robot", "mcp_query"]
