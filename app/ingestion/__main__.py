"""Cho phép: uv run python -m app.ingestion [corpus.json]"""
import sys

from app.ingestion.pipeline import main

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
