"""
config/langfuse_setup.py  — FIXED for Langfuse v3
──────────────────────────────────────────────────
Langfuse v3 uses OpenTelemetry. No more get_langchain_callback().
Tracing is handled via @observe decorators on agent functions.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
_HOST       = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
_ENABLED    = bool(_PUBLIC_KEY and _SECRET_KEY)

_langfuse_client = None

if _ENABLED:
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            public_key=_PUBLIC_KEY,
            secret_key=_SECRET_KEY,
            host=_HOST,
        )
        print("✅ Langfuse v3 initialized (OTel tracing active)")
    except Exception as exc:
        print(f"⚠️  Langfuse init error: {exc}")
        _ENABLED = False


def get_langfuse_config(target_date: str, agent_name: str) -> dict:
    """
    Returns {} — safe to pass as config= in any .ainvoke() call.
    Tracing is handled by @observe decorators on each agent node.
    """
    return {}


def get_langfuse_client():
    return _langfuse_client


def is_enabled() -> bool:
    return _ENABLED and _langfuse_client is not None