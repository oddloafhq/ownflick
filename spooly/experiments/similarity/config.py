"""Read the embedding connection from config.yaml; the Web UI only displays it."""

import os
from urllib.parse import urlsplit


DEFAULT_BASE_URL = 'https://openrouter.ai/api/v1'
DEFAULT_MODEL = 'google/gemini-embedding-2'
API_KEY_VARIABLES = ('SPOOLY_EMBEDDING_API_KEY', 'SPOOLY_AI_API_KEY', 'OPENAI_API_KEY', 'OPENROUTER_API_KEY')


def load_embedding_config(raw) -> dict:
    """Return the base URL, model and API key, or raise ValueError for unusable settings."""
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ValueError('embedding must be a configuration object')
    base_url = str(raw.get('base_url') or DEFAULT_BASE_URL).strip().rstrip('/')
    try:
        url = urlsplit(base_url)
        _ = url.port
    except ValueError:
        url = None
    if (not url or url.scheme not in ('http', 'https') or not url.hostname
            or url.username or url.password or url.query or url.fragment):
        raise ValueError('embedding.base_url must be a plain http:// or https:// URL')
    model = str(raw.get('model_name') or raw.get('model') or DEFAULT_MODEL).strip()
    api_key = raw.get('api_key')
    if api_key is not None and not isinstance(api_key, str):
        raise ValueError('embedding.api_key must be a string')
    key_source = 'config' if api_key else 'environment'
    if not api_key:
        api_key = next((os.environ[name] for name in API_KEY_VARIABLES if os.environ.get(name)), None)
    return {'base_url': base_url, 'model': model, 'api_key': api_key,
            'key_source': key_source if api_key else 'none'}
