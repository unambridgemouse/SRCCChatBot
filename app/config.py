import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from dotenv import load_dotenv

# ローカル環境では .env.local を読み込む（Railway では無視される）
load_dotenv(".env.local", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # Anthropic
    anthropic_api_key: str

    # OpenAI (embedding) - Cohere切り替え後は不要
    openai_api_key: str | None = None

    # Pinecone
    pinecone_api_key: str
    pinecone_index_name: str = "srcc-faq"

    # Cohere
    cohere_api_key: str

    # Upstash Redis
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str

    # App
    app_env: str = "development"
    allowed_origins: str = "*"  # 本番では "https://xxx.vercel.app" を設定
    log_level: str = "INFO"
    debug_mode: bool = False  # True のとき system_prompt をレスポンスに含める
    max_search_results: int = 10
    rerank_top_n: int = 7
    session_ttl_seconds: int = 1800
    max_conversation_turns: int = 5

    # Paths
    faq_data_path: str = "data/faq/faq_master.json"
    glossary_data_path: str = "data/glossary/glossary_master.json"
    bm25_cache_path: str = "/tmp/bm25_index.pkl"

    # Models
    embedding_model: str = "embed-multilingual-v3.0"  # Cohere
    embedding_dim: int = 1024                          # Cohere embed-multilingual-v3.0
    llm_model: str = "claude-sonnet-4-6"
    fast_model: str = "claude-haiku-4-5-20251001"
    rerank_model: str = "rerank-multilingual-v3.0"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        pinecone_api_key=os.environ.get("PINECONE_API_KEY", ""),
        cohere_api_key=os.environ.get("COHERE_API_KEY", ""),
        upstash_redis_rest_url=os.environ.get("UPSTASH_REDIS_REST_URL", ""),
        upstash_redis_rest_token=os.environ.get("UPSTASH_REDIS_REST_TOKEN", ""),
    )
