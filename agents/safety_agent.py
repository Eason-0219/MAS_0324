# agents/safety_agent.py
"""
安全須知查詢 Agent
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent, AgentResponse
from tools.safety_query_rag import safety_query_tool


class SafetyAgent(BaseAgent):
    """
    安全須知查詢 Agent
    
    負責處理作業安全相關的查詢
    """
    
    def __init__(self):
        super().__init__(
            name="SafetyAgent",
            description="查詢作業安全須知，包括開工前準備和流程中注意事項"
        )
        self.tool = safety_query_tool
    
    def execute(
        self,
        category: str = "pre_work",
        keyword: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """
        執行安全須知查詢
        
        Args:
            category: 類別 (pre_work, in_process, all)
            keyword: 關鍵字過濾
        
        Returns:
            AgentResponse
        """
        result = self.tool.query(category=category, keyword=keyword)
        
        return AgentResponse(
            success=result["success"],
            message=result["message"],
            data={
                "category": category,
                "keyword": keyword,
                "items": result.get("items"),
                "count": result.get("count")
            }
        )
    
    def get_pre_work(self) -> AgentResponse:
        """快捷方法：獲取開工前須知"""
        return self.execute(category="pre_work")
    
    def get_in_process(self) -> AgentResponse:
        """快捷方法：獲取流程中須知"""
        return self.execute(category="in_process")


# 全域實例
safety_agent = SafetyAgent()
