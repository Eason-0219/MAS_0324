# agents/robot_agent.py
"""
機器人控制 Agent
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent, AgentResponse
from tools.robot_control import robot_controller


class RobotAgent(BaseAgent):
    """
    機器人控制 Agent
    
    負責處理所有機械手臂相關的操作
    """
    
    def __init__(self):
        super().__init__(
            name="RobotAgent",
            description="控制機械手臂執行動作（伸出、收回、夾取、放置、調整速度）"
        )
        self.controller = robot_controller
    
    def execute(self, action: str, speed: Optional[str] = None, **kwargs) -> AgentResponse:
        """
        執行機器人動作
        
        Args:
            action: 動作類型 (extend, retract, grip, release, adjust_speed)
            speed: 速度設定 (slow, medium, fast)
        
        Returns:
            AgentResponse
        """
        if not action:
            return AgentResponse(
                success=False,
                message="請指定動作類型",
                error="missing_action"
            )
        
        result = self.controller.execute(action=action, speed=speed)
        
        return AgentResponse(
            success=result["success"],
            message=result["message"],
            data={
                "action": action,
                "speed": speed,
                "state": result.get("state"),
                "modbus": result.get("modbus")
            }
        )
    
    def get_status(self) -> str:
        """獲取機械手臂狀態"""
        return self.controller.get_status()


# 全域實例
robot_agent = RobotAgent()
