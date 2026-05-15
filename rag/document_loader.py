# rag/document_loader.py
"""
文件載入器 - 最終修正版
邏輯：保留舊版邏輯，但增加除錯訊息與適當的 Chunk Size
"""

from typing import Dict, List
from dataclasses import dataclass, field
from pathlib import Path
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter

@dataclass
class Document:
    """文件結構"""
    id: str
    title: str
    content: str
    source: str
    doc_type: str
    metadata: Dict = field(default_factory=dict)

class DocumentLoader:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # 永遠相對於這個檔案的位置，不受 working directory 影響
            data_dir = str(Path(__file__).parent.parent / "data")
        self.data_dir = Path(data_dir)
        self.documents: Dict[str, Document] = {}
        self._loaded = False
    
    def load_all(self) -> Dict[str, Document]:
        if self._loaded:
            return self.documents
        
        print("📂 開始載入文件...")

        # 1. 載入 SOP (Chunk Size: 800)
        sop_path = self.data_dir / "sop.md"
        if sop_path.exists():
            loader = TextLoader(str(sop_path), encoding="utf-8")
            raw_docs = loader.load()
            splitter = CharacterTextSplitter(chunk_size=800, chunk_overlap=100)
            chunks = splitter.split_documents(raw_docs)
            
            for i, chunk in enumerate(chunks):
                doc_id = f"sop_{i}"
                metadata = {"source": "sop"}
                # 簡單的步驟標記
                for k in range(1, 15):
                    if f"第{k}步驟" in chunk.page_content:
                        metadata["step"] = f"第{k}步驟"
                
                self.documents[doc_id] = Document(
                    id=doc_id, title=f"SOP Part {i}", content=chunk.page_content,
                    source="sop", doc_type="sop", metadata=metadata
                )
            print(f"   ✅ SOP 載入完成: {len(chunks)} 個區塊")

        # 2. 載入 Troubleshooting (Chunk Size: 300 - 稍微加大以確保完整性)
        trouble_path = self.data_dir / "troubleshooting.md"
        if trouble_path.exists():
            loader = TextLoader(str(trouble_path), encoding="utf-8")
            raw_docs = loader.load()
            splitter = CharacterTextSplitter(chunk_size=300, chunk_overlap=50)
            chunks = splitter.split_documents(raw_docs)
            
            for i, chunk in enumerate(chunks):
                doc_id = f"trouble_{i}"
                self.documents[doc_id] = Document(
                    id=doc_id, title=f"Trouble Part {i}", content=chunk.page_content,
                    source="troubleshooting", doc_type="troubleshooting", metadata={"source": "troubleshooting"}
                )
            print(f"   ✅ 問題排解載入完成: {len(chunks)} 個區塊")

        # 3. 載入 Safety (Chunk Size: 1500)
        safety_path = self.data_dir / "safety.md"
        if safety_path.exists():
            loader = TextLoader(str(safety_path), encoding="utf-8")
            raw_docs = loader.load()
            splitter = CharacterTextSplitter(chunk_size=1500, chunk_overlap=100)
            chunks = splitter.split_documents(raw_docs)
            
            for i, chunk in enumerate(chunks):
                doc_id = f"safety_{i}"
                self.documents[doc_id] = Document(
                    id=doc_id, title=f"Safety Part {i}", content=chunk.page_content,
                    source="safety", doc_type="safety", metadata={"source": "safety"}
                )
            print(f"   ✅ 安全須知載入完成: {len(chunks)} 個區塊")
        
        self._loaded = True
        return self.documents

document_loader = DocumentLoader()