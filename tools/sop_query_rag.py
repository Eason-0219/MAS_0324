# tools/sop_query_rag.py
"""
SOP 查詢工具 - 簡化版 (回歸舊版邏輯)
只負責檢索 Context，不進行過度處理
"""

from typing import Dict, Any, Optional
try:
    from rag.vector_retriever import vector_retriever
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

class SOPQueryToolRAG:
    def __init__(self):
        self.rag_enabled = RAG_AVAILABLE

    def query(self, query_type: str = "semantic", user_query: str = "") -> Dict[str, Any]:
        """
        模擬舊版 SOP Agent 的檢索邏輯
        """
        if not self.rag_enabled:
            return {"success": False, "message": "RAG 未啟用"}

        try:
            # 舊版邏輯：k=3，filter={"source": "sop"}
            # 注意：這裡呼叫的是 vector_retriever，底層已經對接了 FAISS
            results = vector_retriever.retrieve_for_sop(user_query, top_k=3)
            
            if not results:
                return {
                    "success": True, 
                    "context": "SOP 文件中未找到相關資訊。",
                    "message": "查無資料"
                }

            # 舊版邏輯：直接合併 page_content
            context_str = "\n---\n".join([res.document.content for res in results])
            
            return {
                "success": True,
                "context": context_str,
                "message": context_str # 這裡的 message 只是為了向後兼容，實際使用的是 context
            }

        except Exception as e:
            return {"success": False, "context": f"搜尋 SOP 文件時發生錯誤: {e}", "message": str(e)}

sop_query_tool = SOPQueryToolRAG()