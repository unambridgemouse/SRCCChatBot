# SRCCセンちゃんBot — システム仕様書

> 作成: 2026-04-02 / 更新: 随時

---

## 1. プロジェクト概要

| 項目 | 内容 |
|------|------|
| システム名 | SRCCセンちゃんBot |
| 用途 | 囲碁ロボット（SenseRobot）コールセンター向けRAGチャットボット |
| 利用者 | SRCCオペレーター（一般消費者には非公開） |
| バックエンド URL | https://srccchatbot-6636669301ad.up.railway.app |
| フロントエンド URL | https://srcc-chat-bot-m7j6.vercel.app |
| ログ閲覧 URL | https://srccchatbot-6636669301ad.up.railway.app/api/logs |
| GitHub | https://github.com/unambridgemouse/SRCCChatBot |

### 基礎知識
- **センちゃん**：囲碁ロボット（SenseRobot）の愛称
- **SRCC**：センスロボットコールセンターの略称
- **センスタイム社**：ロボットのメーカー（中国企業）
- **伊藤電機**：日本販売代理店（メーカーではない・修理・販売窓口）

---

## 2. アーキテクチャ全体図

```
オペレーター
    │ ブラウザ
    ▼
┌─────────────────────────────┐
│  Next.js フロントエンド      │  Vercel
│  (frontend/)                │
│  ・チャット UI               │
│  ・SSE ストリーム受信         │
│  ・セッション管理（localStorage）│
└──────────┬──────────────────┘
           │ POST /api/chat (プロキシ)
           ▼
┌─────────────────────────────┐
│  FastAPI バックエンド        │  Railway
│  (app/)                     │
│                             │
│  RAGパイプライン             │
│  1. EntityExtractor         │──→ Claude Haiku（用語抽出）
│  2. HybridSearcher          │──→ BM25 + Pinecone + RRF + Cohere Rerank
│  3. PromptBuilder           │
│  4. Claude Sonnet（回答生成）│──→ SSEストリーム
│  5. QueryLogger             │──→ Upstash Redis + Railway stdout
└─────────────────────────────┘
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
Pinecone  Cohere  Upstash Redis
(Vector)  (Embed  (セッション
          +Rerank) +クエリログ)
```

---

## 3. 主要機能

### 3-1. RAGパイプライン（Hybrid Search & Re-ranking）

通常の質問に対するメインフロー：

```
クエリ
 │
 ├─[1] EntityExtractor（Claude Haiku）
 │      └── 囲碁・SRCC用語を抽出 → 用語集で定義取得 → クエリ拡張
 │
 ├─[2] HybridSearcher
 │      ├── BM25（キーワード検索）: 文字バイグラムトークナイズ
 │      ├── Pinecone（ベクトル検索）: Cohere embed-multilingual-v3.0
 │      ├── RRF（Reciprocal Rank Fusion）: 両リストをスコアで統合
 │      └── Cohere Rerank: 上位10件→7件に精度絞り込み
 │
 ├─[3] related_faq_ids補完
 │      └── 取得ナレッジのrelated_faq_idsに含まれる関連FAQを自動追加
 │
 ├─[4] PromptBuilder
 │      └── システムプロンプト組み立て（会話履歴+検索結果+用語定義）
 │
 └─[5] Claude Sonnet 4.6（回答生成・SSEストリーミング）
```

**設定値**

| パラメータ                | 値                               |
| -------------------- | ------------------------------- |
| `max_search_results` | 10（BM25・Vector各上位10件）           |
| `rerank_top_n`       | 7                               |
| Entity抽出モデル          | claude-haiku-4-5-20251001       |
| 回答生成モデル              | claude-sonnet-4-6               |
| Embeddingモデル         | embed-multilingual-v3.0（1024次元） |
| Rerankモデル            | rerank-multilingual-v3.0        |
| SSE max_tokens       | 4096                            |
| Anthropic過負荷時リトライ    | 最大3回（10秒・20秒・30秒待機）             |

### 3-2. 店舗検索フロー（Store Scraper）

