# SRCCセンちゃんBot — 開発ログ・重要決定事項まとめ

> 抽出元: 開発チャット履歴（〜2026-04-02）
> 関連: [[SPEC]] / [[STRUCTURE]]

---

## 1. RAGパイプライン設計

### 検索フロー（確定仕様）

```
クエリ
 → [1] EntityExtractor (Claude Haiku)
       └ 囲碁/SRCC用語を抽出 → 用語集で定義取得 → クエリ拡張（関連用語を末尾追加、最大5件）
 → [2] HybridSearcher
       ├ BM25（文字バイグラムトークナイズ）: 完全一致・専門用語強
       ├ Pinecone Vector（Cohere embed-multilingual-v3.0 / 1024次元）: 意味的近傍
       ├ RRF（Reciprocal Rank Fusion）: score = Σ(1 / (60 + rank)) で統合
       └ Cohere Rerank（rerank-multilingual-v3.0）: 上位10件→7件に絞り込み
 → [3] related_faq_ids補完
       └ 取得FAQの related_faq_ids に含まれるFAQをスコアそのままで追加
 → [4] PromptBuilder → Claude Sonnet 4.6（SSEストリーミング）
```

### モデル使い分けの意図

| 用途 | モデル | 理由 |
|------|--------|------|
| Entity抽出 | claude-haiku-4-5-20251001 | 速度優先・低コスト・JSONのみ返せばよい |
| 回答生成 | claude-sonnet-4-6 | 精度優先・日本語オペレーター向け文体 |
| Embedding | embed-multilingual-v3.0 | 日本語精度が高い |
| Rerank | rerank-multilingual-v3.0 | 同上 |

---

## 2. プロンプト設計の工夫（prompt_builder.py）

### システムプロンプトの重要ルール

#### オペレーター向け文体（最重要）

```
✅ 正しい: 「お客様にテキストサイズを標準に変更するようご案内ください」
❌ 誤り:   「テキストサイズを標準に変更してください」
```

読み手は常にオペレーター。お客様に直接語りかける文体は禁止。

#### FAQ選択の曖昧さ排除ルール（後から追加）

```
複数FAQが検索された場合、ユーザーの質問に含まれる
エラーメッセージ名・表示文言が一字一句一致するFAQのみを使用すること。
例：「局面が異常です」→ faq-053のみ使用、faq-019（対局異常）は使用しない。
```

**追加背景**: BM25の文字バイグラム特性により「異常」を含む faq-019 と faq-053 が
両方ヒットし、混合した回答が生成される問題が発生。embedding_text 分離だけでは
解決不十分だったため、システムプロンプトのルールで制御することにした。

#### エスカレーション案内の制約

```
「伊藤電機へご連絡ください」「伊藤電機に直接お問い合わせください」は絶対に行わない。
→ お客様は伊藤電機へ直接連絡しない。必ずSRCCオペレーターが中継する運用。
```

#### エスカレーション時のヒアリング項目（4パターン）

```
全項目: ①氏名 ②連絡先 ③住所 ④シリアル番号 ⑤販路 ⑥バージョン ⑦備考 ⑧認知経路 ⑨支払方法

パターン1（折り返し連絡のみ）: ①②⑦
パターン2（郵送物あり）:       ①②③⑦
パターン3（故障・不具合疑い）:  ①②③④⑤⑥⑦
パターン4（カタログ・購入希望）: ①②③⑦⑧⑨
```

#### 基礎知識のシステムプロンプト注入

```
## このシステムの基礎知識（常に前提として認識すること）
- センちゃん：囲碁ロボット（SenseRobot）の愛称
- SRCC：センスロボットコールセンターの略称
- センスタイム社：囲碁ロボットのメーカー（中国企業）
- 伊藤電機：囲碁ロボットの日本販売代理店（メーカーではない）
```

### 店舗検索プロンプト（STORE_SYSTEM_PROMPT_TEMPLATE）

体験/購入の目的別フォールバック分岐:

