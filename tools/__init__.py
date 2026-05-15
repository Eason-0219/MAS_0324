# tools/__init__.py
from .robot_control import RobotController
from .sop_query_rag import SOPQueryToolRAG
from .safety_query_rag import SafetyQueryToolRAG
from .troubleshoot_rag import TroubleshootToolRAG

# 向後兼容（保留舊名稱）
SOPQueryTool = SOPQueryToolRAG
SafetyQueryTool = SafetyQueryToolRAG
TroubleshootTool = TroubleshootToolRAG

__all__ = [
    "RobotController",
    "SOPQueryTool",
    "SOPQueryToolRAG",
    "SafetyQueryTool",
    "SafetyQueryToolRAG",
    "TroubleshootTool",
    "TroubleshootToolRAG"
]
