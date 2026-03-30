"""
POST /api/chat エンドポイント。
Server-Sent Events (SSE) でトークンをストリーミング配信。
"""
import asyncio
import json
import anthropic
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.request import ChatRequest
from app.core.pipeline import RAGPipeline
from app.config import get_settings
from app.utils import get_logger

router = APIRouter()
logger = get_logger(__name__)

# シングルトン: コールドスタート後は再利用
_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


@router.post("/api/chat")
async def chat(req: ChatRequest):
    pipeline = get_pipeline()
    settings = get_settings()

    try:
        result = await pipeline.run(
            session_id=req.session_id,
            query=req.message,
            metadata_filter=req.metadata_filter,
        )
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    async def stream_response():
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        full_answer = []
        max_retries = 3
        for attempt in range(max_retries):
            full_answer = []
            try:
                async with client.messages.stream(
                    model=settings.llm_model,
                    max_tokens=1024,
                    system=result["system_prompt"],
                    messages=result["messages"],
                ) as stream:
                    async for text in stream.text_stream:
                        full_answer.append(text)
                        yield f"data: {json.dumps({'type': 'text', 'text': text}, ensure_ascii=False)}\n\n"

                # ストリーム完了: メタデータ（引用元・エンティティ）を最後に送信
                answer_text = "".join(full_answer)
                pipeline.save_turn(req.session_id, req.message, answer_text)

                metadata = {
                    "type": "done",
                    "sources": result["sources"],
                    "extracted_entities": result["extracted_entities"],
                    "expanded_query": result["expanded_query"],
                    "session_id": req.session_id,
                }
                if settings.debug_mode:
                    metadata["system_prompt"] = result["system_prompt"]
                yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
                return

            except anthropic.APIStatusError as e:
                if e.status_code == 529 and attempt < max_retries - 1:
                    wait = 10 * (attempt + 1)
                    logger.warning(f"Anthropic overloaded (attempt {attempt + 1}), retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': 'AIサービスが一時的に混雑しています。しばらくしてから再試行してください。'}, ensure_ascii=False)}\n\n"
                return
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
                return

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx バッファリング無効化
        },
    )
