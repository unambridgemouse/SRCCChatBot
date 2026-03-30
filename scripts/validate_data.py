"""
data/ のJSONスキーマバリデーション。
make validate で実行。
"""
import json
import sys
from pathlib import Path

FAQ_REQUIRED = {"id", "type", "category", "question", "answer", "embedding_text"}
GLOSSARY_REQUIRED = {"id", "type", "term", "definition", "definition_for_operator", "embedding_text"}


def validate_faq(path: Path) -> list[str]:
    errors = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for item in data.get("items", []):
        missing = FAQ_REQUIRED - set(item.keys())
        if missing:
            errors.append(f"[FAQ] {item.get('id', 'unknown')}: missing fields {missing}")
        if not item.get("id", "").startswith("faq-"):
            errors.append(f"[FAQ] id must start with 'faq-': {item.get('id')}")
    return errors


def validate_glossary(path: Path) -> list[str]:
    errors = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for item in data.get("items", []):
        missing = GLOSSARY_REQUIRED - set(item.keys())
        if missing:
            errors.append(f"[Glossary] {item.get('id', 'unknown')}: missing fields {missing}")
        if not item.get("id", "").startswith("term-"):
            errors.append(f"[Glossary] id must start with 'term-': {item.get('id')}")
    return errors


def main():
    base = Path(__file__).parent.parent
    faq_path = base / "data/faq/faq_master.json"
    glossary_path = base / "data/glossary/glossary_master.json"

    errors = []
    if faq_path.exists():
        errors += validate_faq(faq_path)
        print(f"FAQ: {faq_path} ... OK" if not errors else "")
    else:
        errors.append(f"FAQ file not found: {faq_path}")

    if glossary_path.exists():
        glossary_errors = validate_glossary(glossary_path)
        errors += glossary_errors
        if not glossary_errors:
            print(f"Glossary: {glossary_path} ... OK")
    else:
        errors.append(f"Glossary file not found: {glossary_path}")

    if errors:
        print("\n[VALIDATION ERRORS]")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\nAll data validated successfully.")


if __name__ == "__main__":
    main()
