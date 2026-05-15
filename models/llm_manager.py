# models/llm_manager.py
"""
LLM 管理器 - 混合模型策略
- Qwen3-0.6B: 快速路由器，處理簡單指令
- Qwen3-8B: 強力執行器，處理複雜任務
"""

import ollama
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from config.settings import settings, TOOLS_DEFINITION, SIMPLE_ACTIONS, COMPLEX_TOOLS


@dataclass
class LLMResponse:
    """LLM 回應資料結構"""
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    model_used: str = ""
    latency_ms: float = 0.0
    is_tool_call: bool = False


@dataclass
class LatencyStats:
    """延遲統計"""
    total_requests: int = 0
    total_latency: float = 0.0
    router_requests: int = 0
    router_latency: float = 0.0
    executor_requests: int = 0
    executor_latency: float = 0.0
    
    def add_router_request(self, latency: float):
        self.total_requests += 1
        self.total_latency += latency
        self.router_requests += 1
        self.router_latency += latency
    
    def add_executor_request(self, latency: float):
        self.total_requests += 1
        self.total_latency += latency
        self.executor_requests += 1
        self.executor_latency += latency
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "avg_latency_ms": self.total_latency / self.total_requests if self.total_requests > 0 else 0,
            "router": {
                "requests": self.router_requests,
                "avg_latency_ms": self.router_latency / self.router_requests if self.router_requests > 0 else 0
            },
            "executor": {
                "requests": self.executor_requests,
                "avg_latency_ms": self.executor_latency / self.executor_requests if self.executor_requests > 0 else 0
            }
        }


class LLMManager:
    """
    LLM 管理器 - 實現混合模型策略
    
    策略：
    1. 所有請求先經過 Router (0.6B) 進行意圖分類
    2. 簡單指令 (如機器人控制) 由 Router 直接處理
    3. 複雜指令 (如 RAG 查詢) 轉交 Executor (8B) 處理
    """
    
    def __init__(self):
        self.router_model = settings.ollama_router_model
        self.executor_model = settings.ollama_executor_model
        self.base_url = settings.ollama_base_url
        self.stats = LatencyStats()
        
        # 系統提示詞
        self.system_prompt = """你是一個顯示卡組裝產線的智慧助手。你可以使用以下工具來幫助操作員：

1. control_robot: 控制機械手臂執行動作（伸出、收回、夾取、放置、調整速度）
2. query_sop: 查詢標準作業程序（SOP）步驟
3. query_safety_guidelines: 查詢作業安全須知
4. troubleshoot: 處理作業中遇到的問題

根據操作員的需求，選擇適當的工具。如果是一般對話（如打招呼、詢問功能），直接回答即可，不需要使用工具。

重要規則：
- 使用繁體中文回答
- 回答要簡潔明瞭
- 涉及安全問題時要謹慎處理
- 機器人控制指令要確認動作類型"""
    
    def _call_ollama(
        self, 
        model: str, 
        user_input: str,
        use_tools: bool = True
    ) -> Tuple[Any, float]:
        """呼叫 Ollama API"""
        start_time = time.perf_counter()
        
        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_input}
            ],
            "options": {"temperature": 0}
        }
        
        if use_tools:
            kwargs["tools"] = TOOLS_DEFINITION
        
        response = ollama.chat(**kwargs)
        latency = (time.perf_counter() - start_time) * 1000
        
        return response, latency
    
    def _parse_response(self, response: Any, model: str, latency: float) -> LLMResponse:
        """解析 Ollama 回應"""
        result = LLMResponse(
            model_used=model,
            latency_ms=latency
        )
        
        if response.message.tool_calls:
            tool_call = response.message.tool_calls[0]
            result.is_tool_call = True
            result.tool_name = tool_call.function.name
            result.tool_args = tool_call.function.arguments
        else:
            result.content = response.message.content
        
        return result
    
    def _is_simple_action(self, tool_name: str, tool_args: Dict[str, Any]) -> bool:
        """判斷是否為簡單動作（可由 Router 直接處理）"""
        if tool_name in SIMPLE_ACTIONS:
            action = tool_args.get("action", "")
            return action in SIMPLE_ACTIONS[tool_name]
        return False
    
    def process(self, user_input: str, debug: bool = False) -> LLMResponse:
        """
        處理用戶輸入 - 混合模型策略
        
        流程：
        1. Router (0.6B) 先進行意圖分類
        2. 如果是簡單指令，直接返回結果
        3. 如果是複雜指令，交給 Executor (8B) 處理
        """
        
        # Step 1: Router 進行意圖分類
        if debug:
            print(f"\n🔀 [Router] 使用 {self.router_model} 分析意圖...")
        
        router_response, router_latency = self._call_ollama(
            model=self.router_model,
            user_input=user_input,
            use_tools=True
        )
        router_result = self._parse_response(router_response, self.router_model, router_latency)
        self.stats.add_router_request(router_latency)
        
        if debug:
            print(f"   ⏱️  Router 延遲: {router_latency:.1f}ms")
            if router_result.is_tool_call:
                print(f"   🔧 識別工具: {router_result.tool_name}")
                print(f"   📋 參數: {router_result.tool_args}")
        
        # Step 2: 判斷是否需要 Executor
        if not router_result.is_tool_call:
            # 一般對話，Router 直接處理
            if debug:
                print(f"   ✅ 一般對話，Router 直接回應")
            return router_result
        
        if self._is_simple_action(router_result.tool_name, router_result.tool_args):
            # 簡單動作，Router 直接處理
            if debug:
                print(f"   ✅ 簡單指令，Router 直接處理")
            return router_result
        
        # Step 3: 複雜指令，交給 Executor
        if debug:
            print(f"\n🚀 [Executor] 複雜任務，使用 {self.executor_model} 處理...")
        
        executor_response, executor_latency = self._call_ollama(
            model=self.executor_model,
            user_input=user_input,
            use_tools=True
        )
        executor_result = self._parse_response(executor_response, self.executor_model, executor_latency)
        self.stats.add_executor_request(executor_latency)
        
        if debug:
            print(f"   ⏱️  Executor 延遲: {executor_latency:.1f}ms")
            print(f"   📊 總延遲: {router_latency + executor_latency:.1f}ms")
        
        # 更新總延遲（Router + Executor）
        executor_result.latency_ms = router_latency + executor_latency
        
        return executor_result
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取延遲統計"""
        return self.stats.get_summary()
    
    def reset_stats(self):
        """重置統計"""
        self.stats = LatencyStats()


# 全域 LLM 管理器實例
llm_manager = LLMManager()