```
ケースA（体験目的・該当県なし）:
  ① 近隣都道府県の体験店舗を1〜3件案内
  ② 「遠くて行けない」→ Rentio（レンタル）を案内
  ③ Rentioも難しい → 伊藤電機へエスカレ

ケースB（購入目的・該当県なし）:
  近隣県・ECサイト一覧は提示しない。以下のみ:
  ① 伊藤電機直販（このお電話で購入可能）
    - 囲碁将棋チャンネル視聴者: 145,000円
    - それ以外: 165,000円
  ② Amazon（senserobot-jp.com トップの【ご購入】から）
  ③ senserobot-jp.com/store 掲載の購入可能店舗
```

---

## 3. FAQナレッジの重要修正履歴

### embedding_text による曖昧さ制御

faq-019（対局異常）と faq-053（局面が異常です）の混同問題:

- **誤った対処**: faq-019 の embedding_text に「局面が異常です」を追記
  → 逆にBM25スコアが上がり悪化
- **正しい対処**:
  - faq-019: 「対局異常エラー」に限定した embedding_text
  - faq-053: 「局面が異常ですエラーメッセージ」に限定した embedding_text
  - **根本解決**: システムプロンプトの一字一句一致ルールで制御

### バージョン確認ステップの順序ルール

**方針**: バージョン確認は「基本トラブルシューティングの後・エスカレの前」に配置。

修正したFAQ:

| FAQ | 修正内容 |
|-----|---------|
| faq-005 | カメラテスト(⑦) ↔ バージョン確認(⑧) を入れ替え |
| faq-014 | 周波数確認(⑤) ↔ バージョン確認(⑥) を入れ替え |
| faq-023 Section1 | ③にバージョン確認を追加（全ボタン無反応パスに欠如していた） |

### 新規追加・修正FAQ

**faq-081（ロボット価格）新規追加**
```
質問: ロボットはいくら？ / 値段を教えて
回答:
  - 伊藤電機直販: 囲碁将棋チャンネル視聴者 145,000円 / それ以外 165,000円
  - Amazon でも購入可能
  - senserobot-jp.com/store に掲載の販売店でも購入可能
```

**faq-080（購入場所）マークダウンリンク化**
```
senserobot-jp.com/store
→ [senserobot-jp.com/store](https://www.senserobot-jp.com/store)
```
フロントエンドで `[text](url)` を `<a>` タグにレンダリングする実装も同時追加。

**faq-004（ネットワーク診断）④の修正**
```
④ ネットワーク診断:
  ロボットをゲストモードで起動し、設定＞ネットワーク診断で
  ネットワーク診断を行ってください（改善しない場合は⑤へ）。
```

---

## 4. 店舗フォローアップ検出ロジック（store_scraper.py）

### 問題

「東京都杉並区」のような地名のみのクエリは `is_store_query()` で体験/購入ワードが
なければ False になり、店舗フローに入らない。

### 解決策: is_store_followup() の改善

```python
_PROXIMITY_WORDS = ["近い", "近く", "最寄り", "一番近い", "近いのは", "近場"]
_RESIDENCE_WORDS = ["住んでる", "住んでいる", "住む", "最寄", "在住", "近隣", "周辺", "付近", "近くに住"]

def is_store_followup(query, history):
    # 直近6ターンのuser/assistant両方を検索
    had_store_context = False
    for h in history[-6:]:
        if h["role"] == "user" and is_store_query(h["content"]):
            had_store_context = True; break
        if h["role"] == "assistant" and (
            "体験・購入" in h["content"] or
            "senserobot-jp.com/store" in h["content"]
        ):
            had_store_context = True; break

    has_location = (
        any(都道府県) or any(_FOLLOWUP_WORDS) or
        any(_PROXIMITY_WORDS) or any(_RESIDENCE_WORDS)
    )
    return had_store_context and has_location
```

**ポイント**: assistantターンの履歴も確認することで、前回の回答で店舗リストを
提示していれば地名のみのフォローアップも正しく店舗フローへ誘導できる。

---

## 5. クエリログシステム（query_logger.py）

### 設計方針

- **Railway stdout**: `[QUERY_LOG]` タグ付きJSON → Railway Logsで検索可能
- **Upstash Redis**: `query_log` キー、LPUSH + LTRIM（最大500件）
- **非クリティカル**: try/except で囲み、失敗してもチャットに影響しない

