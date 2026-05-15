# agents/base_agent.py
"""
基礎 Agent 類別
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AgentResponse:
    """Agent 回應結構"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    基礎 Agent 抽象類別
    
    所有 Agent 都需要繼承此類別並實現 execute 方法
    """
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, **kwargs) -> AgentResponse:
        """
        執行 Agent 任務
        
        Args:
            **kwargs: 任務參數
        
        Returns:
            AgentResponse: 執行結果
        """
        pass
    
    def validate_input(self, required_keys: list, **kwargs) -> Optional[str]:
        """
        驗證輸入參數
        
        Args:
            required_keys: 必要的參數名稱
            **kwargs: 輸入參數
        
        Returns:
            錯誤訊息，如果驗證通過則返回 None
        """
        missing = [k for k in required_keys if k not in kwargs]
        if missing:
            return f"缺少必要參數: {', '.join(missing)}"
        return None
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}')>"
