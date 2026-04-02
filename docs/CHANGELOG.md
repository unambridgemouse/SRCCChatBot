# SRCCセンちゃんBot — 変更履歴

> バージョン管理ルール:
> - **Patch (x.x.1)**: ナレッジ追加・FAQ修正・用語集更新
> - **Minor (x.1.0)**: プロンプト変更・RAGロジック変更・UI機能追加
> - **Major (2.0.0)**: アーキテクチャ変更・破壊的変更

---

## Ver 1.1.0 — 2026-04-02

**店舗案内フロー改善（プロンプト変更）**
- 近隣店舗の選定基準を「地理的距離」から「交通アクセスの良さ」優先に変更
- 隣接県・直通鉄道でつながっている県を必ず含めるルールを追加（例: 滋賀→京都はJR琵琶湖線で直通のため必須）
- アクセス時間の目安（電車・車で1〜1.5時間以内）を明記
- 複数方向への分散（一方向の県だけにならないよう）を指示
- ケースBの提示件数を1〜3件→3〜5件に拡張
- ケースA（体験フロー）にも同じアクセス基準を適用

---

## Ver 1.0.1 — 2026-04-02

**ログ改善**
- クエリログの回答保存を全文に変更（旧: 先頭300文字）
- `/api/logs` の回答列を折りたたみ式（先頭80文字プレビュー → クリックで全文表示）に変更

---

## Ver 1.0 — 2026-04-02（オペレーター公開）

### 初回リリース

**システム構成**
- バックエンド: FastAPI + Railway
- フロントエンド: Next.js + Vercel
- RAG: BM25 + Pinecone (Cohere embed-multilingual-v3.0) + RRF + Cohere Rerank
- セッション管理: Upstash Redis

**ナレッジ**
- FAQ: 83件（faq-001〜faq-083）
- 用語集: 226件

**主要機能**
- Hybrid Search & Re-ranking（BM25 + Vector + RRF + Cohere Rerank）
- Entity-Focused Query Expansion（用語集直接照合・クエリ拡張）
- Multi-turn Context Management（Upstash Redis、TTL 30分・最大5ターン）
- 店舗検索フロー（senserobot-jp.com/store リアルタイムスクレイピング）
- クエリログ（Railway stdout + Upstash Redis、/api/logs で閲覧）
- SSEストリーミング回答

**このバージョンでの主な変更（リリース直前）**
- 購入フロー改訂: 該当県に購入店舗なしの場合、近隣県店舗を先案内 → 伊藤電機直販・Amazonを付記する形に変更（旧: 伊藤電機・Amazonのみ）
- FAQ追加: faq-082（メインメニュー構成）、faq-083（システム設定メニュー構成）
- CLAUDE.md修正: OPENAI_API_KEY を不要に変更、Obsidianパス修正、rerank件数誤記修正（3→7）
