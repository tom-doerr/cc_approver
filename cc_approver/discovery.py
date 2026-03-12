"""Auto-discover model name from vLLM/SGLang API base URL with caching."""
from __future__ import annotations
import json, logging, urllib.request, urllib.error
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_CACHE_PATH = Path.home() / ".cache" / "cc_approver" / "models.json"
_FETCH_TIMEOUT = 3  # seconds


def _load_cache() -> dict:
    try:
        return json.loads(MODEL_CACHE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    MODEL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n")


def _fetch_model_from_api(api_base: str) -> str:
    """Query {api_base}/models and return the first model ID."""
    url = api_base.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
        data = json.loads(resp.read())
    models = data.get("data", [])
    if not models:
        raise ValueError(f"No models found at {url}")
    return models[0]["id"]


def discover_model(api_base: str) -> str:
    """Return model name for an API base, using cache when possible."""
    cache = _load_cache()
    cached = cache.get(api_base)
    if cached:
        logger.debug(f"Model cache hit: {api_base} → {cached}")
        return cached
    logger.debug(f"Model cache miss, fetching from {api_base}")
    model = _fetch_model_from_api(api_base)
    cache[api_base] = model
    _save_cache(cache)
    return model


def refresh_model(api_base: str) -> str:
    """Force re-fetch model from API and update cache."""
    model = _fetch_model_from_api(api_base)
    cache = _load_cache()
    cache[api_base] = model
    _save_cache(cache)
    return model


def invalidate_cache(api_base: Optional[str] = None) -> None:
    """Remove cached entry for api_base, or clear entire cache."""
    if api_base is None:
        if MODEL_CACHE_PATH.exists():
            MODEL_CACHE_PATH.unlink()
        return
    cache = _load_cache()
    cache.pop(api_base, None)
    _save_cache(cache)
