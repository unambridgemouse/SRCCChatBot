# SRCCセンちゃんBot — ディレクトリ構成

> 作成: 2026-04-02

---

## ルート構成

```
srcc-faq-bot/
├── app/                    # FastAPI バックエンド本体
├── frontend/               # Next.js フロントエンド
├── data/                   # ナレッジデータ（FAQ・用語集・インデックス）
├── scripts/                # データ管理・運用スクリプト
├── tests/                  # テスト
├── docs/                   # Obsidian ドキュメント（仕様書・変更履歴）
├── .obsidian/              # Obsidian設定（Vaultルート = プロジェクトルート）
├── Makefile                # 開発コマンド定義
├── Procfile                # Railway 起動定義（参照のみ、railway.tomlが優先）
├── railway.toml            # Railway デプロイ設定
├── vercel.json             # Vercel デプロイ設定
├── requirements.txt        # Python依存パッケージ
├── pyproject.toml          # Pythonプロジェクト設定
├── CLAUDE.md               # Claude Code向け開発ガイド（AIへの指示）
├── .env.local              # ローカル環境変数（Git管理外）
└── .env.example            # 環境変数のテンプレート
```

---

## app/ — FastAPIバックエンド

```
app/
├── main.py           # FastAPIアプリ本体・ミドルウェア・ルーター登録
├── config.py         # 環境変数定義（Settings クラス）
├── api/              # エンドポイント定義
│   ├── chat.py       # POST /api/chat（メインチャット・SSEストリーム）
│   ├── health.py     # GET /api/health（ヘルスチェック）
│   └── logs.py       # GET /api/logs（クエリログ閲覧）
├── core/             # RAGコアロジック
│   ├── pipeline.py         # RAGパイプライン統合（全フローの司令塔）
│   ├── hybrid_search.py    # BM25 + Pinecone + RRF + Cohere Rerank
│   ├── entity_extractor.py # 用語抽出・クエリ拡張（Claude Haiku使用）
│   ├── prompt_builder.py   # システムプロンプト組み立て（変更はここのみ）
│   ├── context_manager.py  # Upstash Redis セッション管理
│   ├── query_logger.py     # クエリログ保存（stdout + Redis）
│   └── store_scraper.py    # senserobot-jp.com/store スクレイピング
├── models/           # Pydanticモデル定義
│   ├── request.py    # ChatRequest（message, session_id, metadata_filter）
│   └── response.py   # SourceItem（doc_id, type, title, score, source）
└── utils/            # ユーティリティ
    ├── __init__.py         # get_logger, normalize, tokenize_japanese をエクスポート
    ├── logger.py           # structlog ベースのロガー設定
    └── text_normalizer.py  # テキスト正規化・日本語バイグラムトークナイザ
```

### 各ファイルの役割詳細

#### app/main.py
- FastAPIアプリのエントリーポイント
- CORSミドルウェア設定（`ALLOWED_ORIGINS` 環境変数から読み込み）
- 3つのルーター（chat, health, logs）を登録
- `docs_url` は development環境のみ有効
- `handler = Mangum(app)` — AWS Lambda / Vercel Serverless対応（現在は未使用だが互換性のため）

#### app/config.py
- `Settings` クラス（pydantic-settings）で全環境変数を型安全に管理
- `@lru_cache` でシングルトン化（`get_settings()` 経由でアクセス）
- 重要な設定値:
  - `llm_model`: claude-sonnet-4-6（回答生成）
  - `fast_model`: claude-haiku-4-5-20251001（Entity抽出）
  - `max_search_results`: 10、`rerank_top_n`: 7
  - `session_ttl_seconds`: 1800、`max_conversation_turns`: 5

#### app/api/chat.py
- `_pipeline` をモジュールグローバルでシングルトン管理（コールドスタート後は再利用）
- RAGパイプライン実行 → SSEジェネレーター `stream_response()` でストリーミング
- Anthropic過負荷（status 529）時は最大3回リトライ（10/20/30秒待機）
- ストリーム完了後: `pipeline.save_turn()` → `save_query_log()` の順で実行

#### app/core/pipeline.py
- **RAGパイプラインの司令塔**。全フローはここを経由する
- `is_store_query()` または `is_store_followup()` が True → `_run_store_query()` で専用フロー
- 通常フロー: EntityExtractor → HybridSearcher → `_append_related_faqs()` → PromptBuilder
- `_append_related_faqs()`: 取得FAQの `related_faq_ids` に含まれるFAQをスコアそのままで補完
- `save_turn()`: 回答確定後にRedisセッションへ保存

#### app/core/hybrid_search.py
- `HybridSearcher`: Pinecone（ベクトル）+ BM25（キーワード）のハイブリッド
- `_reciprocal_rank_fusion()`: `score = Σ(1 / (60 + rank))` でリストを統合
- `_cohere_rerank()`: Cohere rerank-multilingual-v3.0 で最終絞り込み
- BM25インデックスは `/tmp/bm25_index.pkl` にキャッシュ（Railway コールドスタート対策）
- `SearchNode` データクラス: `doc_id, text, metadata, score` + LlamaIndex互換インターフェース

