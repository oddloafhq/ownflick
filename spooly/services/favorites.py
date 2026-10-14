import json
from threading import RLock
from pathlib import Path

from spooly.services.library import LibraryService, normalize_media_uri

from spooly.services.json_storage import write_json_atomic


class FavoriteService:
    def __init__(
        self,
        db_path: Path,
        library_service: LibraryService,
    ):
        self.db_path = db_path
        self.library_service = library_service
        self._lock = RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _normalize(self, filename: str) -> str:
        return self.library_service.canonicalize_uri(filename)

    def _read_raw(self, path: Path) -> set[str]:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return set()
        if not isinstance(data, list):
            raise ValueError('Invalid favorites file format')
        return {normalize_media_uri(item) for item in data}

    def load(self) -> set[str]:
        return self.library_service.canonicalize_many(self._read_raw(self.db_path))

    def save(self, favorites: set[str]) -> None:
        with self._lock:
            write_json_atomic(self.db_path, sorted(self._normalize(item) for item in favorites if normalize_media_uri(item)))

    def toggle(self, filename: str) -> bool:
        """Toggle and persist within one read-modify-write critical section."""
        with self._lock:
            favs = self.load()
            key = self._normalize(filename)
            return self._save_state(favs, key, key not in favs)

    def set_favorite(self, filename: str, is_favorite: bool) -> bool:
        """Set favorite state idempotently and return the persisted state."""
        with self._lock:
            return self._save_state(self.load(), self._normalize(filename), bool(is_favorite))

    def _save_state(self, favs: set[str], key: str, is_favorite: bool) -> bool:
        if is_favorite:
            favs.add(key)
        else:
            favs.discard(key)
        self.save(favs)
        return is_favorite

    def is_favorite(self, filename: str) -> bool:
        return self._normalize(filename) in self.load()
