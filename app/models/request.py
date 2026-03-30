from pydantic import BaseModel, Field
import uuid


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="オペレーターの質問文")
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="会話セッションID。フロントエンドで生成・保持する",
    )
    metadata_filter: dict | None = Field(
        default=None,
        description="Pineconeメタデータフィルタ（例: {'category': '操作方法'}）",
    )
