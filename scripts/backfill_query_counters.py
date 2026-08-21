"""
既存の query_log から月次カウンタ（query_count:* / query_sessions:*）を再構築する。

月次カウンタは query_log がトリムされても件数だけを永久に残すための仕組み
（app/core/query_logger.py 参照）。カウンタ導入以前のログを取り込むために使う。

安全策: query_log から算出した件数が既存カウンタ値を下回る月はスキップする
（＝ログがトリム済みの過去月を、少ない値で上書きしてしまうのを防ぐ）。

Usage:
    python scripts/backfill_query_counters.py --dry-run
    python scripts/backfill_query_counters.py
"""
import argparse
import collections
import json
import os
import sys

from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv(".env.local", override=False)
sys.path.insert(0, os.getcwd())

from app.core.query_logger import (  # noqa: E402
    COUNT_KEY_PREFIX,
    REDIS_LOG_KEY,
    SESSION_KEY_PREFIX,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    redis = Redis(
        url=os.environ["UPSTASH_REDIS_REST_URL"],
        token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
    )
    rows = [json.loads(r) for r in redis.lrange(REDIS_LOG_KEY, 0, -1)]
    print(f"query_log: {len(rows)} entries")

    counts: dict[str, int] = collections.Counter()
    sessions: dict[str, set] = collections.defaultdict(set)
    for x in rows:
        month = x["ts"][:7]
        counts[month] += 1
        sessions[month].add(x["session_id"])

    for month in sorted(counts):
        count_key = f"{COUNT_KEY_PREFIX}{month}"
        current = int(redis.get(count_key) or 0)
        if current > counts[month]:
            print(f"  {month}: skip (既存 {current} > ログ由来 {counts[month]})")
            continue
        print(f"  {month}: answers {current} -> {counts[month]}, "
              f"sessions -> {len(sessions[month])}")
        if not args.dry_run:
            redis.set(count_key, str(counts[month]))
            redis.sadd(f"{SESSION_KEY_PREFIX}{month}", *sessions[month])

    print("dry-run（書き込みなし）" if args.dry_run else "backfill 完了")


if __name__ == "__main__":
    main()
