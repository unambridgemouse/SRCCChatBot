"""
プロンプトキャッシュ実装可否を判断するため、
SYSTEM_PROMPT_TEMPLATE の静的部分のトークン数を計測する。

目的:
  Sonnet 4.6 のキャッシュ最小要件 2048 トークンを満たすかを確認する。
  下回る場合、現行のテンプレ構造のままではキャッシュは効かない。

使い方:
  python scripts/measure_prompt_tokens.py
"""
import io
import sys
from pathlib import Path

# Windows cp932 でも UTF-8 で出力
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from app.config import get_settings
from app.core.prompt_builder import (
    SYSTEM_PROMPT_TEMPLATE,
    STORE_SYSTEM_PROMPT_TEMPLATE,
)


def split_static_prefix(template: str, first_dynamic_placeholder: str) -> tuple[str, str]:
    """テンプレを「最初の動的プレースホルダ直前」で2分割する。"""
    idx = template.index("{" + first_dynamic_placeholder + "}")
    # プレースホルダを含む行頭まで遡って分割（行の途中で切らないため）
    line_start = template.rfind("\n", 0, idx) + 1
    return template[:line_start], template[line_start:]


def count_tokens(client, model: str, system_text: str) -> int:
    """system のみのトークン数を測る（messages は最小ダミー）。"""
    resp = client.messages.count_tokens(
        model=model,
        system=system_text,
        messages=[{"role": "user", "content": "x"}],
    )
    # ダミーメッセージ "x" 分（数トークン）を引いた近似値を返したいが、
    # API は内訳を返さないので、別途ダミーのみのカウントを引く
    return resp.input_tokens


def main() -> None:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    sonnet = "claude-sonnet-4-6"
    minimum = 2048

    # ダミーのみ（system 空）の baseline を取って差し引く
    baseline = client.messages.count_tokens(
        model=sonnet,
        messages=[{"role": "user", "content": "x"}],
    ).input_tokens

    print(f"=== Token Count Measurement ===")
    print(f"Model      : {sonnet}")
    print(f"Min for cache: {minimum} tokens")
    print(f"Baseline (empty system + 'x'): {baseline} tokens")
    print()

    targets = [
        ("FAQ用 SYSTEM_PROMPT_TEMPLATE", SYSTEM_PROMPT_TEMPLATE, "conversation_history"),
        ("店舗用 STORE_SYSTEM_PROMPT_TEMPLATE", STORE_SYSTEM_PROMPT_TEMPLATE, "conversation_history"),
    ]

    for name, template, first_placeholder in targets:
        static, dynamic = split_static_prefix(template, first_placeholder)

        # 静的部分のみ（動的プレースホルダを取り除いた状態）のトークン数
        full_with_static = count_tokens(client, sonnet, static)
        static_tokens = full_with_static - baseline

        # 参考: 動的プレースホルダを空文字で埋めた完成形のトークン数
        filled_empty = template.format(
            conversation_history="（会話履歴なし）",
            retrieved_context="（検索結果なし）",
            extracted_entities="（専門用語なし）",
        ) if "extracted_entities" in template else template.format(
            conversation_history="（会話履歴なし）",
            store_text="（店舗データなし）",
        )
        full_filled = count_tokens(client, sonnet, filled_empty) - baseline

        verdict = "[OK] キャッシュ適格" if static_tokens >= minimum else "[NG] 最小要件未達 - 構造変更が必要"

        print(f"--- {name} ---")
        print(f"  静的接頭辞のみ      : {static_tokens:>5} トークン  {verdict}")
        print(f"  動的部分を空で充填  : {full_filled:>5} トークン  (参考)")
        print()


if __name__ == "__main__":
    main()
