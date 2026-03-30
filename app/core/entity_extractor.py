"""
Entity-Focused Query Expansion モジュール。
質問から囲碁用語・SRCC固有用語を抽出し、用語集と直接照合する。
ベクトル検索を経由しない高速パスで専門用語の定義をコンテキストに挿入。
"""
import json
import anthropic
from app.config import get_settings
from app.core.prompt_builder import ENTITY_EXTRACTION_PROMPT
from app.utils import get_logger, normalize

logger = get_logger(__name__)


class EntityExtractor:
    def __init__(self, glossary: dict):
        self.settings = get_settings()
        self.client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

        # 高速照合用フラット辞書: 表記ゆれ（term_variants）も含めてインデックス化
        self.term_dict: dict[str, dict] = {}
        for item in glossary.get("items", []):
            variants = [item["term"]] + item.get("term_variants", [])
            for v in variants:
                self.term_dict[normalize(v)] = item

        logger.info(f"EntityExtractor: {len(self.term_dict)} variants indexed")

    def extract_and_expand(self, query: str) -> dict:
        """
        Returns:
            {
                "original_query": str,
                "expanded_query": str,
                "entities": list[str],
                "definitions": dict[str, {...}],
            }
        """
        # Step1: 軽量モデルで用語抽出（速度優先・Haiku使用）
        entities = self._extract_entities(query)
        logger.info(f"Extracted entities: {entities}")

        # Step2: 用語集と直接照合（ベクトル検索を経由しない）
        matched_definitions = self._match_glossary(entities)

        # Step3: 関連用語でクエリ拡張
        expanded_query = self._expand_query(query, matched_definitions)

        return {
            "original_query": query,
            "expanded_query": expanded_query,
            "entities": entities,
            "definitions": matched_definitions,
        }

    def _extract_entities(self, query: str) -> list[str]:
        try:
            resp = self.client.messages.create(
                model=self.settings.fast_model,
                max_tokens=256,
                messages=[
                    {
                        "role": "user",
                        "content": ENTITY_EXTRACTION_PROMPT.format(query=query),
                    }
                ],
            )
            raw = resp.content[0].text.strip()
            # JSONパース: 余分なマークダウン等を除去
            raw = raw.strip("`").strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
            return json.loads(raw) if raw.startswith("[") else []
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            # フォールバック: クエリ中の既知用語を単純マッチ
            return self._fallback_match(query)

    def _match_glossary(self, entities: list[str]) -> dict[str, dict]:
        matched = {}
        for entity in entities:
            key = normalize(entity)
            if key in self.term_dict:
                item = self.term_dict[key]
                matched[entity] = {
                    "definition": item["definition_for_operator"],
                    "related_terms": item.get("related_terms", []),
                    "doc_id": item["id"],
                    "category": item.get("category", ""),
                }
        return matched

    def _expand_query(self, query: str, definitions: dict) -> str:
        if not definitions:
            return query
        related_terms = list(
            {t for d in definitions.values() for t in d.get("related_terms", [])}
        )
        if related_terms:
            return f"{query} {' '.join(related_terms[:5])}"  # 最大5件追加
        return query

    def _fallback_match(self, query: str) -> list[str]:
        """LLM失敗時のフォールバック: 既知用語の単純部分一致"""
        normalized = normalize(query)
        return [term for term in self.term_dict if term in normalized]
