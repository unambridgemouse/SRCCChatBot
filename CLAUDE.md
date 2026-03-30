# SRCC FAQ Bot - Claude Code Development Guide

## Project Overview
囲碁ロボット(SRCC)コールセンター向けRAGボット。
Dify標準RAGを超える3戦略を実装:
1. **Hybrid Search & Re-ranking** - BM25 + Vector + RRF + Cohere Rerank
2. **Entity-Focused Query Expansion** - 囲碁用語の直接照合・クエリ拡張
3. **Multi-turn Context Management** - Upstash Redis によるセッション管理

## Directory Layout
```
srcc-faq-bot/
├── app/
│   ├── main.py           # FastAPI エントリーポイント
│   ├── config.py         # 環境変数・定数（必ずここ経由でアクセス）
│   ├── api/              # エンドポイント定義
│   ├── core/             # RAGコアロジック
│   ├── models/           # Pydanticモデル
│   └── utils/            # ユーティリティ
├── data/
│   ├── faq/              # FAQ マスターデータ
│   └── glossary/         # 用語集マスターデータ
├── scripts/              # データ投入・管理スクリプト
├── tests/                # テスト
└── frontend/             # Next.js フロントエンド
```

## Critical Rules
- LLMへの直接呼び出しは `app/core/pipeline.py` 経由のみ
- プロンプト変更は `app/core/prompt_builder.py` のみで行う
- Pineconeへの書き込みは `scripts/ingest.py` 経由のみ（本番データ保護）
- 環境変数は必ず `app/config.py` の Settings クラス経由でアクセス
- 新しいFAQ/用語集は `data/` のJSONを編集後、`make ingest` で反映

## Commands
```bash
make dev        # ローカル起動 (http://localhost:8000)
make ingest     # Pinecone・BM25インデックス再構築
make validate   # data/ のJSONスキーマ検証
make test       # pytestフルスイート
make test-unit  # ユニットテストのみ
```

## Key Design Decisions
1. **BM25キャッシュ**: コールドスタート対策でPickleを `/tmp` にキャッシュ（Vercel対応）
2. **Cohereリランク**: 上位10件→3件に絞る（精度/コストバランス）
3. **Redisセッション**: キー `session:{session_id}` TTL=1800秒・最大5ターン保持
4. **モデル分離**: Entity抽出はHaiku（速度優先）、回答生成はSonnet（精度優先）
5. **streaming**: SSE (Server-Sent Events) でトークンをストリーミング配信

## Environment Variables (required)
```
ANTHROPIC_API_KEY       # Claude API
OPENAI_API_KEY          # text-embedding-3-small
PINECONE_API_KEY        # ベクトルDB
PINECONE_INDEX_NAME     # 例: srcc-faq
COHERE_API_KEY          # Re-ranking
UPSTASH_REDIS_REST_URL  # セッション管理
UPSTASH_REDIS_REST_TOKEN
```

## Data Update Workflow
1. `data/faq/faq_master.json` または `data/glossary/glossary_master.json` を編集
2. `make validate` でスキーマ確認
3. `make ingest` で差分をPinecone・BM25に反映
4. `make test` で回帰テスト

## Testing Checklist
- [ ] アタリ・コウ・シチョウ等の基本用語が正確に返るか
- [ ] 複数ターン会話で前の文脈を参照できるか
- [ ] 未知の質問に対して「情報なし」と回答するか（幻覚なし）
- [ ] SRCC固有機能の質問が一般囲碁FAQと混合しないか
