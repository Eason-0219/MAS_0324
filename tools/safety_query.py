# tools/safety_query.py
"""
安全須知查詢工具 - 純 RAG 檢索
包含「進產線」安全檢查清單功能（從 RAG 提取）
"""

import re
from typing import Dict, Any, Optional, List
from rag.retriever import retriever


class SafetyQueryTool:
    """
    安全須知查詢工具

    完全透過 RAG 從 safety.md 檢索內容
    Checklist 項目也從 RAG 動態提取
    """

    def __init__(self):
        self.retriever = retriever
        self._checklist_items: Optional[List[str]] = None
    
    def search(self, query: str, k: int = 3) -> Dict[str, Any]:
        """
        使用 RAG 語義搜尋安全須知
        
        Args:
            query: 查詢文字
            k: 返回數量
        
        Returns:
            搜尋結果（包含 context 供 LLM 使用）
        """
        results = self.retriever.search_safety(query, k=k)
        
        if not results:
            return {
                "success": True,
                "message": "安全文件中未找到相關資訊。",
                "context": ""
            }
        
        context = self.retriever.get_context_string(results)
        
        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "context": context,
            "message": context
        }
    
    def query(self, query_text: str, k: int = 3) -> Dict[str, Any]:
        """查詢安全須知（別名）"""
        return self.search(query_text, k=k)
    
    def get_checklist_items(self) -> List[str]:
        """
        從 RAG 動態提取安全檢查清單項目
        
        Returns:
            檢查項目列表
        """
        if self._checklist_items:
            return self._checklist_items
        
        # 從 RAG 搜尋「操作前作業要求」相關內容
        results = self.retriever.search_safety("開始操作前作業要求須知", k=2)
        
        if not results:
            # 備用：嘗試其他關鍵字
            results = self.retriever.search_safety("作業前檢查", k=2)
        
        if results:
            # 合併所有結果的內容
            all_content = "\n".join([r.content for r in results])
            items = self._parse_checklist_items(all_content)
            
            if items:
                self._checklist_items = items
                return items
        
        # 如果 RAG 無法提取，返回空列表（讓系統知道需要處理）
        return []
    
    def _parse_checklist_items(self, text: str) -> List[str]:
        """
        從文字中解析檢查項目
        
        Args:
            text: RAG 檢索到的原始文字
        
        Returns:
            檢查項目列表
        """
        items = []
        
        # 嘗試多種格式匹配
        patterns = [
            r"^\s*(\d+)\.\s*(.+?)\s*$",      # 1. xxx
            r"^\s*[-•]\s*(.+?)\s*$",          # - xxx 或 • xxx
            r"^\s*\d+\)\s*(.+?)\s*$",         # 1) xxx
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        item = match[-1].strip()
                    else:
                        item = match.strip()
                    
                    # 過濾太短或無意義的項目
                    if item and len(item) > 3 and item not in items:
                        items.append(item)
        
        return items
    
    def validate_checklist_response(self, response: str) -> Dict[str, Any]:
        """
        驗證用戶對檢查項目的回應
        
        Args:
            response: 用戶回應
        
        Returns:
            驗證結果 {"valid": bool, "confirmed": bool|None}
        """
        response_lower = response.lower().strip()
        
        affirmative = ["yes", "是", "對", "完成", "ok", "y", "好", "確認", "done", "好了", "有"]
        negative = ["no", "否", "還沒", "未", "n", "沒", "不", "沒有"]
        
        is_yes = any(aff in response_lower for aff in affirmative)
        is_no = any(neg in response_lower for neg in negative)
        
        if is_yes and not is_no:
            return {"valid": True, "confirmed": True}
        elif is_no and not is_yes:
            return {"valid": True, "confirmed": False}
        else:
            return {"valid": False, "confirmed": None}
    
    def parse_name_height(self, text: str) -> Dict[str, Any]:
        """
        從文字中解析姓名和身高
        
        Args:
            text: 用戶輸入（例如「我是林小明，身高168公分」）
        
        Returns:
            解析結果
        """
        result = {
            "success": False,
            "name": None,
            "height": None,
            "message": ""
        }
        
        # 匹配姓名
        name_patterns = [
            r"我是([^\s，,。、]+)",
            r"我叫([^\s，,。、]+)",
            r"姓名[：:]\s*([^\s，,。、]+)",
            r"名字[：:]\s*([^\s，,。、]+)",
        ]
        
        name = None
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                break
        
        # 匹配身高
        height_patterns = [
            r"身高\s*[：:]?\s*(\d{2,3})",
            r"(\d{2,3})\s*(公分|cm|CM)",
            r"(\d{2,3})\s*高",
        ]
        
        height = None
        for pattern in height_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    height = float(match.group(1))
                    if 100 <= height <= 250:
                        break
                    else:
                        height = None
                except ValueError:
                    continue
        
        if name and height:
            result["success"] = True
            result["name"] = name
            result["height"] = height
            result["message"] = f"已識別：{name}，身高 {height} 公分"
        elif name:
            result["message"] = "已識別姓名，但未能識別身高。請提供身高（公分）。"
        elif height:
            result["message"] = "已識別身高，但未能識別姓名。請提供姓名。"
        else:
            result["message"] = "無法識別姓名和身高。請依照格式提供，例如：「我是林小明，身高168公分」"
        
        return result


# 全域實例
safety_query_tool = SafetyQueryTool()