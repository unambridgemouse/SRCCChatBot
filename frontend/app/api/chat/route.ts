/**
 * FastAPI バックエンドへのプロキシ。
 * SSE ストリームをそのままクライアントに転送する。
 */
import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();

  const backendRes = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!backendRes.ok) {
    return new Response(JSON.stringify({ error: "Backend error" }), {
      status: backendRes.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  // SSE ストリームをそのまま転送
  return new Response(backendRes.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
