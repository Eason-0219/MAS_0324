# agents/troubleshoot_agent.py
"""
問題排解 Agent
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent, AgentResponse
from tools.troubleshoot import troubleshoot_tool


class TroubleshootAgent(BaseAgent):
    """
    問題排解 Agent
    
    負責處理作業中遇到的各種問題
    """
    
    def __init__(self):
        super().__init__(
            name="TroubleshootAgent",
            description="處理作業中的問題（螺絲掉落、工具掉落、忘記流程等）"
        )
        self.tool = troubleshoot_tool
    
    def execute(
        self,
        issue_type: str = "other",
        description: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """
        執行問題排解
        
        Args:
            issue_type: 問題類型 (forgot_sop, screw_dropped, tool_dropped, speed_issue, other)
            description: 問題描述
        
        Returns:
            AgentResponse
        """
        result = self.tool.solve(
            issue_type=issue_type,
            description=description or ""
        )
        
        return AgentResponse(
            success=result["success"],
            message=result["message"],
            data={
                "issue_type": result.get("issue_type", issue_type),
                "solution": result.get("solution"),
                "steps": result.get("steps")
            }
        )
    
    def solve_screw_dropped(self, description: str = "") -> AgentResponse:
        """快捷方法：螺絲掉落問題"""
        return self.execute(issue_type="screw_dropped", description=description)
    
    def solve_tool_dropped(self, description: str = "") -> AgentResponse:
        """快捷方法：工具掉落問題"""
        return self.execute(issue_type="tool_dropped", description=description)
    
    def solve_forgot_sop(self, description: str = "") -> AgentResponse:
        """快捷方法：忘記流程問題"""
        return self.execute(issue_type="forgot_sop", description=description)


# 全域實例
troubleshoot_agent = TroubleshootAgent()
