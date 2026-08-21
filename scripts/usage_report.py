"""
SRCCセンちゃんBot 利用実績レポート生成スクリプト。

Upstash Redis の query_log（全応答ログ）を集計し、
四半期報告用の Markdown レポートを標準出力に書き出す。

Usage:
    python scripts/usage_report.py                    # 全期間
    python scripts/usage_report.py --from 2026-06-01 --to 2026-08-31
    python scripts/usage_report.py --minutes 8        # 1件あたり削減工数（分）を変更
    python scripts/usage_report.py --out docs/USAGE_REPORT.md
"""
import argparse
import collections
import json
import os
import statistics
import sys

import requests
from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv(".env.local", override=False)

sys.path.insert(0, os.getcwd())
from app.core.query_logger import get_monthly_stats  # noqa: E402

REDIS_LOG_KEY = "query_log"
DEFAULT_MINUTES_SAVED = 5  # 1応答あたりの削減工数（分）— 報告時の前提値


def fetch_logs() -> list[dict]:
    url = os.environ["UPSTASH_REDIS_REST_URL"]
    token = os.environ["UPSTASH_REDIS_REST_TOKEN"]
    res = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=["LRANGE", REDIS_LOG_KEY, "0", "-1"],
        timeout=30,
    )
    res.raise_for_status()
    return [json.loads(r) for r in res.json()["result"]]


def fetch_monthly_stats() -> dict[str, dict]:
    """月次カウンタ（TTLなし・永久保持）を取得する。

    query_log がトリムされた過去月についても件数が残るため、
    報告値の根拠としてはこちらが正となる。
    """
    redis = Redis(
        url=os.environ["UPSTASH_REDIS_REST_URL"],
        token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
    )
    return get_monthly_stats(redis)


def build_report(rows: list[dict], minutes: int, monthly: dict[str, dict] | None = None) -> str:
    rows = sorted(rows, key=lambda x: x["ts"])
    total = len(rows)
    if total == 0:
        return "# 利用実績\n\n対象期間のログがありません。\n"

    sessions = {x["session_id"] for x in rows}
    days = collections.Counter(x["ts"][:10] for x in rows)

    # 月別
    per_month = collections.defaultdict(lambda: [0, set()])
    for x in rows:
        key = x["ts"][:7]
        per_month[key][0] += 1
        per_month[key][1].add(x["session_id"])

    # 参照ナレッジ
    top_docs = collections.Counter()
    for x in rows:
        if x.get("sources"):
            top_docs[x["sources"][0]["id"]] += 1
    no_source = sum(1 for x in rows if not x.get("sources"))

    hours = collections.Counter(int(x["ts"][11:13]) for x in rows)

    saved_min = total * minutes
    lines = []
    a = lines.append
    a("# SRCCセンちゃんBot 利用実績レポート")
    a("")
    a(f"- 集計期間: **{rows[0]['ts'][:10]} 〜 {rows[-1]['ts'][:10]}**")
    a(f"- 総応答件数: **{total} 件**")
    a(f"- 相談セッション数: **{len(sessions)} 件**（1セッション平均 {total/len(sessions):.1f} 往復）")
    a(f"- ログのあった稼働日数: **{len(days)} 日**（1日平均 {total/len(days):.1f} 件）")
    a(f"- 回答が知識ベースに紐づいた率: **{(total-no_source)/total*100:.1f}%**（該当なし {no_source} 件）")
    a(f"- 平均回答文字数: {statistics.mean(len(x['answer']) for x in rows):.0f} 文字")
    a("")
    a("## 削減工数の試算")
    a("")
    a(f"1件あたりの調査・回答時間を **{minutes} 分** と置いた場合:")
    a("")
    a(f"> {total} 件 × {minutes} 分 = **{saved_min:,} 分（約 {saved_min/60:.1f} 時間）**")
    a("")
    a("※ セッション単位（1問合せ＝1セッション）で数える場合は "
      f"{len(sessions)} 件 × {minutes} 分 = {len(sessions)*minutes:,} 分（約 {len(sessions)*minutes/60:.1f} 時間）")
    a("")
    a("## 月別内訳")
    a("")
    a("| 月 | 応答件数 | セッション数 | 1セッション平均往復 |")
    a("|---|---:|---:|---:|")
    for k in sorted(per_month):
        c, s = per_month[k]
        a(f"| {k} | {c} | {len(s)} | {c/len(s):.1f} |")
    a("")

    if monthly:
        counter_total = sum(v["answers"] for v in monthly.values())
        a("## 月次カウンタ（永久保持・報告値の正）")
        a("")
        a("Redis の `query_count:YYYY-MM` / `query_sessions:YYYY-MM` に記録された累計。")
        a("ログ本体がトリムされた過去月も件数が残るため、長期の報告はこちらを使う。")
        a("")
        a("| 月 | 応答件数 | セッション数 |")
        a("|---|---:|---:|")
        for k, v in monthly.items():
            a(f"| {k} | {v['answers']} | {v['sessions']} |")
        a(f"| **累計** | **{counter_total}** | — |")
        a("")
    a("## 時間帯別の利用（コールセンター稼働時間との整合確認）")
    a("")
    a("| 時 | 件数 |")
    a("|---:|---:|")
    for h in sorted(hours):
        a(f"| {h}時 | {hours[h]} |")
    a("")
    a("## よく参照されたナレッジ TOP15")
    a("")
    a("| ナレッジID | 参照件数 |")
    a("|---|---:|")
    for k, v in top_docs.most_common(15):
        a(f"| {k} | {v} |")
    a("")
    a("## 集計方法")
    a("")
    a("Bot が回答を返すたびに `app/api/chat.py` から `save_query_log()` が呼ばれ、")
    a("Upstash Redis のリスト `query_log` と Railway の標準出力に1件ずつ記録される。")
    a("本レポートはそのリストを `scripts/usage_report.py` で集計したもの。")
    a("")
    a("関連: [[SPEC]] / [[STRUCTURE]] / [[CHANGELOG]]")
    a("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="date_from", help="YYYY-MM-DD 以降")
    p.add_argument("--to", dest="date_to", help="YYYY-MM-DD 以前")
    p.add_argument("--minutes", type=int, default=DEFAULT_MINUTES_SAVED,
                   help="1応答あたりの削減工数（分）")
    p.add_argument("--out", help="出力先ファイル（省略時は標準出力）")
    args = p.parse_args()

    rows = fetch_logs()
    if args.date_from:
        rows = [x for x in rows if x["ts"][:10] >= args.date_from]
    if args.date_to:
        rows = [x for x in rows if x["ts"][:10] <= args.date_to]

    monthly = fetch_monthly_stats()
    if args.date_from:
        monthly = {k: v for k, v in monthly.items() if k >= args.date_from[:7]}
    if args.date_to:
        monthly = {k: v for k, v in monthly.items() if k <= args.date_to[:7]}

    report = build_report(rows, args.minutes, monthly)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"wrote {args.out} ({len(rows)} entries)", file=sys.stderr)
    else:
        sys.stdout.buffer.write(report.encode("utf-8"))


if __name__ == "__main__":
    main()