「体験・購入場所を知りたい」クエリは専用フローで処理：

```
is_store_query(query) or is_store_followup(query, history)
 │
 ├── senserobot-jp.com/store をスクレイピング（httpx + BeautifulSoup）
 │   └── インメモリキャッシュ 1時間（CACHE_TTL=3600秒）
 ├── 専用プロンプト（STORE_SYSTEM_PROMPT_TEMPLATE）で組み立て
 └── 体験/購入・都道府県別に案内

フォールバック（該当なし）:
  体験目的 → ①近隣県体験店 → ②Rentio → ③伊藤電機エスカレ
  購入目的 → ①近隣県購入店（表形式・近い順1〜3件）
           + ②伊藤電機直販(145,000円/165,000円)・Amazon を必ず付記
           ③ 近隣県にも購入店なし → 伊藤電機直販・Amazonのみ案内
```

**`is_store_query()` 判定ロジック（体験系と購入系で別ルール）**

| クエリ種別 | トリガーワード | 店舗フロー適用条件 |
|---|---|---|
| 体験系 | `体験` `試せ` | 場所ワード（どこ/場所/店/県 等）または都道府県名を含む |
| 購入系 | `購入` `買え` `買いたい` | 都道府県名 または 具体的場所指定（場所/店/ショップ/県 等）を含む |

> **注意**: 「どこで買えますか」のような購入方法の質問と区別するため、購入系は「どこ」単体では店舗フローへ進まない。

**`is_store_followup()`**：直近6ターン（3往復）のuser/assistant両方のhistoryを検索し、
店舗コンテキスト（過去ユーザーターンがstore_query、またはアシスタント回答に「体験・購入」や `senserobot-jp.com/store` URLを含む）があれば、
地名・最寄り・近接ワード（近い/近く/最寄り/住んでいる 等）のみのフォローアップクエリも店舗フローで処理する。

### 3-3. セッション管理（Multi-turn Context）

- **ストレージ**: Upstash Redis（REST API）
- **キー形式**: `session:{session_id}`
- **TTL**: 1800秒（30分）
- **最大ターン数**: 5ターン（10メッセージ）保持
- **保存形式**: アシスタント回答は先頭500文字でRedisに保存、プロンプト挿入時は先頭200文字

### 3-4. クエリログ

各チャットの記録を2箇所に保存：

| 保存先 | 内容 |
|--------|------|
| Railway stdout | `[QUERY_LOG] {JSON}` タグ付き構造化ログ |
| Upstash Redis | キー `query_log`（LPUSH/LTRIM、最大500件） |

**ログに含まれるフィールド**

| フィールド | 説明 |
|------------|------|
| `ts` | 日時（JST） |
| `session_id` | セッションID |
| `query` | オペレーターのクエリ |
| `expanded_query` | エンティティ抽出後の拡張クエリ |
| `answer` | 回答（先頭300文字） |
| `sources` | 参照ナレッジID・スコア |
| `system_prompt` | 思考回路（注入されたFAQ・ルール全文） |

**ログ閲覧**: `GET /api/logs`（HTML表形式）、`?format=json`、`?limit=N`

### 3-5. SSEストリーミング

```
フロントエンド           バックエンド
    │                      │
    │── POST /api/chat ──→  │
    │                      │ RAGパイプライン実行
    │ ←── data: {"type": "text", "text": "..."} ─── (トークン逐次)
    │ ←── data: {"type": "text", "text": "..."} ───
    │ ←── data: {"type": "done", "sources": [...], "extracted_entities": [...]} ───
    │
フロントエンドでSSE解析 → 文字列を逐次表示（isStreaming=true）
                         → "done"受信でメタデータ付与・localStorage保存
```

### 3-6. マークダウンレンダリング

MessageBubble.tsx の `renderInline()` で独自パース：
- `**text**` → `<strong>`
- `[text](https://...)` → `<a href="..." target="_blank">`
- `①②...` → そのまま表示（UTF-8囲み数字）

---

## 4. ナレッジ構成

