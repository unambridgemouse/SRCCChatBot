"""
Hybrid Search & Re-ranking モジュール。
BM25（キーワード） + Pinecone（ベクトル） → RRF融合 → Cohere Re-rank
"""
import pickle
import os
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi
from app.config import get_settings
from app.utils import get_logger, tokenize_japanese

logger = get_logger(__name__)


@dataclass
class SearchNode:
    """検索結果の統一型"""
    doc_id: str
    text: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0

    @property
    def node(self):
        return self  # LlamaIndex互換インターフェース


class HybridSearcher:
    def __init__(self, pinecone_retriever, bm25_path: str):
        self.settings = get_settings()
        self.pinecone_retriever = pinecone_retriever

        # BM25: /tmp にキャッシュ（Vercelのエフェメラルストレージ活用）
        self.bm25, self.bm25_docs = self._load_bm25(bm25_path)
        logger.info(f"BM25 loaded: {len(self.bm25_docs)} documents")

    def _load_bm25(self, source_path: str) -> tuple:
        cache_path = self.settings.bm25_cache_path
        if os.path.exists(cache_path):
            logger.info(f"Loading BM25 from cache: {cache_path}")
            with open(cache_path, "rb") as f:
                return pickle.load(f)

        if not os.path.exists(source_path):
            logger.warning(f"BM25 index not found at {source_path}. Run 'make ingest' first.")
            return BM25Okapi([[""]]), []

        logger.info(f"Loading BM25 from source: {source_path}")
        with open(source_path, "rb") as f:
            data = pickle.load(f)

        # /tmp にキャッシュ保存（次回コールドスタート対策）
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
        return data

    async def search(self, query: str, metadata_filter: dict | None = None) -> list[SearchNode]:
        top_k = self.settings.max_search_results

        # 1. ベクトル検索（意味的近傍）
        vector_results = await self._vector_search(query, top_k, metadata_filter)
        logger.info(f"Vector search: {len(vector_results)} results")

        # 2. BM25キーワード検索（完全一致・専門用語強）
        bm25_results = self._bm25_search(query, top_k)
        logger.info(f"BM25 search: {len(bm25_results)} results")

        # 3. RRF (Reciprocal Rank Fusion) でマージ
        merged = self._reciprocal_rank_fusion(vector_results, bm25_results)
        logger.info(f"RRF merged: {len(merged)} results")

        # 4. Cohere Re-rank で最終 rerank_top_n 件に絞る
        reranked = await self._cohere_rerank(query, merged)
        logger.info(f"After rerank: {len(reranked)} results")

        return reranked

    async def _vector_search(
        self, query: str, top_k: int, metadata_filter: dict | None
    ) -> list[SearchNode]:
        try:
            nodes = await self.pinecone_retriever.aretrieve(query)
            return [
                SearchNode(
                    doc_id=n.node.metadata.get("doc_id", ""),
                    text=n.node.text,
                    metadata=n.node.metadata,
                    score=n.score or 0.0,
                )
                for n in nodes
            ]
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    def _bm25_search(self, query: str, top_k: int) -> list[SearchNode]:
        if not self.bm25_docs:
            return []
        tokens = tokenize_japanese(query)
        scores = self.bm25.get_scores(tokens)
        top_indices = scores.argsort()[-top_k:][::-1]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                doc = self.bm25_docs[idx]
                results.append(
                    SearchNode(
                        doc_id=doc.get("doc_id", ""),
                        text=doc.get("text", ""),
                        metadata=doc,
                        score=float(scores[idx]),
                    )
                )
        return results

    def _reciprocal_rank_fusion(
        self, list_a: list[SearchNode], list_b: list[SearchNode], k: int = 60
    ) -> list[SearchNode]:
        """RRF: 複数ランキングリストをスコアで統合"""
        scores: dict[str, dict] = {}
        for rank, node in enumerate(list_a):
            doc_id = node.doc_id
            if doc_id not in scores:
                scores[doc_id] = {"node": node, "score": 0.0}
            scores[doc_id]["score"] += 1.0 / (k + rank + 1)

        for rank, node in enumerate(list_b):
            doc_id = node.doc_id
            if doc_id not in scores:
                scores[doc_id] = {"node": node, "score": 0.0}
            scores[doc_id]["score"] += 1.0 / (k + rank + 1)

        sorted_nodes = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        for item in sorted_nodes:
            item["node"].score = item["score"]
        return [item["node"] for item in sorted_nodes]

    async def _cohere_rerank(self, query: str, nodes: list[SearchNode]) -> list[SearchNode]:
        """Cohere Re-rank APIで最終絞り込み"""
        if not nodes:
            return []
        try:
            import cohere
            co = cohere.Client(self.settings.cohere_api_key)
            documents = [n.text for n in nodes]
            response = co.rerank(
                model=self.settings.rerank_model,
                query=query,
                documents=documents,
                top_n=self.settings.rerank_top_n,
            )
            reranked = []
            for result in response.results:
                node = nodes[result.index]
                node.score = result.relevance_score
                reranked.append(node)
            return reranked
        except Exception as e:
            logger.warning(f"Cohere rerank failed, using top-{self.settings.rerank_top_n}: {e}")
            return nodes[: self.settings.rerank_top_n]