### ログエントリのフィールド

```python
{
    "ts":             "2026-04-02 10:37:04",   # JST
    "ts_unix":        1743550624.123,
    "session_id":     "uuid-v4",
    "query":          "アタリとは？",
    "expanded_query": "アタリとは？ コウ シチョウ",  # entity拡張後
    "answer":         "アタリとは...",              # 先頭300文字
    "sources":        [{"id": "faq-001", "score": 0.823}],
    "system_prompt":  "あなたは囲碁ロボット...",     # 思考回路（全文）
}
```

### /api/logs の列構成

| 日時(JST) | クエリ | 拡張クエリ | 回答(300字) | 参照ナレッジ+スコア | セッションID | 思考回路(折りたたみ) |

---

## 6. フロントエンドの実装詳細

### マークダウンレンダリング（MessageBubble.tsx）

```tsx
// renderInline() で独自パース
const parts = text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\))/g);
// [text](https://...) → <a href="..." target="_blank" rel="noopener noreferrer">
const linkMatch = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
if (linkMatch) return <a href={linkMatch[2]} ...>{linkMatch[1]}</a>;
```

### ロボットアバター（RobotAvatar.tsx）の視覚設計

- コンテナ: `borderRadius: "22px"` + `overflow: "hidden"` + `boxShadow`
  → `filter: drop-shadow` は border-radius でクリップされないため boxShadow を使用
- SVG: 黒背景 rect + 顔パーツ（light gray #d4d4d4）

### 碁盤背景CSS（ChatWindow.tsx）

```tsx
style={{
  backgroundColor: "#C8923A",
  backgroundImage: [
    "repeating-linear-gradient(0deg, rgba(92,48,16,0.55) 0px, rgba(92,48,16,0.55) 1px, transparent 1px, transparent 18px)",
    "repeating-linear-gradient(90deg, rgba(92,48,16,0.55) 0px, rgba(92,48,16,0.55) 1px, transparent 1px, transparent 18px)",
  ].join(","),
}}
```

「ご質問をどうぞ」テキスト: `color: white` + `textShadow` で碁盤背景でも視認性確保。

---

## 7. Difyからの移行で変えた主なロジック

| Dify の制約 | 現システムの解決策 |
|------------|-----------------|
| 標準RAGの検索精度不足 | BM25+Vector+RRF+Cohereリランク |
| 用語定義をコンテキストに注入できない | EntityExtractor → 用語集直接照合 |
| 会話履歴管理が限定的 | Upstash Redis（TTL 1800秒・5ターン保持） |
| 動的情報（店舗）取得不可 | senserobot-jp.com/store リアルタイムスクレイプ |
| ログ可視化が難しい | /api/logs + Excel自動エクスポート |
| プロンプトのGit管理が困難 | prompt_builder.py に一元集約 |
| FAQの曖昧さ（異常系混合） | embedding_text分離 + システムプロンプトルール |

---

## 8. 運用で判明したトラブルとその対処

### BM25バイグラム問題

- **症状**: 「局面が異常です」で faq-019（対局異常）が誤ヒット
- **原因**: 「異常」がバイグラム「異常」として両FAQにマッチ
- **対処**: システムプロンプトにエラーメッセージ名一字一句一致ルールを追加

### Cohereリランクスコア均等化

- **症状**: faq-019/053がともにスコア 0.016 前後
- **原因**: BM25のみでヒット→RRFスコアが均等（`1/61 ≈ 0.016`）
- **対処**: 上記システムプロンプトルールで根本解決

### is_store_followup が地名のみで発火しない

- **症状**: 「東京都杉並区」だけでは体験・購入ワードなし → 店舗フローに入らない
- **対処**: assistantターンの履歴（senserobot-jp.com/store URLの有無）も検索対象に追加

### drop-shadow + border-radius の競合

- **症状**: CSS `filter: drop-shadow` が border-radius のクリッピングを無視して四角くなる
- **対処**: `filter: drop-shadow` → `box-shadow` に変更（border-radiasを尊重する）

### Excel が Git に混入

- **対処**: `data/excel/` を `.gitignore` に追加、`git rm --cached` で追跡解除
