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
from app.core.store_scraper import (
    is_store_query, is_store_followup, get_store_text,
    needs_location_clarification, is_prefecture_only_query, extract_prefecture,
)
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

    def _load_faq_index(self) -> dict:
        """FAQ IDをキーにしたインデックスを返す"""
        with open(self.settings.faq_data_path, encoding="utf-8") as f:
            data = json.load(f)
        return {item["id"]: item for item in data.get("items", [])}

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

        # 都道府県のみ → 体験/購入どちらかを確認
        if is_prefecture_only_query(query):
            return self._run_prefecture_clarification(session_id, query)

        # 都道府県確認フローへの回答を処理
        prefecture_followup = self._check_prefecture_clarification_followup(query, history)
        if prefecture_followup is not None:
            if prefecture_followup == "not_found":
                return self._not_found_response(session_id, query)
            return await self._run_store_query(session_id, prefecture_followup)

        if is_store_query(query) or is_store_followup(query, history):
            return await self._run_store_query(session_id, query)

        # Step 1: Entity抽出・クエリ拡張
        entity_result = self.entity_extractor.extract_and_expand(query)
        expanded_query = entity_result["expanded_query"]

        # Step 2: Hybrid Search
        nodes = await self.hybrid_searcher.search(expanded_query, metadata_filter)

        # Step 2.5: related_faq_ids で関連FAQを補完
        nodes = self._append_related_faqs(nodes)

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
        sources = [
            SourceItem(
                doc_id=n.doc_id,
                type=n.metadata.get("type", ""),
                title=n.metadata.get("doc_id", ""),
                score=round(n.score, 3),
                source=n.metadata.get("source"),
            )
            for n in nodes
        ]

        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": query}],
            "sources": [s.model_dump() for s in sources],
            "extracted_entities": entity_result["entities"],
            "expanded_query": expanded_query,
            "session_id": session_id,
        }

    def _run_prefecture_clarification(self, session_id: str, query: str) -> dict:
        """都道府県名のみのクエリに対して体験/購入どちらかを問い返す。"""
        pref = extract_prefecture(query) or query.strip()
        logger.info(f"Prefecture-only query detected: {pref}")
        return {
            "system_prompt": (
                "あなたはSRCC（囲碁ロボット）コールセンターのサポートAIです。\n"
                "回答の読み手はSRCCのオペレーターです。\n\n"
                f"お客様が「{pref}」とだけ入力しました。"
                "体験または購入のどちらをご希望か確認するため、必ず以下の2文だけを返してください。\n\n"
                f"「{pref}県でロボットの体験をご希望ですか？」\n"
                f"「{pref}県でロボットの購入をご希望ですか？」"
            ),
            "messages": [{"role": "user", "content": query}],
            "sources": [],
            "extracted_entities": [],
            "expanded_query": query,
            "session_id": session_id,
        }

    def _check_prefecture_clarification_followup(
        self, query: str, history: list[dict]
    ) -> str | None:
        """直近の会話が都道府県確認フローなら、クエリ内容に応じて展開済みクエリ文字列を返す。
        - 「体験」系 → "{pref}で体験したい"
        - 「購入」系 → "{pref}で購入したい"
        - 「いいえ」系 → "not_found"
        - 関係ない → None（通常フロー）
        """
        if not history:
            return None
        # 直近アシスタントターンが体験/購入の確認メッセージか
        for h in reversed(history[-4:]):
            if h["role"] == "assistant" and "ご希望ですか" in h["content"]:
                break
        else:
            return None

        # 確認時のユーザー入力から都道府県を取り出す
        pref = None
        for h in reversed(history[-6:]):
            if h["role"] == "user":
                pref = extract_prefecture(h["content"])
                if pref:
                    break
        if not pref:
            return None

        _NO_WORDS = ["いいえ", "違う", "違います", "no", "ない", "別", "異なる"]
        _EXPERIENCE_WORDS = ["体験", "試し", "試せ"]
        _BUY_WORDS = ["購入", "買", "ほしい"]

        if any(w in query for w in _NO_WORDS):
            return "not_found"
        if any(w in query for w in _EXPERIENCE_WORDS):
            return f"{pref}で体験したい"
        if any(w in query for w in _BUY_WORDS):
            return f"{pref}で購入したい"
        # 「はい」だけの場合はどちらか不明 → 再度確認を促す（None で通常フロー）
        return None

    def _not_found_response(self, session_id: str, query: str) -> dict:
        """ナレッジなし固定レスポンス。"""
        return {
            "system_prompt": (
                "あなたはSRCC（囲碁ロボット）コールセンターのサポートAIです。\n"
                "回答の読み手はSRCCのオペレーターです。\n\n"
                "必ず以下の1文だけを返してください。\n\n"
                "「申し訳ありませんが、その内容に関するナレッジが見つかりませんでした。"
                "質問を言い換えてもう一度入力するか、伊藤電機へのエスカレーションをご検討ください。」"
            ),
            "messages": [{"role": "user", "content": query}],
            "sources": [],
            "extracted_entities": [],
            "expanded_query": query,
            "session_id": session_id,
        }

    async def _run_store_query(self, session_id: str, query: str) -> dict:
        """
        体験・購入場所クエリ専用フロー。
        senserobot-jp.com/store から最新情報を取得してClaudeに渡す。
        地名が指定されていない体験クエリの場合は都道府県を問い返す。
        """
        logger.info(f"Store query detected: {query}")

        if needs_location_clarification(query):
            logger.info("Experience query without location — asking for prefecture")
            return {
                "system_prompt": (
                    "あなたはSRCC（囲碁ロボット）コールセンターのサポートAIです。\n"
                    "回答の読み手はSRCCのオペレーターです。\n\n"
                    "ユーザーが体験店舗を探していますが、地名（都道府県）が指定されていません。\n"
                    "必ず以下の1文だけを返してください。余計な情報は一切追加しないこと。\n\n"
                    "「お客様のご所在地（都道府県）をお聞かせいただけますか？最寄りの体験店舗をご案内いたします。」"
                ),
                "messages": [{"role": "user", "content": query}],
                "sources": [],
                "extracted_entities": [],
                "expanded_query": query,
                "session_id": session_id,
            }

        store_text = await get_store_text()
        history_text = self.context_manager.format_for_prompt(session_id)
        system_prompt = prompt_builder.build_store_system_prompt(
            store_text=store_text,
            conversation_history=history_text,
        )
        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": query}],
            "sources": [
                SourceItem(
                    doc_id="store",
                    type="store",
                    title="store",
                    score=1.0,
                    source="https://www.senserobot-jp.com/store",
                ).model_dump()
            ],
            "extracted_entities": [],
            "expanded_query": query,
            "session_id": session_id,
        }

    def _append_related_faqs(self, nodes: list) -> list:
        """取得ノードのrelated_faq_idsに含まれるFAQを未取得なら補完する"""
        from app.core.hybrid_search import SearchNode
        try:
            faq_index = self._load_faq_index()
        except Exception as e:
            logger.warning(f"Failed to load FAQ index for related FAQs: {e}")
            return nodes

        retrieved_ids = {n.doc_id for n in nodes}
        extra_nodes = []
        for node in list(nodes):
            # node.metadataではなくfaq_index（最新のfaq_master.json）からrelated_faq_idsを取得
            faq_item = faq_index.get(node.doc_id)
            related_ids = faq_item.get("related_faq_ids", []) if faq_item else []
            for related_id in related_ids:
                if related_id in retrieved_ids or related_id in {n.doc_id for n in extra_nodes}:
                    continue
                item = faq_index.get(related_id)
                if not item:
                    continue
                extra_nodes.append(SearchNode(
                    doc_id=related_id,
                    text=item.get("answer") or item.get("embedding_text", ""),
                    metadata={**item, "type": "faq", "_is_related": True},
                    score=node.score,  # 親ノードと同スコアを付与
                ))
                logger.info(f"Related FAQ appended: {related_id}")

        return nodes + extra_nodes

    def save_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """回答確定後にセッションへ保存"""
        self.context_manager.add_turn(session_id, user_msg, assistant_msg)