#### app/core/entity_extractor.py
- Claude Haiku で質問から囲碁/SRCC用語を JSON配列で抽出
- 用語集（glossary_master.json）と直接照合（ベクトル検索を経由しない）
- 照合成功 → `definition_for_operator` + `related_terms` をプロンプトに挿入
- `related_terms` でクエリを拡張（最大5件追加）→ HybridSearcherに渡す
- LLM失敗時フォールバック: 既知用語の部分一致で代替

#### app/core/prompt_builder.py
- **プロンプトの変更は必ずこのファイルのみで行う**
- 3つのテンプレート:
  - `SYSTEM_PROMPT_TEMPLATE`: 通常FAQ回答用
  - `STORE_SYSTEM_PROMPT_TEMPLATE`: 店舗検索用
  - `ENTITY_EXTRACTION_PROMPT`: 用語抽出用（Haiku向け）
- 重要なプロンプトルール（SYSTEM_PROMPT_TEMPLATE内）:
  - オペレーター向け文体（お客様に直接語りかけない）
  - エラーメッセージ名が完全一致するFAQのみ使用（複数FAQ混合禁止）
  - 伊藤電機へ「直接連絡ください」案内禁止
  - エスカレーション時のヒアリング項目（4パターン）

#### app/core/context_manager.py
- Upstash Redis（REST API）でセッション管理
- キー: `session:{session_id}` / TTL: 1800秒
- アシスタント回答は先頭500文字でRedis保存、プロンプト挿入時は先頭200文字
- 直近 `max_conversation_turns * 2` 件のみ保持

#### app/core/query_logger.py
- 各チャットのクエリ・回答・参照ナレッジ・思考回路をログ保存
- Railway stdout: `[QUERY_LOG]` タグ付きJSON（Railway Logsで検索可能）
- Upstash Redis: `query_log` キー、LPUSH + LTRIM（最大500件）
- ログフィールド: ts, ts_unix, session_id, query, expanded_query, answer[:300], sources, system_prompt

#### app/core/store_scraper.py
- `get_store_text()`: senserobot-jp.com/store をスクレイピングして店舗リスト取得
- `is_store_query()`: 体験・購入・場所関連ワードを含むか判定
- `is_store_followup()`: 直近6ターンのuser/assistant両ターンで店舗コンテキストがあり、かつ地名・近接ワードを含むか判定

---

## frontend/ — Next.js フロントエンド

