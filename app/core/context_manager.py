"""
Multi-turn Context Management モジュール。
Upstash Redis (REST API) を使ったサーバーレス対応セッション管理。
"""
import json
import time
from upstash_redis import Redis
from app.config import get_settings
from app.utils import get_logger

logger = get_logger(__name__)


class ConversationContextManager:
    def __init__(self):
        self.settings = get_settings()
        self.redis = Redis(
            url=self.settings.upstash_redis_rest_url,
            token=self.settings.upstash_redis_rest_token,
        )

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def get_history(self, session_id: str) -> list[dict]:
        try:
            raw = self.redis.get(self._key(session_id))
            if not raw:
                return []
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get failed for {session_id}: {e}")
            return []

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        history = self.get_history(session_id)
        history.append({
            "role": "user",
            "content": user_msg,
            "timestamp": time.time(),
        })
        history.append({
            "role": "assistant",
            # 長文を要約保存してトークン節約（先頭500文字）
            "content": assistant_msg[:500],
            "timestamp": time.time(),
        })
        # 直近 MAX_TURNS * 2 件のみ保持
        max_entries = self.settings.max_conversation_turns * 2
        history = history[-max_entries:]

        try:
            self.redis.setex(
                self._key(session_id),
                self.settings.session_ttl_seconds,
                json.dumps(history, ensure_ascii=False),
            )
        except Exception as e:
            logger.warning(f"Redis setex failed for {session_id}: {e}")

    def format_for_prompt(self, session_id: str) -> str:
        history = self.get_history(session_id)
        if not history:
            return "（会話履歴なし）"
        lines = []
        for turn in history:
            role = "オペレーター" if turn["role"] == "user" else "AI"
            # プロンプトに挿入する際は先頭200文字に切り詰め
            lines.append(f"{role}: {turn['content'][:200]}")
        return "\n".join(lines)

    def clear(self, session_id: str) -> None:
        try:
            self.redis.delete(self._key(session_id))
        except Exception as e:
            logger.warning(f"Redis delete failed for {session_id}: {e}")
