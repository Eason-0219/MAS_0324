# tools/troubleshoot.py
"""
問題排解工具 - 純 RAG 檢索
"""

from typing import Dict, Any, Optional
from rag.retriever import retriever


class TroubleshootTool:
    """
    問題排解工具

    完全透過 RAG 從 troubleshooting.md 檢索內容
    """

    def __init__(self):
        self.retriever = retriever
    
    def search(self, query: str, k: int = 3) -> Dict[str, Any]:
        """
        使用 RAG 語義搜尋問題排解
        
        Args:
            query: 查詢文字（問題描述）
            k: 返回數量
        
        Returns:
            搜尋結果（包含 context 供 LLM 使用）
        """
        # 搜尋 troubleshooting 文件
        results = self.retriever.search_troubleshooting(query, k=k)
        
        # 也搜尋 safety 文件（問題排解可能涉及安全）
        safety_results = self.retriever.search_safety(query, k=1)
        
        # 合併結果
        all_contexts = []
        if results:
            all_contexts.append(self.retriever.get_context_string(results))
        if safety_results:
            all_contexts.append(self.retriever.get_context_string(safety_results))
        
        if not all_contexts:
            return {
                "success": True,
                "message": "問題排解文件中未找到相關資訊。",
                "context": ""
            }
        
        context = "\n---\n".join(all_contexts)
        
        return {
            "success": True,
            "query": query,
            "context": context,
            "message": context
        }
    
    def solve(self, issue_type: str = "other", description: str = "") -> Dict[str, Any]:
        """
        提供問題排解建議（透過 RAG）
        
        Args:
            issue_type: 問題類型（僅供參考，實際用 description 搜尋）
            description: 問題描述
        
        Returns:
            排解建議
        """
        query = description if description else issue_type
        return self.search(query)
    
    def query(self, query_text: str, k: int = 3) -> Dict[str, Any]:
        """查詢問題排解（別名）"""
        return self.search(query_text, k=k)


# 全域實例
troubleshoot_tool = TroubleshootTool()