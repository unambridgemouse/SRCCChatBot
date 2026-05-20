# SRCCセンちゃんBot — ローカルLLM化引き渡し資料

> 作成: 2026-05-01
> 対象読者: ローカルLLM実装担当者
> 目的: 現行Claude API構成からローカルLLM(想定: Qwen2.5系列)への移行に必要な情報を一括提示する

---

## 1. 本資料の前提

- **構造はそのまま、頭脳(LLM)だけをローカルLLMに切り替える**方針
- 検索基盤(Pinecone)・埋め込み(Cohere)・セッション管理(Upstash Redis)はそのまま使用継続
- 想定モデル: **Qwen2.5系列**(他モデルでも応用可)
- 既存ドキュメント [SPEC.md](SPEC.md) / [STRUCTURE.md](STRUCTURE.md) / [CHANGELOG.md](CHANGELOG.md) と併読すること

---

## 2. 引き渡すドキュメント・ファイル

| 区分 | ファイル | 役割 |
| --- | --- | --- |
| **仕様書** | [docs/SPEC.md](SPEC.md) | システム全体仕様。アーキテクチャ図・データスキーマ・API契約・運用フロー |
| **構成** | [docs/STRUCTURE.md](STRUCTURE.md) | ディレクトリ構成と各ファイルの役割詳細 |
| **変更履歴** | [docs/CHANGELOG.md](CHANGELOG.md) | バージョン履歴(設計判断の経緯を辿るのに有用) |
| **開発ガイド** | [CLAUDE.md](../CLAUDE.md) | ローカル開発手順・コマンド・環境変数 |
| **環境変数雛形** | [.env.example](../.env.example) | 必須環境変数一覧 |
| **ナレッジ** | [data/faq/faq_master.json](../data/faq/faq_master.json)<br>[data/glossary/glossary_master.json](../data/glossary/glossary_master.json) | FAQ 83件・用語集226件(JSONスキーマはSPEC.md参照) |
| **プロンプト本体** | [app/core/prompt_builder.py](../app/core/prompt_builder.py) | 3種類のシステムプロンプトテンプレート |
| **本資料** | [docs/LOCAL_LLM_HANDOVER.md](LOCAL_LLM_HANDOVER.md) | 移行ガイド(このファイル) |

---

## 3. LLMが担う2つの役割(置き換え対象)

このシステムでLLMが使われている箇所は **2箇所だけ**。それ以外(検索・埋め込み・リランク・セッション管理)はLLMと無関係。

### 3-1. Entity抽出(高速・低負荷)

