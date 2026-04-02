"""
クエリログモジュール。
各チャットのクエリ・回答・参照ナレッジを
① Railway stdout（構造化JSON）
② Upstash Redis リスト（直近500件を永続保持）
の2箇所に保存する。
"""
import json
import time
from datetime import datetime, timezone, timedelta

from app.utils import get_logger

logger = get_logger(__name__)

REDIS_LOG_KEY = "query_log"
MAX_LOG_ENTRIES = 500  # Redis に保持する最大件数
JST = timezone(timedelta(hours=9))


def _build_entry(
    session_id: str,
    query: str,
    answer: str,
    sources: list,
    expanded_query: str,
    system_prompt: str = "",
) -> dict:
    now = datetime.now(JST)
    return {
        "ts":             now.strftime("%Y-%m-%d %H:%M:%S"),
        "ts_unix":        time.time(),
        "session_id":     session_id,
        "query":          query,
        "expanded_query": expanded_query,
        "answer":         answer[:300],          # 先頭300文字
        "sources":        [
            {"id": s.get("doc_id", ""), "score": s.get("score", 0)}
            for s in (sources or [])
        ],
        "system_prompt":  system_prompt,
    }


def save_query_log(
    redis,                # ConversationContextManager.redis と同一インスタンス
    session_id: str,
    query: str,
    answer: str,
    sources: list,
    expanded_query: str,
    system_prompt: str = "",
) -> None:
    entry = _build_entry(session_id, query, answer, sources, expanded_query, system_prompt)

    # ① Railway stdout（構造化JSON）
    logger.info("[QUERY_LOG] " + json.dumps(entry, ensure_ascii=False))

    # ② Upstash Redis（リストの先頭に追加し最大件数を超えたらトリム）
    try:
        raw = json.dumps(entry, ensure_ascii=False)
        redis.lpush(REDIS_LOG_KEY, raw)
        redis.ltrim(REDIS_LOG_KEY, 0, MAX_LOG_ENTRIES - 1)
    except Exception as e:
        logger.warning(f"Query log Redis write failed: {e}")


def get_query_logs(redis, limit: int = 100) -> list[dict]:
    """Redis から直近 limit 件のログを取得する"""
    try:
        raw_list = redis.lrange(REDIS_LOG_KEY, 0, limit - 1)
        return [json.loads(r) for r in raw_list]
    except Exception as e:
        logger.warning(f"Query log Redis read failed: {e}")
        return []
