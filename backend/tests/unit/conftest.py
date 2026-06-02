"""
Minimal conftest for unit tests.
Sets env vars BEFORE any app import so pydantic-settings reads them.
No DB, no HTTP client, no LLM.
"""
import os

os.environ["SECRET_KEY"] = "unit-test-secret-key-" + "x" * 50
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_db"
os.environ["DATABASE_URL_SYNC"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = "sk-unit-test-key"
