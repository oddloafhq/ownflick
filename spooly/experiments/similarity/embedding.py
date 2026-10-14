"""Embedding API client and the local vector table for the configured model."""

import base64
import datetime
import io
import math
from array import array
from pathlib import Path

import requests
from PIL import Image, ImageOps

from spooly.services.database import AppDatabase


DIMENSIONS = 768
IMAGE_MAX_SIZE = 512
IMAGE_QUALITY = 82
REQUEST_TIMEOUT = 180
EMBEDDINGGEMMA_MODELS = ('embeddinggemma-2', 'google/embeddinggemma-2')


class EmbeddingClient:
    def __init__(self, config: dict):
        self.base_url = config['base_url']
        self.model = config['model']
        self.api_key = config.get('api_key')

    def embed_image(self, path: Path) -> list[float]:
        data_url = 'data:image/jpeg;base64,' + base64.b64encode(encode_image(path)).decode('ascii')
        return self._request([{'content': [{'type': 'image_url', 'image_url': {'url': data_url}}]}])

    def embed_text(self, query: str) -> list[float]:
        if self.model in EMBEDDINGGEMMA_MODELS:
            query = 'task: search result | query: ' + query
        return self._request([query])

    def _request(self, input_items: list) -> list[float]:
        headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        try:
            response = requests.post(f'{self.base_url}/embeddings', headers=headers, timeout=REQUEST_TIMEOUT,
                                     json={'model': self.model, 'input': input_items,
                                           'encoding_format': 'float', 'dimensions': DIMENSIONS})
            data = response.json() if response.content else {}
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(self._redact(str(exc) or 'The embedding service did not respond.')) from None
        error = data.get('error') if isinstance(data, dict) else None
        if response.status_code >= 400 or error:
            message = error.get('message') if isinstance(error, dict) else error
            raise RuntimeError(self._redact(str(message or f'HTTP {response.status_code}')))
        try:
            vector = list(array('f', data['data'][0]['embedding']))
        except (KeyError, IndexError, TypeError):
            raise RuntimeError('The embedding service returned no usable vector.') from None
        if len(vector) != DIMENSIONS or not all(math.isfinite(value) for value in vector) or not any(vector):
            raise RuntimeError(f'Expected a finite, nonzero {DIMENSIONS}-dimension vector.')
        return vector

    def _redact(self, text: str) -> str:
        return text.replace(self.api_key, '[redacted]') if self.api_key else text


def encode_image(path: Path) -> bytes:
    """Return a small JPEG of the pixels only; EXIF, GPS and other metadata are dropped."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((IMAGE_MAX_SIZE, IMAGE_MAX_SIZE), Image.Resampling.LANCZOS)
        if 'A' in image.getbands():
            rgba = image.convert('RGBA')
            image = Image.new('RGB', rgba.size, (255, 255, 255))
            image.paste(rgba, mask=rgba.getchannel('A'))
        buffer = io.BytesIO()
        image.convert('RGB').save(buffer, format='JPEG', quality=IMAGE_QUALITY, optimize=True)
    return buffer.getvalue()


class VectorStore:
    """One vector per file; rows from another model are ignored until they are rebuilt."""

    def __init__(self, database: AppDatabase, model: str):
        self.database = database
        self.model = model

    def states(self) -> dict[str, tuple[float, int]]:
        with self.database.connect() as conn:
            rows = conn.execute('SELECT uri, mtime, size_bytes FROM media_vectors WHERE model = ?',
                                (self.model,)).fetchall()
        return {row['uri']: (row['mtime'], row['size_bytes']) for row in rows}

    def count(self, media_type: str | None = None) -> int:
        with self.database.connect() as conn:
            return conn.execute('SELECT COUNT(*) FROM media_vectors WHERE model = ? '
                                'AND (? IS NULL OR media_type = ?)',
                                (self.model, media_type, media_type)).fetchone()[0]

    def upsert(self, *, uri: str, media_type: str, mtime: float, size_bytes: int, vector: list[float]) -> None:
        indexed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.database.connect() as conn:
            conn.execute("""
                INSERT INTO media_vectors(uri, media_type, model, mtime, size_bytes, embedding, embedding_norm, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uri) DO UPDATE SET media_type = excluded.media_type, model = excluded.model,
                  mtime = excluded.mtime, size_bytes = excluded.size_bytes, embedding = excluded.embedding,
                  embedding_norm = excluded.embedding_norm, indexed_at = excluded.indexed_at
            """, (uri, media_type, self.model, mtime, size_bytes, array('f', vector).tobytes(),
                  _norm(vector), indexed_at))

    def vectors(self, media_type: str | None = None, *, limit: int = -1) -> list[dict]:
        """Return rows newest first by file modification time."""
        with self.database.connect() as conn:
            rows = conn.execute('SELECT uri, media_type, embedding, embedding_norm FROM media_vectors '
                                'WHERE model = ? AND (? IS NULL OR media_type = ?) '
                                'ORDER BY mtime DESC, uri LIMIT ?',
                                (self.model, media_type, media_type, limit)).fetchall()
        return [{'uri': row['uri'], 'media_type': row['media_type'], 'norm': row['embedding_norm'],
                 'vector': array('f', row['embedding'])} for row in rows]

    def rank(self, vector, media_type: str | None = None) -> list[dict]:
        """Rank stored vectors by cosine similarity; callers skip files that are gone."""
        return _ranked(vector, self.vectors(media_type))

    def similar(self, uri: str) -> list[dict]:
        rows = self.vectors('image')
        query = next((row for row in rows if row['uri'] == uri), None)
        return _ranked(query['vector'], [row for row in rows if row is not query]) if query else []


def _ranked(vector, rows: list[dict]) -> list[dict]:
    norm = _norm(vector)
    scored = [{'uri': row['uri'], 'media_type': row['media_type'],
               'score': cosine(vector, norm, row['vector'], row['norm'])} for row in rows]
    return sorted(scored, key=lambda item: (-item['score'], item['uri']))


def cosine(left, left_norm: float, right, right_norm: float) -> float:
    if len(left) != len(right) or left_norm <= 0 or right_norm <= 0:
        return -1.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _norm(vector) -> float:
    return math.sqrt(sum(value * value for value in vector))
