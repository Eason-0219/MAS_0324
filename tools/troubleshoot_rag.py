# tools/troubleshoot_rag.py
"""
問題排解工具 - 純 RAG 檢索
使用向量相似度搜索最相關的解決方案
"""

from typing import Dict, Any

try:
    from rag.vector_retriever import vector_retriever
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("⚠️ RAG 向量檢索不可用")


class TroubleshootToolRAG:
    """
    問題排解工具（純 RAG）

    使用向量檢索從 troubleshooting.md 和 safety.md 找到最相關的解決方案
    """

    def __init__(self):
        self.rag_enabled = RAG_AVAILABLE

    def solve(self, issue_description: str, k: int = 3) -> Dict[str, Any]:
        """
        使用 RAG 搜尋問題解決方案

        Args:
            issue_description: 問題描述
            k: 返回結果數量

        Returns:
            解決方案
        """
        if not self.rag_enabled:
            return {
                "success": False,
                "message": "RAG 向量檢索不可用，無法搜尋解決方案"
            }

        try:
            # 搜尋 troubleshooting 文件
            troubleshoot_results = vector_retriever.retrieve_for_troubleshooting(issue_description, top_k=k)

            # 也搜尋 safety 文件（問題排解可能涉及安全）
            safety_results = vector_retriever.retrieve_for_safety(issue_description, top_k=1)

            # 合併結果
            all_results = []
            if troubleshoot_results:
                all_results.extend(troubleshoot_results)
            if safety_results:
                all_results.extend(safety_results)

            if not all_results:
                return {
                    "success": True,
                    "message": "❓ 未找到直接相關的解決方案。\n\n建議：\n1. 請詳細描述問題\n2. 檢查作業流程是否正確\n3. 必要時請聯絡現場主管",
                    "context": ""
                }

            # 組合解決方案
            context_parts = []
            for i, result in enumerate(all_results[:k], 1):
                context_parts.append(f"[解決方案 {i}] (相關度: {result.score:.1%})")
                context_parts.append(result.document.content)
                context_parts.append("")

            context = "\n".join(context_parts)

            # 生成友善的回應訊息
            message = f"""🔧 **找到 {len(all_results[:k])} 個相關解決方案**

{context}

💡 **建議**：請按照上述解決方案處理。如果問題仍未解決，請聯絡現場主管。"""

            return {
                "success": True,
                "issue": issue_description,
                "solutions_count": len(all_results[:k]),
                "top_relevance": all_results[0].score if all_results else 0,
                "context": context,
                "message": message
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"⚠️ 搜尋解決方案時發生錯誤: {e}"
            }

    def search_by_category(self, category: str, k: int = 3) -> Dict[str, Any]:
        """
        按類別搜尋問題

        Args:
            category: 問題類別（forgot_sop, screw_dropped, tool_dropped, speed_issue, other）
            k: 返回結果數量

        Returns:
            解決方案
        """
        # 類別對應的查詢文字
        category_queries = {
            "forgot_sop": "忘記作業流程步驟",
            "screw_dropped": "螺絲掉落怎麼辦",
            "tool_dropped": "工具掉落怎麼辦",
            "speed_issue": "機械手臂速度問題",
            "other": "一般作業問題"
        }

        query = category_queries.get(category, category)
        return self.solve(query, k=k)


# 全域實例
troubleshoot_tool = TroubleshootToolRAG()
