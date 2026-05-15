# agents/sop_agent.py
"""
SOP 查詢 Agent
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent, AgentResponse
from tools.sop_query import sop_query_tool


class SOPAgent(BaseAgent):
    """
    SOP (標準作業程序) 查詢 Agent
    
    負責處理組裝流程相關的查詢
    """
    
    def __init__(self):
        super().__init__(
            name="SOPAgent",
            description="查詢顯示卡組裝的標準作業程序步驟"
        )
        self.tool = sop_query_tool
    
    def execute(
        self,
        query_type: str = "all_steps",
        step_number: Optional[int] = None,
        start_step: Optional[int] = None,
        end_step: Optional[int] = None,
        **kwargs
    ) -> AgentResponse:
        """
        執行 SOP 查詢
        
        Args:
            query_type: 查詢類型 (all_steps, single_step, step_range)
            step_number: 步驟編號 (用於 single_step)
            start_step: 起始步驟 (用於 step_range)
            end_step: 結束步驟 (用於 step_range)
        
        Returns:
            AgentResponse
        """
        result = self.tool.query(
            query_type=query_type,
            step_number=step_number,
            start_step=start_step,
            end_step=end_step
        )
        
        return AgentResponse(
            success=result["success"],
            message=result["message"],
            data={
                "query_type": query_type,
                "steps": result.get("steps"),
                "count": result.get("count")
            }
        )
    
    def get_step(self, step_number: int) -> AgentResponse:
        """快捷方法：獲取單一步驟"""
        return self.execute(query_type="single_step", step_number=step_number)
    
    def get_all_steps(self) -> AgentResponse:
        """快捷方法：獲取所有步驟"""
        return self.execute(query_type="all_steps")


# 全域實例
sop_agent = SOPAgent()
