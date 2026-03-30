"""
FAQ_20260325.csv → data/faq/faq_master.json 変換スクリプト。
既存サンプルデータを上書きし、実データ77件で置き換える。

Usage:
    cd C:/Users/hashiguchi/ClaudeProjects/srcc-faq-bot
    python scripts/convert_csv_to_faq.py
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

CSV_PATH = Path("C:/Users/hashiguchi/Desktop/FAQ_20260325.csv")
OUTPUT_PATH = Path(__file__).parent.parent / "data/faq/faq_master.json"

# タグ文字列 → Python list
def parse_tags(tag_str: str) -> list[str]:
    if not tag_str:
        return []
    # スラッシュ区切り、空白除去
    return [t.strip() for t in re.split(r"[/／]", tag_str) if t.strip()]

# 問合せ内容 → カテゴリ推定
def infer_category(title: str) -> tuple[str, str]:
    t = title
    if "エスカレーション" in t:
        return "サポート対応", "エスカレーション"
    if "ゲストモード" in t:
        return "操作方法", "ログイン・ゲストモード"
    if "ペアリング" in t or "ネットワーク接続" in t or "初期設定" in t:
        return "セットアップ", "ペアリング・ネットワーク"
    if "Wi-Fi" in t or "ネットワーク" in t:
        return "セットアップ", "ネットワーク・Wi-Fi"
    if "QRコード" in t or "カメラ" in t:
        return "トラブル", "カメラ・QRコード"
    if "詰め碁" in t or "詰碁" in t:
        return "仕様・機能", "対局モード"
    if "廃棄" in t or "回収" in t:
        return "方針・規定", "廃棄・回収"
    if "GOボタン" in t:
        return "操作方法", "対局操作"
    if "パス" in t:
        return "操作方法", "対局操作"
    if "レベル" in t or "強さ" in t or "棋力" in t:
        return "仕様・機能", "対局モード"
    if "棋譜" in t:
        return "仕様・機能", "棋譜・データ"
    if "保存" in t or "一時停止" in t or "放置" in t:
        return "仕様・機能", "対局保存"
    if "位置" in t or "碁石を正しい" in t or "重ねて" in t:
        return "トラブル", "ハードウェア"
    if "友達対戦" in t or "遠隔" in t:
        return "仕様・機能", "対局モード"
    if "一手戻" in t or "訂正" in t:
        return "操作方法", "対局操作"
    if "表示されない" in t or "反映されない" in t:
        return "トラブル", "アプリ・データ"
    if "勝敗" in t or "アゲハマ" in t or "判定" in t or "終局" in t:
        return "仕様・機能", "ルール・判定"
    if "対局異常" in t:
        return "トラブル", "対局エラー"
    if "終わらせたい" in t or "投了" in t:
        return "操作方法", "対局操作"
    if "電源" in t:
        return "操作方法", "電源操作"
    if "ボタン" in t:
        return "トラブル", "ハードウェア"
    if "碁石を拾わない" in t or "アーム" in t:
        return "トラブル", "ハードウェア"
    if "認証" in t or "ログイン" in t or "アカウント" in t:
        return "セットアップ", "アプリ・アカウント"
    if "アプリ" in t:
        return "操作方法", "アプリ操作"
    if "更新" in t or "アップデート" in t:
        return "操作方法", "ソフトウェア更新"
    if "購入" in t or "価格" in t or "値段" in t:
        return "方針・規定", "購入・販売"
    if "返品" in t or "返金" in t:
        return "方針・規定", "返品・保証"
    if "修理" in t or "保証" in t:
        return "方針・規定", "修理・保証"
    if "碁盤" in t or "碁石" in t:
        return "仕様・機能", "ハードウェア仕様"
    if "Bluetooth" in t or "音声" in t or "音" in t:
        return "仕様・機能", "ハードウェア仕様"
    if "SRCCモード" in t or "囲碁将棋チャンネル" in t:
        return "仕様・機能", "サービス・コンテンツ"
    if "LINE" in t or "メール" in t or "連絡" in t:
        return "方針・規定", "お問い合わせ方法"
    return "その他", "一般"

# 難易度推定（タグ・タイトルから）
def infer_difficulty(title: str, tags: list[str]) -> str:
    combined = title + " ".join(tags)
    if any(k in combined for k in ["エスカレーション", "故障", "修理", "トラブル", "異常", "詳細", "仕様"]):
        return "hard"
    if any(k in combined for k in ["手順", "設定", "セットアップ", "ペアリング", "アップデート"]):
        return "medium"
    return "easy"

# answer_short: 回答の最初の200文字
def make_answer_short(answer: str) -> str:
    # 箇条書き記号や改行を除去して先頭200文字
    cleaned = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩]", "", answer)
    cleaned = re.sub(r"\n+", " ", cleaned).strip()
    return cleaned[:120] + "…" if len(cleaned) > 120 else cleaned

# embedding_text: question + tags + answer冒頭
def make_embedding_text(question: str, tags: list[str], answer: str) -> str:
    tag_str = " ".join(tags[:10])  # タグ上位10個
    # answerの最初の300文字
    answer_snippet = re.sub(r"\n+", " ", answer)[:300]
    return f"{question} {tag_str} {answer_snippet}"

# 参照マニュアル → source文字列
def parse_source(manual_str: str) -> str | None:
    if not manual_str or manual_str.strip() == "":
        return None
    # 複数行の場合は最初の1行
    first_line = manual_str.strip().split("\n")[0].strip()
    return first_line[:150] if first_line else None


def main():
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH}")
        sys.exit(1)

    items = []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header: No,問合せ内容,タグ,回答,参照マニュアル,テスト
        print(f"Header: {header}")

        for row in reader:
            if len(row) < 4:
                continue
            no_str = row[0].strip()
            if not no_str.isdigit():
                continue

            no = int(no_str)
            question = row[1].strip()
            tags_raw = row[2].strip() if len(row) > 2 else ""
            answer = row[3].strip() if len(row) > 3 else ""
            manual = row[4].strip() if len(row) > 4 else ""

            if not question or not answer:
                print(f"  Skip row {no}: missing question or answer")
                continue

            tags = parse_tags(tags_raw)
            category, subcategory = infer_category(question)
            difficulty = infer_difficulty(question, tags)
            source = parse_source(manual)
            answer_short = make_answer_short(answer)
            embedding_text = make_embedding_text(question, tags, answer)

            item = {
                "id": f"faq-{no:03d}",
                "type": "faq",
                "category": category,
                "subcategory": subcategory,
                "question": question,
                "answer": answer,
                "answer_short": answer_short,
                "related_terms": tags[:5],  # タグを related_terms として流用
                "related_faq_ids": [],
                "tags": tags,
                "difficulty": difficulty,
                "source": source,
                "verified_at": "2026-03-25",
                "embedding_text": embedding_text,
            }
            items.append(item)
            print(f"  [{no:02d}] {question[:40]}... → {category}/{subcategory}")

    output = {
        "version": "2.0.0",
        "updated_at": str(date.today()),
        "items": items,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone: {len(items)} items written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
