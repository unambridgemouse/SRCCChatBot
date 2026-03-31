"""
RAGパイプライン統合モジュール。
LLMへの直接呼び出しはすべてここを経由する。

処理フロー:
  1. EntityExtractor → 用語抽出・クエリ拡張
  2. HybridSearcher  → BM25 + Vector + RRF + Rerank
  3. ContextManager  → 会話履歴の取得
  4. PromptBuilder   → システムプロンプト組み立て
  5. Claude API      → ストリーミング回答生成
  6. ContextManager  → 会話履歴の保存
"""
import json
import os
from functools import cached_property

from pinecone import Pinecone
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.cohere import CohereEmbedding
from llama_index.core.retrievers import VectorIndexRetriever

from app.config import get_settings
from app.core.entity_extractor import EntityExtractor
from app.core.hybrid_search import HybridSearcher
from app.core.context_manager import ConversationContextManager
from app.core import prompt_builder
from app.core.store_scraper import is_store_query, is_store_followup, get_store_text
from app.models.response import SourceItem
from app.utils import get_logger

logger = get_logger(__name__)


class RAGPipeline:
    """シングルトンとして main.py でインスタンス化する"""

    def __init__(self):
        self.settings = get_settings()
        self._glossary: dict | None = None
        self._entity_extractor: EntityExtractor | None = None
        self._hybrid_searcher: HybridSearcher | None = None
        self._context_manager: ConversationContextManager | None = None

    def _load_glossary(self) -> dict:
        with open(self.settings.glossary_data_path, encoding="utf-8") as f:
            return json.load(f)

    @cached_property
    def entity_extractor(self) -> EntityExtractor:
        if self._glossary is None:
            self._glossary = self._load_glossary()
        return EntityExtractor(self._glossary)

    @cached_property
    def hybrid_searcher(self) -> HybridSearcher:
        pc = Pinecone(api_key=self.settings.pinecone_api_key)
        index = pc.Index(self.settings.pinecone_index_name)
        vector_store = PineconeVectorStore(pinecone_index=index)
        embed_model = CohereEmbedding(
            cohere_api_key=self.settings.cohere_api_key,
            model_name=self.settings.embedding_model,
            input_type="search_query",  # 検索クエリ時
        )
        llama_index = VectorStoreIndex.from_vector_store(
            vector_store, embed_model=embed_model
        )
        retriever = VectorIndexRetriever(
            index=llama_index,
            similarity_top_k=self.settings.max_search_results,
        )
        bm25_path = self.settings.bm25_cache_path.replace("/tmp/", "data/")
        return HybridSearcher(retriever, bm25_path)

    @cached_property
    def context_manager(self) -> ConversationContextManager:
        return ConversationContextManager()

    async def run(self, session_id: str, query: str, metadata_filter: dict | None = None) -> dict:
        """
        Returns:
            {
                "system_prompt": str,
                "messages": list,
                "sources": list[SourceItem],
                "extracted_entities": list[str],
                "expanded_query": str,
            }
        """
        # 店舗クエリ（体験・購入場所の検索）は専用フローで処理
        history = self.context_manager.get_history(session_id)
        if is_store_query(query) or is_store_followup(query, history):
            return await self._run_store_query(session_id, query)

        # Step 1: Entity抽出・クエリ拡張
        entity_result = self.entity_extractor.extract_and_expand(query)
        expanded_query = entity_result["expanded_query"]

        # Step 2: Hybrid Search
        nodes = await self.hybrid_searcher.search(expanded_query, metadata_filter)

        # Step 3: 会話履歴
        history_text = self.context_manager.format_for_prompt(session_id)

        # Step 4: プロンプト組み立て
        retrieved_context = prompt_builder.build_retrieved_context(nodes)
        entity_context = prompt_builder.build_entity_context(entity_result["definitions"])
        system_prompt = prompt_builder.build_system_prompt(
            conversation_history=history_text,
            retrieved_context=retrieved_context,
            extracted_entities=entity_context,
        )

        # Step 5: ソース情報の整形（フロントエンド表示用）
        # スコアが低い場合は関連ナレッジなしとみなしてsourcesを返さない
        MIN_SCORE = 0.05
        top_score = max((n.score for n in nodes), default=0.0)
        sources = (
            [
                SourceItem(
                    doc_id=n.doc_id,
                    type=n.metadata.get("type", ""),
                    title=n.metadata.get("doc_id", ""),
                    score=round(n.score, 3),
                    source=n.metadata.get("source"),
                )
                for n in nodes
            ]
            if top_score >= MIN_SCORE
            else []
        )

        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": query}],
            "sources": [s.model_dump() for s in sources],
            "extracted_entities": entity_result["entities"],
            "expanded_query": expanded_query,
            "session_id": session_id,
        }

    async def _run_store_query(self, session_id: str, query: str) -> dict:
        """
        体験・購入場所クエリ専用フロー。
        senserobot-jp.com/store から最新情報を取得してClaudeに渡す。
        """
        logger.info(f"Store query detected: {query}")
        store_text = await get_store_text()
        history_text = self.context_manager.format_for_prompt(session_id)
        system_prompt = prompt_builder.build_store_system_prompt(
            store_text=store_text,
            conversation_history=history_text,
        )
        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": query}],
            "sources": [],
            "extracted_entities": [],
            "expanded_query": query,
            "session_id": session_id,
        }

    def save_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """回答確定後にセッションへ保存"""
        self.context_manager.add_turn(session_id, user_msg, assistant_msg)
