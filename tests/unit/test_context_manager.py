"""
ConversationContextManager のユニットテスト。
Upstash Redis はモックする。
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.context_manager import ConversationContextManager


@pytest.fixture
def ctx_manager():
    with patch("app.core.context_manager.get_settings") as mock_settings, \
         patch("app.core.context_manager.Redis") as mock_redis_class:
        mock_settings.return_value = MagicMock(
            upstash_redis_rest_url="https://test.upstash.io",
            upstash_redis_rest_token="token",
            session_ttl_seconds=1800,
            max_conversation_turns=5,
        )
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        manager = ConversationContextManager()
        manager.redis = mock_redis
        return manager


def test_add_and_get_turn(ctx_manager):
    ctx_manager.redis.get.return_value = None

    ctx_manager.add_turn("sess-1", "アタリとは？", "アタリとは呼吸点が1つになった状態です。")

    call_args = ctx_manager.redis.setex.call_args
    assert call_args is not None
    key = call_args[0][0]
    assert key == "session:sess-1"


def test_format_for_prompt_empty(ctx_manager):
    ctx_manager.redis.get.return_value = None
    result = ctx_manager.format_for_prompt("sess-new")
    assert "会話履歴なし" in result


def test_max_turns_trimmed(ctx_manager):
    import json, time
    # 6ターン（12エントリ）のヒストリーを設定（max=5ターン=10エントリ）
    history = []
    for i in range(6):
        history.append({"role": "user", "content": f"質問{i}", "timestamp": time.time()})
        history.append({"role": "assistant", "content": f"回答{i}", "timestamp": time.time()})
    ctx_manager.redis.get.return_value = json.dumps(history)

    ctx_manager.add_turn("sess-x", "新しい質問", "新しい回答")

    call_args = ctx_manager.redis.setex.call_args[0]
    saved = json.loads(call_args[2])
    assert len(saved) <= 10  # 5ターン * 2
