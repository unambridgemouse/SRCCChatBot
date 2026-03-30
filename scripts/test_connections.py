"""
各サービスへの接続テスト。
python scripts/test_connections.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(".env.local")

from app.config import get_settings
settings = get_settings()


def test_redis():
    print("\n[1/4] Upstash Redis...", end=" ")
    try:
        from upstash_redis import Redis
        r = Redis(url=settings.upstash_redis_rest_url, token=settings.upstash_redis_rest_token)
        r.set("srcc_test", "ok")
        val = r.get("srcc_test")
        r.delete("srcc_test")
        assert val == "ok"
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")


def test_cohere_embedding():
    print("[2/4] Cohere Embedding...", end=" ")
    try:
        import cohere
        co = cohere.Client(settings.cohere_api_key)
        resp = co.embed(
            texts=["テスト"],
            model=settings.embedding_model,
            input_type="search_document",
        )
        assert len(resp.embeddings[0]) == settings.embedding_dim
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")


def test_anthropic():
    print("[3/4] Anthropic Claude...", end=" ")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.fast_model,
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        assert resp.content[0].text
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")


def test_pinecone():
    print("[4/4] Pinecone...", end=" ")
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.pinecone_api_key)
        indexes = [i.name for i in pc.list_indexes()]
        print(f"OK (indexes: {indexes})")
    except Exception as e:
        print(f"FAILED: {e}")


if __name__ == "__main__":
    print("=== SRCC FAQ Bot 接続テスト ===")
    test_redis()
    test_cohere_embedding()
    test_anthropic()
    test_pinecone()
    print("\n完了。FAILED がなければ make ingest を実行できます。")
