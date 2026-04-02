"""
GET /api/logs  — クエリログ閲覧エンドポイント。
?limit=N  最大取得件数（デフォルト100、最大500）
?format=json  JSON返却（デフォルトはHTML表）
"""
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.context_manager import ConversationContextManager
from app.core.query_logger import get_query_logs

router = APIRouter()
_ctx: ConversationContextManager | None = None


def _get_ctx() -> ConversationContextManager:
    global _ctx
    if _ctx is None:
        _ctx = ConversationContextManager()
    return _ctx


@router.get("/api/logs")
async def logs(
    limit: int = Query(default=100, le=500),
    fmt: str = Query(default="html", alias="format"),
):
    entries = get_query_logs(_get_ctx().redis, limit=limit)

    if fmt == "json":
        return JSONResponse(content=entries)

    # ── HTML 表形式で返す ──
    rows = ""
    for e in entries:
        sources = ", ".join(s["id"] for s in e.get("sources", []))
        rows += f"""
        <tr>
          <td>{e.get('ts','')}</td>
          <td class="q">{_esc(e.get('query',''))}</td>
          <td class="a">{_esc(e.get('answer',''))}</td>
          <td>{_esc(sources)}</td>
          <td class="sid">{e.get('session_id','')[:8]}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>SRCCセンちゃんBot — クエリログ</title>
<style>
  body {{ font-family: sans-serif; font-size: 13px; padding: 16px; background:#f8f9fa; }}
  h1 {{ font-size: 18px; margin-bottom: 12px; }}
  p.meta {{ color: #666; margin-bottom: 12px; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; }}
  th {{ background: #1f4e79; color: #fff; padding: 8px 10px; text-align: left; position: sticky; top: 0; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
  tr:hover td {{ background: #eef4fb; }}
  .q  {{ max-width: 220px; font-weight: bold; }}
  .a  {{ max-width: 340px; color: #333; white-space: pre-wrap; }}
  .sid {{ color: #999; font-size: 11px; }}
  a {{ color: #1f4e79; }}
</style>
</head>
<body>
<h1>📋 SRCCセンちゃんBot — クエリログ</h1>
<p class="meta">直近 {len(entries)} 件を表示（最大 {limit} 件） ／
  <a href="?format=json&limit={limit}">JSONで見る</a></p>
<table>
  <thead><tr>
    <th>日時(JST)</th><th>クエリ</th><th>回答（先頭300字）</th>
    <th>参照ナレッジ</th><th>セッションID</th>
  </tr></thead>
  <tbody>{rows if rows else '<tr><td colspan="5" style="text-align:center;color:#999;">ログなし</td></tr>'}</tbody>
</table>
</body></html>"""

    return HTMLResponse(content=html)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
