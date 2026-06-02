"""
Root test conftest — sets env vars so pydantic-settings loads correctly.
App imports happen lazily inside fixtures (not at module level).
"""
import os

# Must be set before any app module import
os.environ.setdefault("SECRET_KEY", "test-secret-key-" + "x" * 50)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://test:test@localhost:5432/test_db")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
