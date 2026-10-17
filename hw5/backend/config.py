"""Paths, the one model every agent uses, and the limits that keep token use in check."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent  # hw5/
PROMPTS_DIR = BACKEND_DIR / "prompts"
MCP_SERVER_SCRIPT = REPO_ROOT / "mcp_server" / "server.py"

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

# hw5/.env first, then the parent folders (the course keeps one .env at its root).
for env_file in (REPO_ROOT / ".env", REPO_ROOT.parent / ".env", REPO_ROOT.parent.parent / ".env"):
    load_dotenv(env_file)

# Overridable only so tests can run against a scratch copy; defaults are the real files.
WORKING_DB = Path(os.getenv("CC_DB_PATH") or REPO_ROOT / "data" / "campus_customs_new.db").resolve()
AUDIT_TRAIL = Path(os.getenv("CC_AUDIT_PATH") or REPO_ROOT / "output" / "audit_trail.json").resolve()

# The ONLY model used by any agent. Deliberately not configurable from the environment.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# --- token and loop limits (also listed in output/harness.md) ---
MAX_DEPTH = 3  # Boss is depth 0; a chain of asks stops at depth 3
MAX_DELEGATIONS_PER_TICKET = 10  # asks between agents, shared by the whole team per ticket
MAX_OUTPUT_TOKENS = 4_000  # per model response
AUDIT_TEXT_LIMIT = 4_000  # characters kept per text field in the audit trail
MODEL_SETTINGS = ModelSettings(max_tokens=MAX_OUTPUT_TOKENS, parallel_tool_calls=True)


def require_api_key() -> str:
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return api_key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    """One Portkey-backed gpt-6-luna model shared by all five agents."""
    api_key = require_api_key()
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
