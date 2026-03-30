"""
HybridSearcher の BM25 + RRF ロジックのユニットテスト。
Pinecone・Cohere は呼び出さない。
"""
import pickle
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from rank_bm25 import BM25Okapi

from app.core.hybrid_search import HybridSearcher, SearchNode
from app.utils.text_normalizer import tokenize_japanese

DOCS = [
    {"doc_id": "faq-001", "type": "faq", "text": "アタリ アタリをかける 石 呼吸点"},
    {"doc_id": "term-001", "type": "glossary", "text": "アタリ 当たり 呼吸点 ダメ"},
    {"doc_id": "faq-002", "type": "faq", "text": "コウ 禁手 繰り返し"},
]


@pytest.fixture
def searcher(tmp_path):
    # BM25インデックスをtmpに作成
    corpus = [tokenize_japanese(d["text"]) for d in DOCS]
    bm25 = BM25Okapi(corpus)
    pkl_path = tmp_path / "bm25.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump((bm25, DOCS), f)

    mock_retriever = AsyncMock()
    mock_retriever.aretrieve.return_value = []

    with patch("app.core.hybrid_search.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            max_search_results=5,
            rerank_top_n=3,
            bm25_cache_path=str(tmp_path / "cache.pkl"),
            cohere_api_key="test",
            rerank_model="rerank-multilingual-v3.0",
        )
        searcher = HybridSearcher(mock_retriever, str(pkl_path))
    return searcher


def test_bm25_search_returns_relevant(searcher):
    results = searcher._bm25_search("アタリとは何ですか", top_k=3)
    assert len(results) > 0
    doc_ids = [r.doc_id for r in results]
    assert "faq-001" in doc_ids or "term-001" in doc_ids


def test_rrf_merges_and_deduplicates(searcher):
    list_a = [
        SearchNode(doc_id="faq-001", text="a", score=0.9),
        SearchNode(doc_id="faq-002", text="b", score=0.7),
    ]
    list_b = [
        SearchNode(doc_id="faq-001", text="a", score=0.8),  # 重複
        SearchNode(doc_id="term-001", text="c", score=0.6),
    ]
    merged = searcher._reciprocal_rank_fusion(list_a, list_b)
    doc_ids = [n.doc_id for n in merged]
    # 重複排除されているか
    assert len(doc_ids) == len(set(doc_ids))
    # faq-001 は両リストに出るのでスコアが高いはず
    assert merged[0].doc_id == "faq-001"
