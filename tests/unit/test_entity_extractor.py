"""
EntityExtractor のユニットテスト。
LLM呼び出しはモックする。
"""
import pytest
from unittest.mock import MagicMock, patch

MOCK_GLOSSARY = {
    "items": [
        {
            "id": "term-001",
            "type": "glossary",
            "term": "アタリ",
            "term_variants": ["当たり", "あたり", "ATARI"],
            "definition": "石の呼吸点が残り1つになった状態。",
            "definition_for_operator": "次の一手で石が取られる状態です。",
            "related_terms": ["ダメ", "呼吸点"],
            "embedding_text": "アタリ",
        },
        {
            "id": "term-002",
            "type": "glossary",
            "term": "コウ",
            "term_variants": ["劫", "こう"],
            "definition": "繰り返しを防ぐルール。",
            "definition_for_operator": "直前に取られた場所をすぐ取り返せないルール。",
            "related_terms": ["禁手"],
            "embedding_text": "コウ",
        },
    ]
}


@pytest.fixture
def extractor():
    with patch("app.core.entity_extractor.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            anthropic_api_key="test",
            fast_model="claude-haiku-4-5-20251001",
        )
        with patch("app.core.entity_extractor.anthropic.Anthropic"):
            from app.core.entity_extractor import EntityExtractor
            return EntityExtractor(MOCK_GLOSSARY)


def test_glossary_indexed(extractor):
    # 表記ゆれも含めてインデックス化されているか
    assert "アタリ" in extractor.term_dict
    assert "atari" in extractor.term_dict  # NFKC正規化で小文字化
    assert "コウ" in extractor.term_dict


def test_fallback_match(extractor):
    matches = extractor._fallback_match("アタリをかけるとはどういう意味ですか？")
    assert "アタリ" in matches


def test_match_glossary(extractor):
    result = extractor._match_glossary(["アタリ"])
    assert "アタリ" in result
    assert "definition" in result["アタリ"]
    assert "related_terms" in result["アタリ"]


def test_expand_query(extractor):
    definitions = {
        "アタリ": {"related_terms": ["ダメ", "呼吸点"], "definition": "...", "doc_id": "term-001"}
    }
    expanded = extractor._expand_query("アタリとは何ですか", definitions)
    assert "アタリとは何ですか" in expanded
    assert "ダメ" in expanded or "呼吸点" in expanded
