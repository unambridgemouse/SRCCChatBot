"""
FAQデータ・用語集をPineconeへ投入するスクリプト。
make ingest で実行。冪等（既存データはupsert）。

Cohere trial key: 40 calls/min
→ バッチ埋め込み（最大96件/回）で呼び出し回数を最小化。
  77件FAQは1回、10件用語集も1回で完了。

Usage:
    python scripts/ingest.py --mode=full    # 全件投入
    python scripts/ingest.py --mode=faq     # FAQのみ
    python scripts/ingest.py --mode=glossary # 用語集のみ
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(".env.local")

import cohere
from pinecone import Pinecone, ServerlessSpec
from app.config import get_settings

# Cohereバッチサイズ上限
COHERE_BATCH_SIZE = 96
# Pineconeアップサート単位
PINECONE_BATCH_SIZE = 100


def embed_batch(co: cohere.Client, texts: list[str], model: str) -> list[list[float]]:
    """Cohereのバッチ埋め込み。COHERE_BATCH_SIZE 件ずつ分割して呼び出す。"""
    all_embeddings = []
    for i in range(0, len(texts), COHERE_BATCH_SIZE):
        chunk = texts[i:i + COHERE_BATCH_SIZE]
        resp = co.embed(
            texts=chunk,
            model=model,
            input_type="search_document",
        )
        all_embeddings.extend(resp.embeddings)
        if i + COHERE_BATCH_SIZE < len(texts):
            # 次バッチまで少し待機（レート制限対策）
            time.sleep(2)
    return all_embeddings


def embed_and_upsert(index, co: cohere.Client, model: str, items: list[dict], label: str):
    print(f"\n[{label}] {len(items)} items to upsert...")

    texts = [item["embedding_text"] for item in items]
    print(f"  Embedding {len(texts)} texts in batches of {COHERE_BATCH_SIZE}...")
    embeddings = embed_batch(co, texts, model)
    print(f"  Embedding done.")

    vectors = []
    for i, (item, embedding) in enumerate(zip(items, embeddings)):
        metadata = {k: v for k, v in item.items()
                    if k != "embedding_text" and isinstance(v, (str, int, float, bool, list))}
        # Pineconeはlist[str]のみサポート
        for k, v in metadata.items():
            if isinstance(v, list):
                metadata[k] = [str(x) for x in v]
        vectors.append({
            "id": item["id"],
            "values": embedding,
            "metadata": {**metadata, "text": item["embedding_text"]},
        })

        if len(vectors) >= PINECONE_BATCH_SIZE:
            index.upsert(vectors=vectors)
            print(f"  Upserted {i + 1}/{len(items)}...")
            vectors = []

    if vectors:
        index.upsert(vectors=vectors)

    print(f"[{label}] Done.")


def main(mode: str):
    settings = get_settings()

    # Pineconeクライアント初期化
    pc = Pinecone(api_key=settings.pinecone_api_key)

    # インデックスが存在しなければ作成
    existing = [idx.name for idx in pc.list_indexes()]
    if settings.pinecone_index_name not in existing:
        print(f"Creating Pinecone index: {settings.pinecone_index_name}")
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.embedding_dim,  # Cohere embed-multilingual-v3.0 = 1024
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    else:
        print(f"Using existing Pinecone index: {settings.pinecone_index_name}")

    pinecone_index = pc.Index(settings.pinecone_index_name)
    co = cohere.Client(settings.cohere_api_key)

    base = Path(__file__).parent.parent

    if mode in ("full", "faq"):
        faq_path = base / "data/faq/faq_master.json"
        with open(faq_path, encoding="utf-8") as f:
            faq_data = json.load(f)
        embed_and_upsert(pinecone_index, co, settings.embedding_model, faq_data["items"], "FAQ")

    if mode in ("full", "glossary"):
        glossary_path = base / "data/glossary/glossary_master.json"
        with open(glossary_path, encoding="utf-8") as f:
            glossary_data = json.load(f)
        embed_and_upsert(pinecone_index, co, settings.embedding_model, glossary_data["items"], "Glossary")

    print("\nIngest complete.")
    stats = pinecone_index.describe_index_stats()
    print(f"Total vectors in index: {stats.total_vector_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "faq", "glossary"], default="full")
    args = parser.parse_args()
    main(args.mode)
