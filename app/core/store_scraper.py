"""
SenseRobot 体験・購入店舗情報スクレイパー。
https://www.senserobot-jp.com/store から最新情報を取得し、
1時間キャッシュする。
"""
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
_EXPERIENCE_WORDS = ["体験", "試せ"]   # 「どこ」でも店舗フローへ
_BUY_WORDS = ["購入", "買え", "買いたい"]  # 具体的な場所指定がある場合のみ店舗フローへ
# 「どこ」は購入方法の質問（どこで買えますか）にも使われるため除外
_SPECIFIC_LOCATION_WORDS = ["場所", "店", "ショップ", "県", "都", "道", "府", "オンライン"]
_LOCATION_WORDS = ["場所", "どこ", "店", "ショップ", "県", "都", "道", "府", "オンライン"]


def is_store_query(query: str) -> bool:
    """クエリが店舗検索かどうか判定する。
    体験系（体験/試せ）はlocation指定があれば店舗フロー。
    購入系（購入/買え/買いたい）は「どこ」単体では購入方法の質問と区別できないため、
    都道府県名または具体的な場所指定（店/ショップ/場所など）がある場合のみ店舗フローへ。
    """
    has_prefecture = any(p in query for p in PREFECTURES)

    if any(w in query for w in _EXPERIENCE_WORDS):
        has_location = any(w in query for w in _LOCATION_WORDS)
        return has_location or has_prefecture

    if any(w in query for w in _BUY_WORDS):
        has_specific = any(w in query for w in _SPECIFIC_LOCATION_WORDS)
        return has_specific or has_prefecture

    return False


_FOLLOWUP_WORDS = ["はどう", "は？", "も教えて", "も同様", "市", "区"]
# 最寄り・近隣を聞くキーワード
_PROXIMITY_WORDS = ["近い", "近く", "最寄り", "一番近い", "近いのは", "近場"]
# 居住地・所在地を示すキーワード
_RESIDENCE_WORDS = ["住んでる", "住んでいる", "住む", "最寄", "在住", "近隣", "周辺", "付近", "近くに住"]


def is_store_followup(query: str, history: list[dict]) -> bool:
    """直近の会話に店舗検索コンテキストがある場合、地名・最寄り系フォローアップを検出する"""
    if not history:
        return False

    # 直近6ターン（3往復）を確認
    recent = history[-6:]
    had_store_context = False

    for h in recent:
        # ユーザーターンが store_query だった
        if h["role"] == "user" and is_store_query(h["content"]):
            had_store_context = True
            break
        # アシスタントが店舗一覧を返していた（表形式 or store URL）
        if h["role"] == "assistant" and (
            "体験・購入" in h["content"]
            or "senserobot-jp.com/store" in h["content"]
            or "体験/購入" in h["content"]
        ):
            had_store_context = True
            break

    if not had_store_context:
        return False

    has_location = (
        any(p in query for p in PREFECTURES)
        or any(w in query for w in _FOLLOWUP_WORDS)
        or any(w in query for w in _PROXIMITY_WORDS)
        or any(w in query for w in _RESIDENCE_WORDS)
    )
    return has_location


async def get_store_text() -> str:
    """
    店舗ページのテキストを返す。キャッシュが有効な場合はキャッシュを使用する。
    """
    global _cache_text, _cache_time

    if _cache_text and (time.time() - _cache_time) < CACHE_TTL:
        logger.info("Store cache hit")
        return _cache_text

    logger.info(f"Fetching store page: {STORE_URL}")
    text = await _fetch_with_httpx()
    text = _clean_text(text)

    _cache_text = text
    _cache_time = time.time()
    logger.info(f"Store page fetched: {len(text)} chars")
    return text


async def _fetch_with_httpx() -> str:
    """httpx + BeautifulSoup でページのテキストを取得する"""
    import httpx
    from bs4 import BeautifulSoup

    headers = {"User-Agent": "Mozilla/5.0 (compatible; SRCCBot/1.0)"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        resp = await client.get(STORE_URL, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator="\n")


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
