.PHONY: dev ingest validate test test-unit install clean

# ローカル開発サーバー起動
dev:
	uvicorn app.main:app --reload --port 8000

# バージョン同期: VERSION → frontend/lib/version.ts
sync-version:
	python scripts/sync_version.py

# データ投入 (BM25 + Pinecone)
ingest:
	python scripts/validate_data.py
	python scripts/build_bm25_index.py
	python scripts/ingest.py --mode=full

# スキーマバリデーションのみ
validate:
	python scripts/validate_data.py

# 全テスト
test:
	pytest tests/ -v --cov=app --cov-report=term-missing

# ユニットテストのみ
test-unit:
	pytest tests/unit/ -v

# 依存パッケージインストール
install:
	pip install -e ".[dev]"

# キャッシュクリア
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pkl" -delete 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# フロントエンド開発
frontend-dev:
	cd frontend && npm run dev

# フロントエンド依存インストール
frontend-install:
	cd frontend && npm install
