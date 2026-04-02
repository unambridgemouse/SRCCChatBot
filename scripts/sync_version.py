"""
VERSION ファイルから frontend/lib/version.ts を自動生成するスクリプト。
バージョン番号の唯一の正解は VERSION ファイル。

使い方: python scripts/sync_version.py
"""
import re
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent
VERSION_FILE = ROOT / "VERSION"
VERSION_TS = ROOT / "frontend" / "lib" / "version.ts"

version = VERSION_FILE.read_text(encoding="utf-8").strip()
today = date.today().isoformat()

VERSION_TS.write_text(
    f'export const APP_VERSION = "{version}";\n'
    f'export const APP_VERSION_DATE = "{today}";\n',
    encoding="utf-8",
)

print(f"version.ts updated: {version} ({today})")
