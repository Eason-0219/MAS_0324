# rag/vector_retriever.py
"""
FAISS 向量檢索器 - 智慧雜湊版
自動偵測文件變更，只有在文件修改時才重建索引
"""

import os
import pickle
import hashlib  # <--- 新增
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("⚠️ faiss-cpu 未安裝，向量檢索不可用")

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("⚠️ ollama 未安裝，向量檢索不可用")

from .document_loader import DocumentLoader, Document, document_loader


@dataclass
class VectorRetrievalResult:
    """向量檢索結果"""
    document: Document
    score: float  # 相似度分數（距離的倒數）
    distance: float  # 原始距離


class FAISSVectorRetriever:
    """
    FAISS 向量檢索器

    使用 Ollama BGE-M3 生成文檔嵌入
    使用 FAISS 進行快速相似度搜索
    """

    def __init__(
        self,
        loader: DocumentLoader = None,
        embedding_model: str = "bge-m3",
        index_path: str = None
    ):
        self.loader = loader or document_loader
        self.embedding_model = embedding_model
        # 永遠相對於這個檔案的位置
        _base = Path(__file__).parent.parent
        self.index_path = index_path or str(_base / "data" / "faiss_index.pkl")

        self.index = None  # FAISS index
        self.doc_ids = []  # 文檔 ID 列表（與 index 對應）
        self.embeddings_cache = {}  # 嵌入緩存
        self.file_hash = "" # <--- 新增：儲存文件雜湊值

        # 檢查可用性
        if not FAISS_AVAILABLE or not OLLAMA_AVAILABLE:
            print("⚠️ FAISS 或 Ollama 不可用，向量檢索功能受限")
            return

        # 智慧載入邏輯
        current_hash = self._calculate_doc_hash()
        
        if os.path.exists(self.index_path):
            loaded_hash = self.load_index()
            if loaded_hash != current_hash:
                print("🔄 檢測到文件變更，正在重建索引...")
                self.build_index()
            else:
                print("✅ 索引已載入且為最新版本")
                # 關鍵修復：載入索引後也要載入文件到記憶體
                # 否則 retrieve() 中 self.loader.documents 為空 → 找不到任何文件
                self.loader.load_all()
        else:
            self.build_index()


    def _calculate_doc_hash(self) -> str:
        """計算 data 目錄下所有 md 文件的 MD5 雜湊值"""
        hash_md5 = hashlib.md5()
        data_dir = Path(__file__).parent.parent / "data"
        # 排序確保順序一致
        files = sorted(list(data_dir.glob("*.md")))
        
        for file_path in files:
            try:
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
            except Exception:
                pass
        return hash_md5.hexdigest()

    def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        使用 Ollama BGE-M3 生成文本嵌入

        Args:
            text: 輸入文本

        Returns:
            嵌入向量（1024 維）
        """
        if not OLLAMA_AVAILABLE:
            return None

        try:
            response = ollama.embeddings(
                model=self.embedding_model,
                prompt=text
            )

            embedding = np.array(response["embedding"], dtype=np.float32)
            return embedding

        except Exception as e:
            print(f"⚠️ 生成嵌入失敗: {e}")
            return None

    def build_index(self):
        """構建 FAISS 索引"""
        if not FAISS_AVAILABLE or not OLLAMA_AVAILABLE:
            print("⚠️ 無法構建索引：FAISS 或 Ollama 不可用")
            return

        print("🔨 正在構建 FAISS 向量索引...")

        # 載入所有文檔
        self.loader.load_all()

        if not self.loader.documents:
            print("⚠️ 沒有文檔可索引")
            return

        # 生成所有文檔的嵌入
        embeddings = []
        self.doc_ids = []

        for doc_id, doc in self.loader.documents.items():
            # 組合標題和內容作為文本
            text = f"{doc.title}\n\n{doc.content}"

            embedding = self.get_embedding(text)
            if embedding is not None:
                embeddings.append(embedding)
                self.doc_ids.append(doc_id)
                self.embeddings_cache[doc_id] = embedding

        if not embeddings:
            print("⚠️ 沒有成功生成嵌入")
            return

        # 創建 FAISS 索引
        embeddings_matrix = np.vstack(embeddings)
        dimension = embeddings_matrix.shape[1]

        # 使用 IndexFlatL2 (L2 距離)
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings_matrix)

        print(f"✅ 索引構建完成：{len(self.doc_ids)} 個文檔，{dimension} 維向量")

        # 記得在 build_index 最後更新 hash
        self.file_hash = self._calculate_doc_hash()
        self.save_index()

    def save_index(self):
        if self.index is None: return
        try:
            Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
            data = {
                "index": faiss.serialize_index(self.index),
                "doc_ids": self.doc_ids,
                "embeddings_cache": self.embeddings_cache,
                "file_hash": self.file_hash # <--- 儲存雜湊值
            }
            with open(self.index_path, "wb") as f:
                pickle.dump(data, f)
            print(f"✅ 索引已保存 (Hash: {self.file_hash[:8]})")
        except Exception as e:
            print(f"⚠️ 保存索引失敗: {e}")

    def load_index(self) -> str:
        """載入索引並回傳儲存的雜湊值"""
        try:
            with open(self.index_path, "rb") as f:
                data = pickle.load(f)

            self.index = faiss.deserialize_index(data["index"])
            self.doc_ids = data["doc_ids"]
            self.embeddings_cache = data.get("embeddings_cache", {})
            # 回傳儲存的 Hash，如果沒有則回傳空字串
            return data.get("file_hash", "")

        except Exception as e:
            print(f"⚠️ 載入索引失敗: {e}")
            return ""

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        doc_type: Optional[str] = None
    ) -> List[VectorRetrievalResult]:
        """
        使用向量相似度檢索文檔

        Args:
            query: 查詢文本
            top_k: 返回前 k 個結果
            doc_type: 限制文檔類型 (sop, safety, troubleshooting)

        Returns:
            檢索結果列表
        """
        if self.index is None or not OLLAMA_AVAILABLE:
            print("⚠️ 索引不可用或 Ollama 不可用")
            return []

        # 生成查詢嵌入
        query_embedding = self.get_embedding(query)
        if query_embedding is None:
            return []

        # 搜索
        query_vector = query_embedding.reshape(1, -1)
        distances, indices = self.index.search(query_vector, min(top_k * 2, len(self.doc_ids)))

        # 過濾並排序結果
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= len(self.doc_ids):
                continue

            doc_id = self.doc_ids[idx]
            doc = self.loader.documents.get(doc_id)

            if doc is None:
                continue

            # 過濾類型
            if doc_type and doc.doc_type != doc_type:
                continue

            # 計算相似度分數（距離越小越相似）
            # 使用 1 / (1 + distance) 轉換為 0-1 之間的分數
            score = 1.0 / (1.0 + float(dist))

            results.append(VectorRetrievalResult(
                document=doc,
                score=score,
                distance=float(dist)
            ))

        # 按分數排序
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]

    def retrieve_for_sop(self, query: str, top_k: int = 3) -> List[VectorRetrievalResult]:
        """檢索 SOP 文件"""
        return self.retrieve(query, top_k=top_k, doc_type="sop")

    def retrieve_for_safety(self, query: str, top_k: int = 3) -> List[VectorRetrievalResult]:
        """檢索安全須知"""
        return self.retrieve(query, top_k=top_k, doc_type="safety")

    def retrieve_for_troubleshooting(self, query: str, top_k: int = 3) -> List[VectorRetrievalResult]:
        """檢索問題排解"""
        return self.retrieve(query, top_k=top_k, doc_type="troubleshooting")

    def get_context_string(self, results: List[VectorRetrievalResult]) -> str:
        """將檢索結果轉換為上下文字串"""
        if not results:
            return ""

        parts = []
        for i, result in enumerate(results, 1):
            parts.append(f"[文件 {i}] {result.document.title} (相關度: {result.score:.2%})")
            parts.append(result.document.content)
            parts.append("")

        return "\n".join(parts)

    def rebuild_index(self):
        """重建索引（用於文檔更新時）"""
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        self.build_index()


# 全域向量檢索器實例
vector_retriever = FAISSVectorRetriever()