| 項目 | 内容 |
| --- | --- |
| 実装箇所 | [app/core/entity_extractor.py:58-67](../app/core/entity_extractor.py#L58-L67) |
| 現行モデル | Claude Haiku 4.5 |
| プロンプト | `ENTITY_EXTRACTION_PROMPT` ([prompt_builder.py:180-187](../app/core/prompt_builder.py#L180-L187)) |
| 入力 | ユーザクエリ1文(例: 「アタリってどういう状態?」) |
| 出力 | **JSON配列のみ**(例: `["アタリ"]`) |
| max_tokens | 256 |
| 失敗時 | フォールバックロジックあり(用語集の部分一致) |
| **ローカル化要件** | Qwen2.5-3B〜7Bで十分。**JSON出力が安定する**ことが必須(vLLMの`guided_json`推奨) |

### 3-2. 回答生成(本丸・品質要件高)

| 項目 | 内容 |
| --- | --- |
| 実装箇所 | [app/api/chat.py:54-62](../app/api/chat.py#L54-L62) |
| 現行モデル | Claude Sonnet 4.6 |
| プロンプト | `SYSTEM_PROMPT_TEMPLATE`(FAQ用)または `STORE_SYSTEM_PROMPT_TEMPLATE`(店舗用) |
| 入力 | system(動的に検索結果・会話履歴を埋め込む) + ユーザクエリ |
| 出力 | **ストリーミング日本語テキスト**(オペレーター向け文体) |
| max_tokens | 4096(Qwen移行時は6000〜8000に拡張推奨) |
| 過負荷リトライ | 最大3回(10/20/30秒) |
| **ローカル化要件** | Qwen2.5-32B以上推奨。日本語ビジネス敬語の品質要件高。SSE互換ストリーミング必須 |

---

## 4. プロンプト仕様の重要ルール

[prompt_builder.py](../app/core/prompt_builder.py) のシステムプロンプトには、**回答品質を左右する重要なルール**が多数含まれている。ローカルLLMでも同等の制御が必要。

### 4-1. FAQ用プロンプト(`SYSTEM_PROMPT_TEMPLATE`)

1. **オペレーター向け文体**: 「お客様に〇〇するようご案内ください」形式(正例/誤例あり)
2. **回答フォーマット**: 「結論(1〜2文) → 手順 → 関連用語」の3段構成
3. **FAQ混在禁止**: エラーメッセージ名が一字一句一致するFAQのみ使用
4. **太字保持**: `**...**` で囲まれた箇所は原文ママ
5. **エスカレーション運用**: 「伊藤電機へ直接ご連絡ください」は **絶対禁止**(SRCCが代理連絡する運用)
6. **ヒアリング項目4パターン**: ①〜⑨の項目をケース別に提示

### 4-2. 店舗用プロンプト(`STORE_SYSTEM_PROMPT_TEMPLATE`)

1. **近隣県・直通鉄道優先の選定基準**(地図距離だけで判断しない)
2. **体験不可 → Rentio → 伊藤電機エスカ** の三段階フォールバック
3. **購入不可 → 近隣県店舗 + 伊藤電機直販 + Amazon** の固定文言

これらは **プロンプトをそのまま使い回せば品質維持できる**設計。書き換える必要はない。
ただしローカルLLMの能力次第で「ルール遵守の強さ」が変わる(後述の懸念点参照)。

---

## 5. 周辺コンポーネント(LLM以外・流用可能)

ローカルLLM化でも **そのまま使える**部分。実装担当者はここに手を入れない。

| コンポーネント | ファイル | 役割 |
| --- | --- | --- |
| ハイブリッド検索 | [app/core/hybrid_search.py](../app/core/hybrid_search.py) | BM25+Pinecone+RRF+Cohere Rerank |
| 用語集照合 | [app/core/entity_extractor.py:79-91](../app/core/entity_extractor.py#L79-L91) | LLM抽出結果と用語集を直接マッチング |
| プロンプト組み立て | [app/core/prompt_builder.py](../app/core/prompt_builder.py) | テンプレートに動的データを埋め込み |
| セッション管理 | [app/core/context_manager.py](../app/core/context_manager.py) | Upstash Redis 30分TTL |
| 店舗スクレイピング | [app/core/store_scraper.py](../app/core/store_scraper.py) | senserobot-jp.com/store をBeautifulSoupで取得 |
| クエリログ | [app/core/query_logger.py](../app/core/query_logger.py) | stdout + Redis |

---

## 6. 実装担当者の作業範囲(置換箇所)

最小工数なら、**たった2ファイルの数行だけ**を書き換えればよい。

### 置換① [app/core/entity_extractor.py:18, 58-67](../app/core/entity_extractor.py)
```python
# 現状(Anthropic SDK)
self.client = anthropic.Anthropic(api_key=...)
resp = self.client.messages.create(model=..., messages=...)
```
→ ローカルLLMサーバ(vLLM/Ollama等のOpenAI互換エンドポイント)へ差し替え

### 置換② [app/api/chat.py:48, 54-62](../app/api/chat.py)
```python
# 現状(Anthropic SDK・ストリーミング)
client = anthropic.AsyncAnthropic(api_key=...)
async with client.messages.stream(model=..., system=..., messages=...) as stream:
```
→ 同様にローカルLLMサーバへ差し替え

### 推奨方針
**vLLM** を立てて **OpenAI互換API** を公開する → Pythonコードを `openai` SDKに置き換えれば差分が最小化される(`base_url`変更のみで済む)。

---

## 7. 店舗フロー特有の注意点

### 7-1. 仕組みの理解
店舗情報の取得は [app/core/store_scraper.py](../app/core/store_scraper.py) が単独で担当。**LLMは関与しない**。

```
ユーザクエリ「滋賀県でセンスロボットを買えるお店ある?」
   ↓
is_store_query() で店舗系クエリと判定
   ↓
get_store_text() が httpx + BeautifulSoup で senserobot-jp.com/store をスクレイピング
   ↓
プレーンテキストの店舗リストを取得(1時間インメモリキャッシュ)
   ↓
STORE_SYSTEM_PROMPT_TEMPLATE に店舗リストを埋め込む
   ↓
LLM が「滋賀県には店舗なし → 京都府の店舗を提案」と判断・回答
```

つまりLLMは **「スクレイプ済み店舗テキスト」を読んで判断・整形しているだけ**。Webアクセス機能を持っているわけではない。

### 7-2. ローカルLLMへの影響
- スクレイピング・キャッシュ・プロンプト埋め込み処理は **無修正で動く**
- 一方、店舗選定の判断はLLMの**日本の地理・鉄道知識**に依存する
- 小型ローカルLLMだと「滋賀県→京都府(JR琵琶湖線で直通)」のような関係を知らない可能性

### 7-3. 推奨対策: プロンプトに隣接県マップを埋め込む
`STORE_SYSTEM_PROMPT_TEMPLATE` に **47都道府県の隣接・主要鉄道ルート表**を約1500トークン分追加する改修を**ローカルLLM化と同時に**実施することを推奨。

例:
```
## 都道府県の隣接・主要鉄道ルート(参考)
- 滋賀県の隣接県: 京都府・三重県・福井県・岐阜県・大阪府(JR新快速で直通)
- 京都府の隣接県: 大阪府・兵庫県・滋賀県・奈良県・三重県・福井県
- ...
```

これでローカルLLMのサイズに依存せず、店舗フローの品質を担保できる。

---

## 8. Qwen2.5固有の懸念点(重要度別)

### 🔴 高: 必ず事前検証すべき項目

#### 8-1. 「オペレーター向け文体」の維持
Qwen2.5は日本語が話せるが、**ビジネス敬語・接客敬語のニュアンス**(「ご案内ください」「ご確認ください」)はClaude Sonnetと比べて硬さが残る傾向あり。

**懸念シナリオ:**
- 「お客様にテキストサイズを標準に変更してもらってください」のような不自然な表現
- 「変更してください」と直接お客様向けに書いてしまう(プロンプトの正例/誤例を無視)

**対策**: 14Bでは不安。**最低32B、可能なら72B**を選ぶ。または日本語特化チューニング版を検討。

#### 8-2. 複数ルールの同時遵守
[SYSTEM_PROMPT_TEMPLATE](../app/core/prompt_builder.py) には **7つ以上の重要ルール**(FAQ混在禁止・太字保持・エスカレーション禁則・ヒアリング項目4パターン等)が並んでいる。Qwen2.5は小型(7B/14B)だと**上位2〜3ルールしか守らない**傾向がある。

**特に致命的なのは:**
- 「伊藤電機へ直接ご連絡ください」と案内してしまう(運用上絶対NG)
- 複数FAQが検索結果に出たときに、エラーメッセージ名が違うFAQを混ぜて回答してしまう

**対策**:
- 32B以上推奨
- プロンプトを **最重要ルールだけ冒頭に集約**し、繰り返し強調する書き方に再構成
- ゴールデンセットで「禁則違反率」をモデル選定の最重要指標にする

#### 8-3. Entity抽出時のJSON出力安定性
[entity_extractor.py:58-67](../app/core/entity_extractor.py#L58-L67) は `["アタリ"]` のような**JSON配列のみ**を期待しているが、Qwen2.5の小型モデル(3B/7B)は、

- ```` ```json\n["..."]\n``` ```` のようにマークダウンで包む
- 「これらの用語が見つかりました: `["..."]`」のように説明文を添える

…等の癖がある。既存コードに ```` ``` ```` 除去ロジックは入っているが、Qwenの癖は別。

**対策**:
- **vLLMの`guided_json` または `outlines`** を使ってJSON Schema強制(これが一番確実)
- フォールバック処理(`_fallback_match()`)の動作を強化

---

### 🟡 中: 設計時に考慮すべき項目

#### 8-4. RAGコンテキスト無視・幻覚リスク
Qwen2.5は **検索結果に明記されていない内容を、もっともらしく作って答える**傾向がClaude Sonnetより強い。Sonnet 4.6で「検索結果に根拠がない場合は『ナレッジが見つかりませんでした』と回答」がほぼ完璧に効くのに対し、Qwenは破る可能性あり。

**対策**:
- `temperature=0.1〜0.3` の低温設定で実行
- プロンプトの「制約」セクションを冒頭にも再掲
- ゴールデンセットに「FAQに載っていない質問」を入れて幻覚率を測定

#### 8-5. 量子化による日本語劣化
14B以上はAWQ/GPTQ 4bit量子化が事実上必須(VRAM制約)。一般的に量子化の品質劣化は1〜3%だが、**日本語タスクは英語より大きく劣化する**という報告が散見される。

**対策**:
- FP16ベースラインを一度測定 → 量子化版と比較してどれくらい落ちるか把握
- 厳しいなら8bit量子化(GPTQ-Int8)を試す
- または1サイズ大きいモデル + 4bit を採用(14B FP16 vs 32B 4bit のような比較)

#### 8-6. プロンプトキャッシュ互換性なし
[prompt_builder.py](../app/core/prompt_builder.py) は2219トークンまで膨らませてSonnet 4.6のキャッシュ要件を満たしている。**この対応はQwenでは無意味**になる。

ただし、vLLMには **Prefix Caching**(自動でプロンプト接頭辞をKVキャッシュする)機能がある。要件はSonnetと違うが、結果的に効くはず。要確認。

#### 8-7. 店舗フローの地理知識依存
日本の都道府県隣接・鉄道路線の知識はQwenにも入っているが、72Bでも完全ではない。**プロンプトに隣接県マップを明記する対応(§7-3)**はQwen移行とセットで必須化した方が安全。

#### 8-8. 専門用語の認識
SRCC固有の用語(「SRCCモード」「センスロボット」「囲碁将棋チャンネル」)はQwenの訓練データに**含まれていない可能性が高い**。

**対策**:
- Entity抽出のフォールバック処理([entity_extractor.py:103-106](../app/core/entity_extractor.py#L103-L106))を強化
- 用語集の `term_variants` を充実させ、文字列マッチでの拾い上げ精度を上げる

---

### 🟢 低: 知っておく程度

#### 8-9. ストリーミング互換性
vLLMはOpenAI互換のSSEストリーミングをサポート。既存のフロントエンド側 [route.ts](../frontend/app/api/chat/route.ts) は無修正で動くはず。

#### 8-10. トークナイザの違い
Qwen2.5のトークナイザは独自(約152K vocab)。プロンプトの「2219トークン」もQwenでは違う値になる。`max_tokens=4096` も意味が変わる(Qwenトークン換算)。

**対策**: Qwen側で再計測。`max_tokens` は安全側に大きめ(6000〜8000)に設定。

#### 8-11. 推論レイテンシ
Sonnet 4.6のAPI応答は地球規模で最適化されている。ローカル32Bモデル(AWQ 4bit、L40S)だと **回答開始まで1〜3秒、出力速度は20〜40 token/sec** くらい。Sonnetより遅くなる可能性が高い。

オペレーターが通話中にリアルタイム参照する運用なので、レイテンシ計測は早めに。

#### 8-12. ライセンス
Qwen2.5はApache 2.0で商用利用可。**ただし72B版は別ライセンス(Qwen License)** で、月間アクティブユーザー1億超で別途許諾が必要。SRCCは余裕で対象外だがメモまで。

---

## 9. 品質検証用データ

ローカルLLMが現行品質を維持できるかの検証には、以下を活用:

| 用途 | データソース | 取得方法 |
| --- | --- | --- |
| **回答ゴールデンセット** | クエリログ(Upstash Redis `query_log` キー / `/api/logs` エンドポイント) | 過去のクエリ + Sonnet応答 + 参照ナレッジが揃っている。**最低30〜50件抽出して評価セット化**する |
| **用語抽出ゴールデンセット** | 同上(`extracted_entities` フィールド) | Haikuの抽出結果を正解として使える |
| **手動テストセット** | [CLAUDE.md](../CLAUDE.md) の "Testing Checklist" | 基本用語(アタリ・コウ等)・複数ターン会話・幻覚防止・スコープ外質問 |

### 評価方法の推奨
- ローカルLLM応答 vs Sonnet応答 を、別のLLMでLLM-as-Judge採点(または人手評価)
- 特に「**オペレーター文体の遵守**」「**FAQ混在禁止ルールの遵守**」「**エスカレーション文言の正確性**」を重点チェック

---

## 10. インフラ要件サマリー

ローカルLLM部分以外は **現状のサービスをそのまま使う前提** で、必要なものだけ整理。

| 必須サービス | 用途 | 代替可否 |
| --- | --- | --- |
| **GPU推論基盤** | LLM2系統(Entity抽出/回答生成)のホスティング | 必須・新規調達 |
| Pinecone | ベクトルDB | そのまま使用 or Qdrant等への移行も可 |
| Cohere | Embedding + Rerank | そのまま使用推奨(品質維持のため) |
| Upstash Redis | セッション・ログ | そのまま使用 |
| Railway | バックエンドホスティング | LLMがオンプレならバックエンドも近接配置が望ましい |

### ハードウェア目安(SRCCの低トラフィック前提)
- **Entity抽出**: Qwen2.5-3B〜7B → 8GB VRAM(RTX 4060 Ti 8GB等)で動作可能
- **回答生成**: Qwen2.5-32B AWQ 4bit → 24〜48GB VRAM(RTX 4090 / L40S)
- **同居運用**: 32B回答生成と3B Entity抽出を同一GPUで動かすなら、L40S(48GB)以上推奨

---

## 11. 推奨される検証順序

担当者にこの順で検証してもらうのが最効率:

1. **Qwen2.5-32B-Instruct-AWQ を vLLM で立てる**(まず動かす)
2. **Entity抽出をJSON Schema制約付きで実装** → JSON失敗率を測定
3. **ゴールデンセット30件で回答生成を測定**:
   - 禁則違反率(伊藤電機直接連絡案内、FAQ混在)
   - 文体スコア(オペレーター向け表現の遵守)
   - 幻覚率(検索結果にない内容を含む割合)
4. 結果が悪ければ **72B または 32B+日本語SFT版**へグレードアップ検討
5. **店舗プロンプトに隣接県マップを追加**してから店舗フローを検証

---

## 12. 引き渡しチェックリスト

担当者にこれを実行してもらえば、現行品質を維持できているか判定可能:

- [ ] [data/faq/faq_master.json](../data/faq/faq_master.json) と [data/glossary/glossary_master.json](../data/glossary/glossary_master.json) を読み込み、Cohereで埋め込み再生成 → 自前ベクトルDB(またはPineconeそのまま)へ投入
- [ ] [app/core/prompt_builder.py](../app/core/prompt_builder.py) の3テンプレートを **変更せず** そのままローカルLLMに渡せる構造を作る
- [ ] Entity抽出のJSON出力が安定するモデル/プロンプト調整を実施(構造化出力機能の活用を推奨)
- [ ] 回答生成側でSSEストリーミング互換出力を実装
- [ ] ゴールデンセット(クエリログから抽出した30〜50件)で品質スコア測定
- [ ] [CLAUDE.md](../CLAUDE.md) の Testing Checklist 全項目を通過
- [ ] 店舗プロンプトに47都道府県の隣接県マップを追加
- [ ] レイテンシ計測(回答開始時間・トークン/秒)

---

## 13. 結論・推奨構成

Qwen2.5は技術的には移行可能だが、SRCC特有の要件(オペレーター向け敬語・複数ルール遵守・エスカレーション禁則)を考慮すると以下が現実解:

| サイズ | 評価 |
| --- | --- |
| 14B以下 | **地雷確定**(ルール遵守・日本語品質ともに不安) |
| **32B AWQ** | **最低ライン推奨**(現実解) |
| 72B | 安全圏(Sonnet 4.6相当の品質を狙うなら) |

担当者には「**まず32B AWQで立てて、ゴールデンセットでスコア確認 → 足りなければ72B**」のスタンスで進めてもらうのが良い。

---

## 14. 関連リンク

- 公式リポジトリ: https://github.com/unambridgemouse/SRCCChatBot
- 本番URL: https://srcc-chat-bot-m7j6.vercel.app
- ログ閲覧: https://srccchatbot-6636669301ad.up.railway.app/api/logs
- vLLM: https://docs.vllm.ai/
- Qwen2.5: https://qwenlm.github.io/blog/qwen2.5/

---

> 本資料に関する質問・追加情報の依頼は、プロジェクトオーナーまでご連絡ください。
