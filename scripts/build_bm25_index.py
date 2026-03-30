"""
BM25インデックスをPineconeとは独立して構築しPickleで保存。
make ingest または make build-bm25 で実行。
"""
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rank_bm25 import BM25Okapi
from app.utils.text_normalizer import tokenize_japanese


def load_documents(base: Path) -> list[dict]:
    docs = []

    faq_path = base / "data/faq/faq_master.json"
    with open(faq_path, encoding="utf-8") as f:
        faq_data = json.load(f)
    for item in faq_data.get("items", []):
        docs.append({
            "doc_id": item["id"],
            "type": "faq",
            "text": item["embedding_text"],
            "category": item.get("category", ""),
            "tags": item.get("tags", []),
            "source": item.get("source", ""),
        })

    glossary_path = base / "data/glossary/glossary_master.json"
    with open(glossary_path, encoding="utf-8") as f:
        glossary_data = json.load(f)
    for item in glossary_data.get("items", []):
        docs.append({
            "doc_id": item["id"],
            "type": "glossary",
            "text": item["embedding_text"],
            "category": item.get("category", ""),
            "tags": item.get("tags", []),
            "source": "",
        })

    return docs


def main():
    base = Path(__file__).parent.parent
    output_path = base / "data/bm25_index.pkl"

    print("Loading documents...")
    docs = load_documents(base)
    print(f"  {len(docs)} documents loaded (FAQ + Glossary)")

    print("Tokenizing...")
    tokenized_corpus = [tokenize_japanese(doc["text"]) for doc in docs]

    print("Building BM25 index...")
    bm25 = BM25Okapi(tokenized_corpus)

    print(f"Saving to {output_path} ...")
    with open(output_path, "wb") as f:
        pickle.dump((bm25, docs), f)

    print(f"BM25 index built successfully: {len(docs)} documents")


if __name__ == "__main__":
    main()
