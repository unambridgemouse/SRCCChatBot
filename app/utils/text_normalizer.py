import unicodedata
import re


def normalize(text: str) -> str:
    """
    全角英数字→半角、全角スペース→半角、カタカナ正規化を行う。
    日本語の検索クエリを正規化して検索精度を向上させる。
    """
    # Unicode正規化（NFKC: 全角→半角、結合文字の正規化）
    text = unicodedata.normalize("NFKC", text)
    # 連続スペースを1つに
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_japanese(text: str) -> list[str]:
    """
    BM25用の日本語トークナイザー。
    文字単位 + 2-gram で分割して専門用語のマッチ精度を上げる。
    """
    text = normalize(text)
    chars = list(text)
    bigrams = [text[i : i + 2] for i in range(len(text) - 1)]
    return chars + bigrams
