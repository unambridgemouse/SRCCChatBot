"""
SenseRobot 体験・購入店舗情報スクレイパー。
https://www.senserobot-jp.com/store からPlaywrightで最新情報を取得し、
1時間キャッシュする。
"""
import asyncio
import re
import time

from app.utils import get_logger

logger = get_logger(__name__)

STORE_URL = "https://www.senserobot-jp.com/store"
CACHE_TTL = 3600  # 1時間

_cache_text: str | None = None
_cache_time: float = 0.0

# 都道府県キーワード
PREFECTURES = [
    "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島",
    "茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川",
    "新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜", "静岡", "愛知",
    "三重", "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山",
    "鳥取", "島根", "岡山", "広島", "山口", "徳島", "香川", "愛媛", "高知",
    "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄",
]

# 店舗クエリを示すキーワード
_STORE_TRIGGER_WORDS = ["体験", "購入", "買え", "試せ", "買いたい"]
_LOCATION_WORDS = ["場所", "どこ", "店", "ショップ", "県", "都", "道", "府", "オンライン"]


def is_store_query(query: str) -> bool:
    """クエリが店舗検索かどうか判定する"""
    has_trigger = any(w in query for w in _STORE_TRIGGER_WORDS)
    if not has_trigger:
        return False
    has_location = any(w in query for w in _LOCATION_WORDS)
    has_prefecture = any(p in query for p in PREFECTURES)
    return has_location or has_prefecture


async def get_store_text() -> str:
    """
    店舗ページのテキストを返す。キャッシュが有効な場合はキャッシュを使用する。
    """
    global _cache_text, _cache_time

    if _cache_text and (time.time() - _cache_time) < CACHE_TTL:
        logger.info("Store cache hit")
        return _cache_text

    logger.info(f"Fetching store page: {STORE_URL}")
    text = await _fetch_with_playwright()
    text = _clean_text(text)

    _cache_text = text
    _cache_time = time.time()
    logger.info(f"Store page fetched: {len(text)} chars")
    return text


async def _fetch_with_playwright() -> str:
    """Playwright で動的レンダリングされたページのテキストを取得する"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright not available (Vercel environment). Store scraping disabled.")
        return "（店舗情報の自動取得はこの環境では利用できません。senserobot-jp.com/store をご確認ください。）"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(STORE_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)
            text = await page.inner_text("body")
        finally:
            await browser.close()
    return text


def _clean_text(text: str) -> str:
    """ゼロ幅スペース等の不要文字を除去し、テキストを整形する"""
    # ゼロ幅スペース・全角スペース除去
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    # 連続する空行を1行にまとめる
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 前後の空白除去
    text = text.strip()
    return text


def invalidate_cache() -> None:
    """キャッシュを強制的に無効化する"""
    global _cache_text, _cache_time
    _cache_text = None
    _cache_time = 0.0