```
frontend/
├── app/
│   ├── layout.tsx          # ルートレイアウト（タイトル・フォント設定）
│   ├── page.tsx            # メインページ（セッション管理・サイドバー・チャット配置）
│   ├── globals.css         # グローバルスタイル
│   └── api/
│       └── chat/
│           └── route.ts    # バックエンドへのSSEプロキシ（Next.js Route Handler）
├── components/
│   ├── ChatWindow.tsx      # チャットUI本体（入力・送信・SSE受信・メッセージ表示）
│   ├── MessageBubble.tsx   # メッセージ表示（マークダウンレンダリング含む）
│   ├── RobotAvatar.tsx     # SVGロボットアバター（isTalking で口が動く）
│   ├── Sidebar.tsx         # セッション一覧・新規チャット（localStorage管理）
│   ├── SourceCitation.tsx  # 参照ナレッジ表示
│   └── DebugPanel.tsx      # デバッグ情報表示（system_prompt・expanded_query等）
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

### 各ファイルの役割詳細

#### frontend/app/page.tsx
- セッションID管理（`crypto.randomUUID()`）
- localStorage でセッション履歴を永続化
- Sidebar + ChatWindow を配置
- 「SRCCセンちゃんBot」タイトル・「センスロボットコールセンターサポートシステム」サブタイトル

#### frontend/app/api/chat/route.ts
- Next.js Route Handler でバックエンドへのプロキシ実装
- `BACKEND_URL` 環境変数（Vercel Variables）からRailway URLを取得
- SSEストリームをそのままクライアントに転送
- バックエンドURLをクライアントから隠蔽（セキュリティ）

#### frontend/components/ChatWindow.tsx
- SSE受信ループ: `EventSource` ではなく `fetch` + `ReadableStream` + `TextDecoder` で実装
- `isStreaming: true` で文字が逐次表示 → `done` イベントで `isStreaming: false` + メタデータ付与
- ロボットアバターエリア背景: 碁盤CSS（repeating-linear-gradient）
- 「ご質問をどうぞ」テキスト: white + text-shadow（碁盤背景で視認性確保）

#### frontend/components/MessageBubble.tsx
- `renderInline()` でマークダウンをReact要素に変換:
  - `**text**` → `<strong>`
  - `[text](https://...)` → `<a target="_blank" rel="noopener noreferrer">`
- 行ごとに `renderLine()` → 箇条書き・番号付きリスト・段落をレンダリング

#### frontend/components/RobotAvatar.tsx
- SVGベースのロボット顔
- `isTalking` prop で口のアニメーション制御
- コンテナ: `borderRadius: "22px"` + `overflow: "hidden"` + `boxShadow`（border-radiusでクリップ）

#### frontend/components/Sidebar.tsx
- セッション一覧をlocalStorageに保存・表示
- 「新規チャット」ボタンでセッションID生成

---

## data/ — ナレッジデータ

```
data/
├── faq/
│   └── faq_master.json      # FAQ本体（83件）
├── glossary/
│   └── glossary_master.json # 用語集（226件）
├── bm25_index.pkl           # BM25インデックス（make ingest で生成）
└── excel/                   # Excelエクスポート（.gitignore対象）
    └── srcc_knowledge_YYYYMMDD_HHMMSS.xlsx
```

### faq_master.json の構造

```json
{
  "version": "1.0",
  "items": [
    {
      "id": "faq-001",
      "question": "...",
      "answer": "...",
      "embedding_text": "...",
      "related_faq_ids": ["faq-002"],
      "tags": ["操作"],
      "type": "faq"
    }
  ]
}
```

**embedding_text** はPineconeとBM25のインデックスに使用するテキスト。
questionと異なる内容にすることで、曖昧な検索クエリに対する取得精度を制御できる。

### glossary_master.json の構造

```json
{
  "version": "1.0",
  "items": [
    {
      "id": "g-001",
      "term": "アタリ",
      "term_variants": ["あたり"],
      "definition_for_operator": "...",
      "related_terms": ["コウ"],
      "embedding_text": "...",
      "type": "glossary"
    }
  ]
}
```

---

## scripts/ — 運用スクリプト

```
scripts/
├── ingest.py             # Pinecone + BM25 インデックス再構築（make ingest）
├── build_bm25_index.py   # BM25インデックスのみ再構築
├── validate_data.py      # data/ JSONスキーマ検証（make validate）
├── export_to_excel.py    # FAQ + 用語集 → Excel出力（data/excel/）
├── install_hooks.py      # Git post-commit フック設定
│                         # （faq_master.json/glossary_master.json変更時に自動Excel出力）
├── convert_csv_to_faq.py     # CSV → faq_master.json 変換
├── convert_csv_to_glossary.py # CSV → glossary_master.json 変換
└── test_connections.py   # 外部サービス（Pinecone/Cohere/Redis）疎通確認
```

### ingest.py の動作

1. Pineconeインデックスが存在しなければ作成（cosine / 1024次元 / AWS us-east-1）
2. `embedding_text` フィールドをCohereでバッチ埋め込み（96件/バッチ）
3. Pineconeにupsert（idが同じベクトルは上書き）
4. BM25インデックスを再生成 → `data/bm25_index.pkl` に保存

### export_to_excel.py の動作

- 3シート構成: サマリー / FAQ（83件）/ 用語集（226件）
- ヘッダースタイル付き（openpyxl）
- 出力先: `data/excel/srcc_knowledge_YYYYMMDD_HHMMSS.xlsx`
- post-commitフックで自動実行（`scripts/install_hooks.py` でフック設定）

---

## tests/ — テスト

```
tests/
├── unit/
│   ├── test_context_manager.py   # Redisセッション管理のユニットテスト
│   ├── test_entity_extractor.py  # 用語抽出のユニットテスト
│   └── test_hybrid_search.py     # ハイブリッド検索のユニットテスト
└── integration/
    └── （統合テスト用・現在は空）
```

---

## docs/ — Obsidianドキュメント

```
docs/
├── SPEC.md             # システム仕様書
├── STRUCTURE.md        # ディレクトリ構成（このファイル）
├── CHANGELOG.md        # バージョン変更履歴
├── LEGACY_LOG.md       # 開発経緯・旧システムからの移行ログ
└── ようこそ.md         # Obsidianデフォルトファイル
```

ObsidianのVaultルートはプロジェクトルート（srcc-faq-bot/）に設定する。
`.obsidian/` フォルダがプロジェクトルートに配置されている。

---

## 設定ファイル

| ファイル | 用途 |
|---------|------|
| `railway.toml` | Railway デプロイ設定（起動コマンド・ヘルスチェック） |
| `vercel.json` | Vercel デプロイ設定（frontend/ をルートにマップ） |
| `Procfile` | Heroku互換形式（参照のみ。railway.tomlが優先） |
| `Makefile` | `make dev/ingest/validate/test` コマンド定義 |
| `pyproject.toml` | Pythonパッケージ設定（pip install -e ".[dev]"） |
| `requirements.txt` | 本番用Pythonパッケージ一覧 |
| `CLAUDE.md` | Claude Code（AI）向けの開発ルール・ガイド |
| `.env.local` | ローカル環境変数（Git管理外・本番は Railway Variables） |
| `.env.example` | 環境変数のテンプレート（Git管理） |
