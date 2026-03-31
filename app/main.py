import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.config import get_settings

# デバッグ: 環境変数が注入されているか確認
print("[DEBUG] PINECONE_API_KEY:", "SET" if os.environ.get("PINECONE_API_KEY") else "NOT SET")
print("[DEBUG] ANTHROPIC_API_KEY:", "SET" if os.environ.get("ANTHROPIC_API_KEY") else "NOT SET")
print("[DEBUG] COHERE_API_KEY:", "SET" if os.environ.get("COHERE_API_KEY") else "NOT SET")

settings = get_settings()

app = FastAPI(
    title="SRCC FAQ Bot",
    description="囲碁ロボット(SRCC) コールセンター用 FAQ・用語集ボット",
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(health_router)


@app.get("/")
async def root():
    return {"status": "ok"}

# AWS Lambda / Vercel Serverless 向けハンドラー
handler = Mangum(app, lifespan="off")
