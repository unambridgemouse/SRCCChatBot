"""
用語集_20260324.csv → data/glossary/glossary_master.json 変換スクリプト。
226件の囲碁用語をJSONスキーマに変換する。

Usage:
    cd C:/Users/hashiguchi/ClaudeProjects/srcc-faq-bot
    python scripts/convert_csv_to_glossary.py
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

CSV_PATH = Path("C:/Users/hashiguchi/Desktop/用語集_20260324.csv")
OUTPUT_PATH = Path(__file__).parent.parent / "data/glossary/glossary_master.json"


def parse_term_and_reading(raw: str) -> tuple[str, list[str]]:
    """'空き三角(あきさんかく)' → ('空き三角', ['あきさんかく'])"""
    m = re.match(r"^(.+?)\((.+?)\)\s*$", raw.strip())
    if m:
        term = m.group(1).strip()
        reading = m.group(2).strip()
        return term, [reading]
    return raw.strip(), []


def parse_tags(tag_str: str) -> list[str]:
    if not tag_str:
        return []
    return [t.strip() for t in re.split(r"[/／]", tag_str) if t.strip()]


def infer_difficulty(term: str, tags: list[str], definition: str) -> str:
    combined = term + " ".join(tags) + definition
    hard_keywords = ["コウ", "セキ", "劫", "シチョウ", "スソガカリ", "サバキ", "転換", "脅し",
                     "ヨセ", "ダメ詰まり", "欠け眼", "ツケ", "ナラビ", "カケ"]
    beginner_keywords = ["アゲハマ", "布石", "定石", "囲碁", "対局", "石", "地", "勝敗",
                         "陣地", "着手", "黒", "白", "ルール", "基本", "パス", "終局", "投了"]
    for k in hard_keywords:
        if k in combined:
            return "advanced"
    for k in beginner_keywords:
        if k in combined:
            return "beginner"
    return "intermediate"


def make_embedding_text(term: str, readings: list[str], tags: list[str], definition: str) -> str:
    reading_str = " ".join(readings)
    tag_str = " ".join(tags[:10])
    snippet = definition[:300]
    return f"{term} {reading_str} {tag_str} {snippet}"


def main():
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH}")
        sys.exit(1)

    items = []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        print(f"Header: {header}")

        for row in reader:
            if len(row) < 4:
                continue
            no_str = row[0].strip()
            if not no_str.isdigit():
                continue

            no = int(no_str)
            raw_term = row[1].strip()
            tags_raw = row[2].strip() if len(row) > 2 else ""
            definition = row[3].strip() if len(row) > 3 else ""

            if not raw_term or not definition:
                print(f"  Skip row {no}: missing term or definition")
                continue

            term, readings = parse_term_and_reading(raw_term)
            tags = parse_tags(tags_raw)
            difficulty = infer_difficulty(term, tags, definition)
            embedding_text = make_embedding_text(term, readings, tags, definition)

            # definition_for_operator: first sentence or up to 80 chars
            first_sentence = re.split(r"[。\n]", definition)[0].strip()
            definition_short = first_sentence[:80] + "…" if len(first_sentence) > 80 else first_sentence

            item = {
                "id": f"term-{no:03d}",
                "type": "glossary",
                "term": term,
                "term_variants": readings,
                "definition": definition,
                "definition_for_operator": definition_short,
                "related_terms": tags[:5],
                "related_faq_ids": [],
                "category": "囲碁用語",
                "difficulty_level": difficulty,
                "tags": tags,
                "srcc_specific": False,
                "source": "囲碁用語集.xlsx",
                "verified_at": "2026-03-24",
                "embedding_text": embedding_text,
            }
            items.append(item)
            print(f"  [{no:03d}] {term} → {difficulty}")

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