### FAQ（data/faq/faq_master.json）

- **件数**: 81件（faq-001〜faq-081）
- **主なカテゴリ**: 操作・トラブル・バージョン確認・囲碁ルール・対局設定・店舗・価格

**JSONスキーマ**

```json
{
  "id": "faq-001",
  "question": "...",
  "answer": "...",
  "embedding_text": "...",   // ベクトル検索用テキスト（questionと異なる場合あり）
  "related_faq_ids": ["faq-002"],
  "tags": ["操作", "トラブル"],
  "metadata_filter": {}
}
```

`embedding_text`は曖昧さ排除のため、FAQによっては`question`と意図的に異なる内容にしている（例：faq-019/faq-053の「異常」系FAQ）。

### 用語集（data/glossary/glossary_master.json）

- **件数**: 226件
- **用途**: EntityExtractorが用語定義をプロンプトに直接注入

**JSONスキーマ**

```json
{
  "id": "g-001",
  "term": "アタリ",
  "term_variants": ["あたり"],
  "definition_for_operator": "...",
  "related_terms": ["コウ", "シチョウ"],
  "embedding_text": "..."
}
```

### BM25インデックス（data/bm25_index.pkl）

- FAQ・用語集のテキストを文字バイグラムでトークナイズしPickleシリアライズ
- 本番（Railway）では `/tmp/bm25_index.pkl` にキャッシュ（コールドスタート対策）
- 更新: `make ingest` で再生成

---

## 5. ナレッジ更新ワークフロー

```
1. data/faq/faq_master.json または data/glossary/glossary_master.json を編集
2. make validate     # JSONスキーマ検証
3. make ingest       # Pinecone + BM25 再構築（差分upsert）
4. git commit + push # Railwayに自動デプロイ
                     # ※ post-commitフックでExcelも自動出力（data/excel/）
```

**注意**: JSONを手動編集する場合は必ず `make validate` でスキーマ確認してからingest。
壊れたJSONをingestするとPineconeの内容と乖離が生じる。

### 単発パッチスクリプト（_patch_version_check.py）

プロジェクトルートに `_patch_version_check.py` が存在する。
複数のFAQ（faq-004/005/014/019/023/024/027/028/030/039/057/071）の `answer` フィールドに
「バージョン確認・アップデート」ステップを一括挿入するための**単発パッチスクリプト**。

- 通常の `make ingest` とは独立して手動実行するもの
- 実行後は必ず `make validate` → `make ingest` でPineconeに反映する
- ステップ番号の繰り上げ（旧⑤→⑥ 等）を自動処理する3種の操作（`insert_before_unnumbered` / `insert_before_step` / `append`）を持つ

---

## 6. デプロイ構成

### バックエンド（Railway）

| 項目 | 内容 |
|------|------|
| ランタイム | Python 3.11 |
| フレームワーク | FastAPI + uvicorn |
| 起動コマンド | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| ヘルスチェック | `GET /` → `{"status": "ok"}` |
| 再起動ポリシー | 失敗時に自動再起動 |
| デプロイトリガー | GitHub main ブランチへのpush |

**必須環境変数（Railway Variables）**

| 変数名 | 用途 |
|--------|------|
| `ANTHROPIC_API_KEY` | Claude API（Haiku + Sonnet） |
| `PINECONE_API_KEY` | ベクトルDB |
| `PINECONE_INDEX_NAME` | インデックス名（例: srcc-faq） |
| `COHERE_API_KEY` | Embedding + Rerank |
| `UPSTASH_REDIS_REST_URL` | セッション管理・クエリログ |
| `UPSTASH_REDIS_REST_TOKEN` | 同上 |
| `APP_ENV` | `production` |
| `ALLOWED_ORIGINS` | Vercelドメイン（CORS） |
| `DEBUG_MODE` | `false`（trueでsystem_promptがSSEに含まれる） |

### フロントエンド（Vercel）

