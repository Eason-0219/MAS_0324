# rag/__init__.py
"""
RAG (Retrieval-Augmented Generation) 模組

提供 FAISS 向量檢索和知識增強功能
"""

from .retriever import SimpleRetriever, RetrievalResult, retriever
from .vector_retriever import FAISSVectorRetriever, VectorRetrievalResult, vector_retriever

__all__ = [
    "SimpleRetriever",
    "RetrievalResult",
    "retriever",
    "FAISSVectorRetriever",
    "VectorRetrievalResult",
    "vector_retriever"
]