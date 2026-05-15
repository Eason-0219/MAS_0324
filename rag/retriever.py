# rag/retriever.py
"""
文件檢索器

提供簡單的關鍵字檢索功能
（未來可以擴展為向量檢索）
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .document_loader import DocumentLoader, Document, document_loader


@dataclass
class RetrievalResult:
    """檢索結果"""
    document: Document
    score: float
    highlights: List[str]


class SimpleRetriever:
    """
    簡單檢索器
    
    使用關鍵字匹配進行檢索
    未來可以替換為向量檢索（FAISS、Chroma 等）
    """
    
    def __init__(self, loader: DocumentLoader = None):
        self.loader = loader or document_loader
    
    def retrieve(
        self, 
        query: str, 
        top_k: int = 3,
        doc_type: Optional[str] = None
    ) -> List[RetrievalResult]:
        """
        檢索相關文件
        
        Args:
            query: 查詢字串
            top_k: 返回前 k 個結果
            doc_type: 限制文件類型 (sop, safety, troubleshooting)
        
        Returns:
            檢索結果列表
        """
        self.loader.load_all()
        
        results = []
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        for doc in self.loader.documents.values():
            # 過濾類型
            if doc_type and doc.doc_type != doc_type:
                continue
            
            # 計算分數
            score = self._calculate_score(query_terms, doc)
            
            if score > 0:
                highlights = self._extract_highlights(query_terms, doc.content)
                results.append(RetrievalResult(
                    document=doc,
                    score=score,
                    highlights=highlights
                ))
        
        # 按分數排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:top_k]
    
    def _calculate_score(self, query_terms: List[str], doc: Document) -> float:
        """計算相關性分數"""
        content_lower = doc.content.lower()
        title_lower = doc.title.lower()
        
        score = 0.0
        
        for term in query_terms:
            # 標題匹配權重較高
            if term in title_lower:
                score += 2.0
            
            # 內容匹配
            count = content_lower.count(term)
            score += count * 0.5
        
        return score
    
    def _extract_highlights(self, query_terms: List[str], content: str, window: int = 50) -> List[str]:
        """提取包含關鍵字的片段"""
        highlights = []
        content_lower = content.lower()
        
        for term in query_terms:
            pos = content_lower.find(term)
            if pos >= 0:
                start = max(0, pos - window)
                end = min(len(content), pos + len(term) + window)
                snippet = content[start:end].strip()
                if snippet not in highlights:
                    highlights.append(f"...{snippet}...")
        
        return highlights[:3]  # 最多 3 個片段
    
    def retrieve_for_sop(self, query: str, top_k: int = 3) -> List[RetrievalResult]:
        """快捷方法：檢索 SOP 文件"""
        return self.retrieve(query, top_k=top_k, doc_type="sop")
    
    def retrieve_for_safety(self, query: str, top_k: int = 3) -> List[RetrievalResult]:
        """快捷方法：檢索安全須知"""
        return self.retrieve(query, top_k=top_k, doc_type="safety")
    
    def retrieve_for_troubleshooting(self, query: str, top_k: int = 3) -> List[RetrievalResult]:
        """快捷方法：檢索問題排解"""
        return self.retrieve(query, top_k=top_k, doc_type="troubleshooting")

    # 向後兼容的方法名稱
    def search_safety(self, query: str, k: int = 3) -> List[RetrievalResult]:
        """向後兼容：檢索安全須知"""
        return self.retrieve_for_safety(query, top_k=k)

    def search_sop(self, query: str, k: int = 3) -> List[RetrievalResult]:
        """向後兼容：檢索 SOP"""
        return self.retrieve_for_sop(query, top_k=k)

    def search_troubleshooting(self, query: str, k: int = 3) -> List[RetrievalResult]:
        """向後兼容：檢索問題排解"""
        return self.retrieve_for_troubleshooting(query, top_k=k)

    def get_context_string(self, results: List[RetrievalResult]) -> str:
        """將檢索結果轉換為上下文字串"""
        if not results:
            return ""

        parts = []
        for i, result in enumerate(results, 1):
            parts.append(f"[文件 {i}] {result.document.title}")
            parts.append(result.document.content)
            if result.highlights:
                parts.append("重點：" + " | ".join(result.highlights))
            parts.append("")

        return "\n".join(parts)


# 全域實例
retriever = SimpleRetriever()