| 項目 | 内容 |
|------|------|
| フレームワーク | Next.js 14（App Router） |
| スタイリング | Tailwind CSS |
| デプロイトリガー | GitHub main ブランチへのpush |
| ルーティング | `vercel.json` で `frontend/` ディレクトリを指定 |

**必須環境変数（Vercel Variables）**

| 変数名 | 用途 |
|--------|------|
| `BACKEND_URL` | RailwayバックエンドURL |

### API プロキシ構成

```
ブラウザ → Vercel (frontend/app/api/chat/route.ts) → Railway (app/api/chat.py)
```

Vercel側でSSEストリームをそのままブラウザに転送するプロキシを実装。
CORSをVercel内部で解決し、バックエンドURLを隠蔽している。

---

## 7. Dify からの移行点

以前はDifyの標準RAGを使用していたが、以下の理由でフルスクラッチ移行：

| 課題（Dify） | 解決策（現システム） |
|-------------|-------------------|
| 標準RAGの検索精度が不十分（特に囲碁専門用語） | BM25+Vector+RRF+Cohereリランクのハイブリッド検索 |
| 用語の定義をコンテキストに注入できない | EntityExtractorで用語集を直接照合してプロンプトに挿入 |
| 会話履歴の管理が限定的 | Upstash RedisによるMulti-turnセッション管理 |
| 体験・購入場所の動的情報取得不可 | senserobot-jp.com/store リアルタイムスクレイピング |
| ログの可視化・エクスポートが難しい | /api/logsエンドポイント + Excelエクスポート |
| プロンプトのバージョン管理が困難 | prompt_builder.py に一元集約・Gitで管理 |
| FAQの曖昧さ（例：「異常」系FAQ混合） | embedding_text分離 + システムプロンプトルールで制御 |

---

## 8. API エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| `POST` | `/api/chat` | チャット（SSEストリーミング） |
| `GET` | `/api/health` | ヘルスチェック |
| `GET` | `/api/logs` | クエリログ閲覧（HTML/JSON） |
| `GET` | `/` | ルートヘルスチェック |
| `GET` | `/docs` | Swagger UI（development環境のみ） |

### POST /api/chat リクエスト

```json
{
  "message": "アタリとは何ですか？",
  "session_id": "uuid-v4",
  "metadata_filter": {}
}
```

### SSEイベント形式

```
data: {"type": "text", "text": "アタリとは..."}
data: {"type": "text", "text": "相手の石を..."}
data: {"type": "done", "sources": [...], "extracted_entities": [...], "expanded_query": "...", "session_id": "..."}
```

エラー時:
```
data: {"type": "error", "message": "AIサービスが一時的に混雑しています..."}
```

---

## 9. ローカル開発

### 初期セットアップ

```bash
cd srcc-faq-bot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# フロントエンド
cd frontend && npm install
```

### 環境変数

`.env.local` にAPIキーを設定（`.env.example` を参照）。

```
ANTHROPIC_API_KEY=sk-ant-...
PINECONE_API_KEY=...
COHERE_API_KEY=...
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
```

### 起動コマンド

```bash
make dev          # バックエンド起動 (localhost:8000)
make ingest       # Pinecone + BM25 インデックス再構築
make validate     # data/ のJSONスキーマ検証
make test         # テスト全実行

# フロントエンド（別ターミナル）
cd frontend && npm run dev   # localhost:3000
```

---

## 10. 運用フロー

### ナレッジ追加・修正時

1. `data/faq/faq_master.json` または `data/glossary/glossary_master.json` を編集
2. `make validate` → `make ingest`
3. `git commit && git push`（Railwayに自動デプロイ、Excelも自動出力）

### ログ確認

- 定期的に `/api/logs` でオペレーターのクエリ・回答・参照ナレッジを確認
- 回答品質に問題があれば FAQの`answer`・`embedding_text` を修正
- 「思考回路」列でどのFAQが参照されたか・どのルールが適用されたか確認可能

### エスカレーション対応

- オペレーターからの「回答がおかしい」報告 → ログで当該クエリを特定 → FAQ修正
- FAQにない質問 → 新規FAQ追加 → make ingest
