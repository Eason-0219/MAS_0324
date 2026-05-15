# graph/state.py
"""
LangGraph 狀態定義
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal


class MASState(TypedDict, total=False):
    """MAS 系統狀態"""
    # ==================== 輸入 ====================
    user_input: str
    detected_language: str              # 偵測到的語言 (zh, en, vi, id)
    
    # ==================== 路由結果 ====================
    route_decision: str
    intent_confidence: float
    matched_keywords: List[str]
    needs_gpt: bool                      # 是否需要 GPT 處理
    
    # ==================== 工具呼叫 ====================
    tool_name: Optional[str]
    tool_args: Optional[Dict[str, Any]]
    tool_result: Optional[str]
    
    # ==================== Agent 結果 ====================
    agent_response: str
    model_used: str
    next_agent: Optional[str]            # 下一個要執行的 Agent
    redirect_reason: Optional[str]       # 二次路由原因（子 Agent 標記）
    
    # ==================== Modbus 結果 ====================
    modbus_result: Optional[Dict[str, Any]]
    
    # ==================== 確認流程 ====================
    needs_confirmation: bool
    confirmation_message: str
    user_confirmed: Optional[bool]
    
    # ==================== 對話歷史 ====================
    conversation_history: List[Dict[str, str]]
    current_step: Optional[int]
    
    # ==================== 操作員資訊（人因工程）====================
    operator_name: Optional[str]         # 操作員姓名
    operator_height: Optional[float]     # 操作員身高 (cm)
    height_profile: Optional[str]        # 身高設定檔 (A/B/C)
    
    # ==================== Safety Checklist ====================
    checklist_active: bool               # 是否正在進行安全檢查
    checklist_items: Optional[List[str]] # 檢查項目列表
    current_checklist_index: int         # 當前檢查項目索引
    checklist_completed: bool            # 檢查清單是否完成
    awaiting_name_height: bool           # 是否等待姓名身高輸入
    
    # ==================== 元數據 ====================
    start_time: float
    end_time: float
    latency_ms: float
    error: Optional[str]


# 路由類型
RouteType = Literal["chat", "sop", "safety", "robot", "troubleshoot", "mcp"]

# 節點名稱
NodeName = Literal[
    "hybrid_router",
    "chat_agent", 
    "sop_agent",
    "safety_agent", 
    "robot_agent",
    "robot_agent_A",
    "robot_agent_B", 
    "robot_agent_C",
    "troubleshoot_agent",
    "mcp_agent",
    "confirmation_node",
    "response_formatter"
]

# 身高設定檔
HEIGHT_PROFILES = {
    "A": {"min_height": 180, "description": "高個子 (>180cm)"},
    "B": {"min_height": 170, "max_height": 180, "description": "中等身高 (170-180cm)"},
    "C": {"max_height": 170, "description": "較矮 (<170cm)"},
}


def get_height_profile(height: float) -> str:
    """根據身高取得設定檔"""
    if height > 180:
        return "A"
    elif height >= 170:
        return "B"
    else:
        return "C"