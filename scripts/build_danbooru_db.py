"""Descarga los tags de Danbooru desde HuggingFace y crea una base de datos SQLite local.

Uso:
    python scripts/build_danbooru_db.py

El script descarga el archivo tags.jsonl de https://huggingface.co/datasets/qdlabs/danbooru-tags,
filtra los tags con post_count >= 20 y los inserta en data/danbooru_tags.db.
"""

import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

DATASET_URL = "https://huggingface.co/datasets/qdlabs/danbooru-tags/resolve/main/tags.jsonl"
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "danbooru_tags.db"
MIN_POST_COUNT = 20


def download_jsonl(url: str, dest: Path) -> Path:
    """Descarga el archivo JSONL desde HuggingFace."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path = dest.parent / "tags.jsonl"

    if jsonl_path.exists():
        size_mb = jsonl_path.stat().st_size / (1024 * 1024)
        print(f"  tags.jsonl ya existe ({size_mb:.1f} MB), reutilizando...")
        return jsonl_path

    print(f"  Descargando desde {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "DanbooruDBBuilder/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(jsonl_path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded / total * 100
                    print(f"\r  {downloaded / (1024*1024):.1f} MB / {total / (1024*1024):.1f} MB ({pct:.0f}%)", end="", flush=True)
    print()
    return jsonl_path


def build_database(jsonl_path: Path, db_path: Path, min_post_count: int) -> int:
    """Parsea el JSONL y crea la base de datos SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE tags (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            danbooru_id INTEGER,
            name       TEXT    NOT NULL,
            category   INTEGER NOT NULL DEFAULT 0,
            post_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute("CREATE INDEX idx_tags_name ON tags(name)")
    cur.execute("CREATE INDEX idx_tags_category ON tags(category)")
    cur.execute("CREATE INDEX idx_tags_post_count ON tags(post_count DESC)")

    inserted = 0
    skipped = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            post_count = row.get("post_count", 0)
            is_deprecated = row.get("is_deprecated", False)

            if post_count < min_post_count or is_deprecated:
                skipped += 1
                continue

            cur.execute(
                "INSERT INTO tags (danbooru_id, name, category, post_count) VALUES (?, ?, ?, ?)",
                (row.get("id"), row["name"], row.get("category", 0), post_count),
            )
            inserted += 1

            if inserted % 10000 == 0:
                print(f"\r  {inserted} tags insertados...", end="", flush=True)

    conn.commit()
    conn.close()
    print()
    return inserted


def main():
    print("=" * 60)
    print("  Danbooru Tags DB Builder")
    print("=" * 60)
    print(f"  Fuente:    {DATASET_URL}")
    print(f"  Destino:   {DB_PATH}")
    print(f"  Filtro:    post_count >= {MIN_POST_COUNT}")
    print()

    print("[1/2] Descargando dataset...")
    jsonl_path = download_jsonl(DATASET_URL, DB_PATH)

    print("[2/2] Construyendo base de datos SQLite...")
    count = build_database(jsonl_path, DB_PATH, MIN_POST_COUNT)

    size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"\n  Listo: {count:,} tags insertados en {DB_PATH.name} ({size_mb:.1f} MB)")
    print(f"  Ruta: {DB_PATH}")


if __name__ == "__main__":
    main()
