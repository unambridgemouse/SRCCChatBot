/**
 * FastAPI バックエンドへのプロキシ。
 * SSE ストリームをそのままクライアントに転送する。
 */
import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    console.error("[proxy] fetch failed:", e);
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (!backendRes.ok) {
    const text = await backendRes.text();
    console.error("[proxy] backend error:", backendRes.status, text);
    return new Response(JSON.stringify({ error: "Backend error", detail: text }), {
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
