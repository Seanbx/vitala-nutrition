"""
检索模块
负责向量检索、BM25检索、混合检索与重排序
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional

from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)


class NutriRetriever:
    """营养助手检索器 —— 向量 + BM25 + RRF 混合检索"""

    def __init__(
        self,
        vectorstore: Chroma,
        chunks: List[Document],
        top_k: int = 5,
    ):
        self.vectorstore = vectorstore
        self.chunks = chunks
        self.top_k = top_k
        self._bm25_retriever = None
        self._setup()

    def _setup(self):
        self._vector_retriever = None
        if self.vectorstore is not None:
            self._vector_retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": self.top_k * 2},
            )
        try:
            from langchain_community.retrievers import BM25Retriever
            self._bm25_retriever = BM25Retriever.from_documents(
                self.chunks,
                k=self.top_k * 2,
                preprocess_func=self._tokenize,
            )
        except ImportError:
            logger.warning("rank_bm25 未安装，BM25检索不可用")
        except Exception as e:
            logger.warning(f"BM25检索器初始化失败: {e}")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        try:
            import jieba
            logging.getLogger("jieba").setLevel(logging.WARNING)
            return [w.strip() for w in jieba.lcut(text) if w.strip()]
        except ImportError:
            return text.split()

    def vector_search(self, query: str, top_k: int = None) -> List[Document]:
        k = top_k or self.top_k
        if self.vectorstore is None:
            return []
        try:
            return self._vector_retriever.invoke(query)[:k]
        except Exception as e:
            logger.warning(f"向量检索不可用，跳过: {e}")
            return []

    def bm25_search(self, query: str, top_k: int = None) -> List[Document]:
        k = top_k or self.top_k
        if self._bm25_retriever is None:
            return []
        return self._bm25_retriever.invoke(query)[:k]

    def hybrid_search(self, query: str, top_k: int = None) -> List[Document]:
        k = top_k or self.top_k
        vector_docs = self.vector_search(query, k * 2)
        bm25_docs = self.bm25_search(query, k * 2)
        if not vector_docs and not bm25_docs:
            return []

        fused = self._rrf_fusion(vector_docs, bm25_docs)
        if not fused and bm25_docs:
            # 向量检索不可用时，直接返回 BM25 结果
            candidates = bm25_docs
        else:
            candidates = fused
        # 按文档标题去重：长文档分块多会霸榜，改为每篇文档只保留最相关的一块
        seen = set()
        result = []
        for doc in candidates:
            key = doc.metadata.get("title") or doc.metadata.get("source", "")
            if key in seen:
                continue
            seen.add(key)
            result.append(doc)
            if len(result) >= k:
                break
        if not result and candidates:
            result = candidates[:k]
        return result

    def metadata_filter_search(
        self, query: str, filters: Dict[str, Any], top_k: int = None
    ) -> List[Document]:
        k = top_k or self.top_k
        candidates = self.hybrid_search(query, k * 3)

        filtered = []
        for doc in candidates:
            match = True
            for key, value in filters.items():
                doc_val = doc.metadata.get(key)
                if doc_val is None:
                    match = False
                    break
                if isinstance(value, list):
                    if doc_val not in value:
                        match = False
                        break
                elif doc_val != value:
                    match = False
                    break
            if match:
                filtered.append(doc)
                if len(filtered) >= k:
                    break
        return filtered

    @staticmethod
    def _rrf_fusion(
        vector_docs: List[Document],
        bm25_docs: List[Document],
        k: int = 60,
    ) -> List[Document]:
        scores: Dict[str, float] = {}
        objects: Dict[str, Document] = {}

        for rank, doc in enumerate(vector_docs):
            doc_id = hashlib.md5(doc.page_content.encode()).hexdigest()
            objects[doc_id] = doc
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

        for rank, doc in enumerate(bm25_docs):
            doc_id = hashlib.md5(doc.page_content.encode()).hexdigest()
            objects[doc_id] = doc
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        for doc_id, score in sorted_ids:
            if doc_id in objects:
                doc = objects[doc_id]
                doc.metadata["rrf_score"] = round(score, 6)
                result.append(doc)
        return result
