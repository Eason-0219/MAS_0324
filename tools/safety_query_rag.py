# tools/safety_query_rag.py
"""
安全須知查詢工具 - RAG + 進產線核對清單
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

try:
    from rag.vector_retriever import vector_retriever
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("⚠️ RAG 向量檢索不可用")


class ChecklistState(Enum):
    """核對清單狀態"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ChecklistItem:
    """核對清單項目"""
    id: int
    content: str
    checked: bool = False


class SafetyQueryToolRAG:
    """
    安全須知查詢工具（RAG + 核對清單）

    功能：
    1. RAG 語義搜索安全須知
    2. 進產線核對清單（8個檢查項目）
    """

    # 進產線檢查清單（8個須知）
    ENTRY_CHECKLIST = [
        ChecklistItem(1, "確認個人裝備整齊：穿好工作服，戴好帽子，確保穿著合適，不影響操作"),
        ChecklistItem(2, "手部清潔：作業前必須洗手或擦拭乾淨，避免污漬或油脂污染零件"),
        ChecklistItem(3, "工具點檢：確認螺絲起子、電動工具等作業工具齊全，外觀完好無異常"),
        ChecklistItem(4, "機械手臂設定檢查：確認機械手臂設定正確，符合作業需求"),
        ChecklistItem(5, "置物台整理：清理置物台面，確保有足夠空間放置鎖付後的主機板"),
        ChecklistItem(6, "作業區檢查：檢查周圍地面是否乾淨、無障礙物，保持走道暢通"),
        ChecklistItem(7, "身體狀況自我檢查：確認身體狀況良好，無不適感影響作業穩定性"),
        ChecklistItem(8, "作業流程複習：快速瀏覽作業流程，掌握重點步驟與注意事項"),
    ]

    def __init__(self):
        self.rag_enabled = RAG_AVAILABLE

        # 核對清單狀態管理
        self.checklist_state = ChecklistState.NOT_STARTED
        self.current_checklist: List[ChecklistItem] = []
        self.current_item_index = 0

    # ============================================================
    # RAG 語義搜索
    # ============================================================

    def search(self, query: str, k: int = 3) -> Dict[str, Any]:
        """
        使用 RAG 語義搜尋安全須知

        Args:
            query: 查詢文字
            k: 返回數量

        Returns:
            搜尋結果
        """
        if not self.rag_enabled:
            return {
                "success": False,
                "message": "RAG 向量檢索不可用"
            }

        try:
            results = vector_retriever.retrieve_for_safety(query, top_k=k)

            if not results:
                return {
                    "success": True,
                    "message": "安全文件中未找到相關資訊。",
                    "context": ""
                }

            context = vector_retriever.get_context_string(results)

            return {
                "success": True,
                "query": query,
                "results_count": len(results),
                "context": context,
                "message": context
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"搜尋失敗: {e}"
            }

    # ============================================================
    # 進產線核對清單
    # ============================================================

    def start_entry_checklist(self) -> Dict[str, Any]:
        """
        開始進產線核對清單

        Returns:
            第一個檢查項目
        """
        # 重置狀態
        self.checklist_state = ChecklistState.IN_PROGRESS
        self.current_checklist = [
            ChecklistItem(item.id, item.content, False)
            for item in self.ENTRY_CHECKLIST
        ]
        self.current_item_index = 0

        return self._get_current_item_message()

    def process_checklist_response(self, response: str) -> Dict[str, Any]:
        """
        處理用戶對檢查項目的回應

        Args:
            response: 用戶回應（"是"/"否"/"完成"/"取消"）

        Returns:
            下一個項目或完成訊息
        """
        if self.checklist_state != ChecklistState.IN_PROGRESS:
            return {
                "success": False,
                "message": "目前沒有進行中的核對清單。請先說「我要進產線了」開始核對。",
                "checklist_active": False # 確保狀態同步
            }

        # 解析回應
        validation = self._validate_response(response)

        if not validation["valid"]:
            return {
                "success": False,
                "needs_retry": True,
                "message": "請回答「是」或「否」。",
                "checklist_active": True, # 保持激活
                "current_checklist_index": self.current_item_index
            }

        confirmed = validation["confirmed"]

        if confirmed is None:
            # 取消核對
            self.checklist_state = ChecklistState.CANCELLED
            return {
                "success": True,
                "cancelled": True,
                "checklist_active": False, # 取消後關閉狀態
                "message": "❌ 核對清單已取消。請確認完成所有準備後再次進入產線。"
            }

        # 記錄當前項目
        current_item = self.current_checklist[self.current_item_index]
        current_item.checked = confirmed

        if not confirmed:
            # 用戶回答「否」
            # 🔴 關鍵修正：這裡必須回傳 active=True 和 index，否則狀態會斷掉
            return {
                "success": True,
                "incomplete_item": current_item.id,
                "checklist_active": True,  # 保持鎖定狀態！
                "current_checklist_index": self.current_item_index, # 保持當前索引
                "message": f"⚠️ **未完成項目 {current_item.id}**\n\n{current_item.content}\n\n請完成此項目後再繼續 (完成請回答「是」)。"
            }

        # 用戶回答「是」，移動到下一項
        self.current_item_index += 1

        # 檢查是否全部完成
        if self.current_item_index >= len(self.current_checklist):
            return self._complete_checklist()

        # 返回下一個項目
        return self._get_current_item_message()
    

    def _get_current_item_message(self) -> Dict[str, Any]:
        """獲取當前檢查項目的訊息"""
        if self.current_item_index >= len(self.current_checklist):
            return self._complete_checklist()

        current_item = self.current_checklist[self.current_item_index]
        progress = f"({self.current_item_index + 1}/{len(self.current_checklist)})"

        message = f"""📋 **進產線前安全檢查 {progress}**

**檢查項目 {current_item.id}**：
{current_item.content}

請確認是否完成？（回答「是」或「否」）"""

        return {
            "success": True,
            "checklist_active": True,
            "current_item_index": self.current_item_index,
            "total_items": len(self.current_checklist),
            "current_item": {
                "id": current_item.id,
                "content": current_item.content
            },
            "message": message
        }

    def _complete_checklist(self) -> Dict[str, Any]:
        """完成核對清單"""
        self.checklist_state = ChecklistState.COMPLETED

        # 統計
        checked_count = sum(1 for item in self.current_checklist if item.checked)
        all_passed = checked_count == len(self.current_checklist)

        if all_passed:
            message = f"""✅ **進產線前安全檢查完成！**

您已完成所有 {len(self.current_checklist)} 項安全檢查。

為確保機械手臂參數正確設定，請提供您的姓名與身高。
例如：「我是王小明，身高175公分」"""
        else:
            message = f"""⚠️ **部分檢查未通過**

完成項目：{checked_count}/{len(self.current_checklist)}

請確保所有安全準備完成後再進入產線。"""

        return {
            "success": True,
            "checklist_completed": True,
            "checklist_active": False,
            "awaiting_name_height": all_passed,
            "all_passed": all_passed,
            "checked_count": checked_count,
            "total_count": len(self.current_checklist),
            "message": message
        }

    def _validate_response(self, response: str) -> Dict[str, Any]:
        """
        驗證用戶對檢查項目的回應

        Args:
            response: 用戶回應

        Returns:
            驗證結果 {"valid": bool, "confirmed": bool|None}
        """
        response_lower = response.lower().strip()

        affirmative = ["yes", "是", "對", "完成", "ok", "y", "好", "確認", "done", "好了", "有", "確定"]
        negative = ["no", "否", "還沒", "未", "n", "沒", "不", "沒有", "未完成"]
        cancel = ["取消", "cancel", "停止", "stop", "退出", "quit"]

        if any(word in response_lower for word in cancel):
            return {"valid": True, "confirmed": None}

        is_yes = any(aff in response_lower for aff in affirmative)
        is_no = any(neg in response_lower for neg in negative)

        if is_yes and not is_no:
            return {"valid": True, "confirmed": True}
        elif is_no and not is_yes:
            return {"valid": True, "confirmed": False}
        else:
            return {"valid": False, "confirmed": None}

    def get_checklist_status(self) -> Dict[str, Any]:
        """獲取核對清單狀態"""
        return {
            "state": self.checklist_state.value,
            "current_index": self.current_item_index if self.checklist_state == ChecklistState.IN_PROGRESS else None,
            "total_items": len(self.current_checklist) if self.current_checklist else len(self.ENTRY_CHECKLIST),
            "is_active": self.checklist_state == ChecklistState.IN_PROGRESS
        }

    def reset_checklist(self):
        """重置核對清單"""
        self.checklist_state = ChecklistState.NOT_STARTED
        self.current_checklist = []
        self.current_item_index = 0

    def parse_name_height(self, text: str) -> Dict[str, Any]:
        """從文字中解析姓名和身高"""
        import re
        
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
        ]
        
        height = None
        for pattern in height_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    height = float(match.group(1))
                    if 100 <= height <= 250:
                        break
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
            result["message"] = "無法識別。請依照格式：「我是王小明，身高175公分」"
        
        return result


# 全域實例
safety_query_tool = SafetyQueryToolRAG()
