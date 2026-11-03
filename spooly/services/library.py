import os
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PureWindowsPath
from typing import Any

from spooly.services.trash import TRASH_DIR

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.mkv', '.avi', '.m4v'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.aac', '.m4a', '.ogg', '.opus', '.wav'}


@dataclass(frozen=True)
class MediaSource:
    id: str
    name: str
    path: Path
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class MediaRef:
    source_id: str
    rel_path: str

    def to_uri(self) -> str:
        return f"@{self.source_id}/{self.rel_path}"


def normalize_source_id(value: Any) -> str:
    text = str(value or '').strip().lower()
    cleaned = ''.join(ch for ch in text if ch.isalnum() or ch in {'-', '_'})
    return cleaned or 'default'


def normalize_media_uri(value: Any) -> str:
    text = str(value or '').strip().replace('\\', '/')
    while text.startswith('./'):
        text = text[2:]
    return text


def normalize_exclusions(value: Any, *, field: str = 'exclude') -> tuple[str, ...]:
    """Validate filename and source-relative path patterns for media exclusion."""
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{field} must be a list of non-empty strings')
    patterns = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f'{field} must be a list of non-empty strings')
        pattern = normalize_media_uri(item).casefold()
        if (
            not pattern or pattern.startswith(('/', '!')) or PureWindowsPath(pattern).drive
            or '..' in pattern.split('/')
        ):
            raise ValueError(f'{field} patterns must be relative and cannot use .. or negation')
        patterns.append(pattern)
    return tuple(dict.fromkeys(patterns))


def build_media_sources(media_root: str | Path | None = None, raw_sources: Any = None) -> list[MediaSource]:
    sources: list[MediaSource] = []
    seen: set[str] = set()

    def add_source(source_id: Any, name: Any, path_value: Any, exclude: Any = None) -> None:
        path_text = str(path_value or '').strip()
        if not path_text:
            return
        sid = normalize_source_id(source_id)
        if sid in seen:
            return
        seen.add(sid)
        sources.append(MediaSource(
            id=sid,
            name=str(name or sid).strip() or sid,
            path=Path(path_text).expanduser().resolve(),
            exclude=normalize_exclusions(exclude, field=f'media_sources[{sid}].exclude'),
        ))

    if raw_sources:
        if isinstance(raw_sources, dict):
            iterable = [{'id': key, 'name': key, 'path': value} for key, value in raw_sources.items()]
        else:
            iterable = raw_sources if isinstance(raw_sources, list) else []
        for item in iterable:
            if isinstance(item, dict):
                add_source(
                    item.get('id') or item.get('name'), item.get('name') or item.get('id'),
                    item.get('path'), item.get('exclude'),
                )

    if media_root and 'default' not in seen:
        # The CLI may use the first configured source as the legacy default root.
        # That alias must not bypass the source's exclusion rules.
        root = Path(media_root).expanduser().resolve()
        alias = next((source for source in sources if source.path == root), None)
        add_source('default', 'Default', media_root, alias.exclude if alias else None)

    return sources


class LibraryService:
    def __init__(
        self, media_root: str | Path | None = None, media_sources: list[MediaSource] | None = None,
        *, exclude: Any = None,
    ):
        self.exclude = normalize_exclusions(exclude)
        self.sources = media_sources or build_media_sources(media_root)
        if not self.sources:
            self.sources = build_media_sources(media_root or '.')
        self.sources_by_id = {source.id: source for source in self.sources}
        self.default_source_id = 'default' if 'default' in self.sources_by_id else self.sources[0].id
        self.media_root = self.sources_by_id[self.default_source_id].path

    def is_excluded(self, uri: str, *, is_dir: bool = False) -> bool:
        """Match a media URI or directory and its ancestors without accessing the filesystem."""
        ref = self.parse_uri(uri)
        if ref is None:
            return False
        patterns = self.exclude + self.sources_by_id[ref.source_id].exclude
        if not patterns:
            return False
        parts = ref.rel_path.casefold().split('/')
        for index, name in enumerate(parts):
            directory = is_dir or index < len(parts) - 1
            relative_path = '/'.join(parts[:index + 1])
            for pattern in patterns:
                if pattern.endswith('/') and not directory:
                    continue
                pattern = pattern.rstrip('/')
                candidate = relative_path if '/' in pattern else name
                if fnmatchcase(candidate, pattern):
                    return True
        return False

    def scan_source(
        self, source: MediaSource, extensions: set[str] | None = None, *, recursive: bool = True,
    ) -> list[Path]:
        """Scan one source, raising on incomplete traversal rather than returning an empty snapshot."""
        extensions = extensions if extensions is not None else VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS

        def fail(error: OSError) -> None:
            raise error

        paths = []
        for directory, folders, files in os.walk(source.path, onerror=fail):
            relative_dir = Path(directory).relative_to(source.path)
            if not recursive:
                folders.clear()
            else:
                folders[:] = [
                    name for name in folders
                    if name != TRASH_DIR and not self.is_excluded(
                        MediaRef(source.id, (relative_dir / name).as_posix()).to_uri(), is_dir=True,
                    )
                ]
            paths.extend(
                Path(directory) / name for name in files
                if Path(name).suffix.lower() in extensions
                and not self.is_excluded(MediaRef(source.id, (relative_dir / name).as_posix()).to_uri())
            )
        return paths

    def _scan_available_sources(self, extensions: set[str], recursive: bool) -> list[Path]:
        paths = []
        for source in self.sources:
            try:
                paths.extend(self.scan_source(source, extensions, recursive=recursive))
            except OSError:
                continue
        return paths

    def scan_videos(self, recursive=True) -> list[Path]:
        return sorted(self._scan_available_sources(VIDEO_EXTENSIONS, recursive), key=lambda p: p.stat().st_mtime, reverse=True)

    def scan_audios(self, recursive=True) -> list[Path]:
        return sorted(self._scan_available_sources(AUDIO_EXTENSIONS, recursive), key=lambda p: p.stat().st_mtime, reverse=True)

    def scan_images(self, recursive=True) -> list[Path]:
        return self._scan_available_sources(IMAGE_EXTENSIONS, recursive)

    def get_relative_path(self, path: Path) -> str:
        ref = self.ref_for_path(path)
        return ref.to_uri() if ref else str(path)

    def ref_for_path(self, path: Path) -> MediaRef | None:
        target = path.resolve()
        for source in self.sources:
            try:
                rel = str(target.relative_to(source.path.resolve())).replace('\\', '/')
                return MediaRef(source.id, rel)
            except ValueError:
                continue
        return None

    def parse_uri(self, uri: str) -> MediaRef | None:
        clean = normalize_media_uri(uri)
        if not clean:
            return None
        if clean.startswith('@'):
            source_text, sep, rel_path = clean[1:].partition('/')
            source_id = normalize_source_id(source_text)
            rel_path = normalize_media_uri(rel_path)
            if sep and source_id in self.sources_by_id and rel_path:
                return MediaRef(source_id, rel_path)
            return None
        return MediaRef(self.default_source_id, clean)

    def canonicalize_uri(self, uri: str) -> str:
        ref = self.parse_uri(uri)
        return ref.to_uri() if ref else normalize_media_uri(uri)

    def legacy_candidates(self, uri: str) -> list[str]:
        clean = normalize_media_uri(uri)
        ref = self.parse_uri(clean)
        if not ref:
            return [clean] if clean else []
        candidates = [ref.to_uri()]
        if ref.source_id == self.default_source_id:
            candidates.append(ref.rel_path)
        return list(dict.fromkeys([item for item in candidates if item]))

    def is_uri_in_set(self, uri: str, values: set[str]) -> bool:
        return any(candidate in values for candidate in self.legacy_candidates(uri))

    def canonicalize_many(self, values: set[str]) -> set[str]:
        return {self.canonicalize_uri(value) for value in values if normalize_media_uri(value)}

    def source_for_uri(self, uri: str) -> MediaSource | None:
        ref = self.parse_uri(uri)
        return self.sources_by_id.get(ref.source_id) if ref else None

    def relative_path_for_uri(self, uri: str) -> str:
        ref = self.parse_uri(uri)
        return ref.rel_path if ref else normalize_media_uri(uri)

    def canonicalize_outputs(self, rel_paths: list[str], *, source_id: str | None = None) -> list[str]:
        sid = source_id or self.default_source_id
        outputs: list[str] = []
        for rel_path in rel_paths:
            clean = normalize_media_uri(rel_path)
            if not clean:
                continue
            outputs.append(self.canonicalize_uri(clean) if clean.startswith('@') else MediaRef(sid, clean).to_uri())
        return outputs

    def resolve_source_relative_path(self, uri: str) -> tuple[MediaSource, str] | None:
        ref = self.parse_uri(uri)
        if not ref:
            return None
        source = self.sources_by_id.get(ref.source_id)
        if not source:
            return None
        return source, ref.rel_path

    def resolve_path(self, relative_path: str) -> Path | None:
        """Securely resolve a media URI to an absolute path within its media source."""
        resolved = self.resolve_source_relative_path(relative_path)
        if not resolved:
            return None
        source, rel_path = resolved
        try:
            target = (source.path / rel_path).resolve()
            target.relative_to(source.path.resolve())
            return target
        except Exception:
            return None

    def find_existing_uri(self, uri: str) -> str:
        for candidate in self.legacy_candidates(uri):
            target = self.resolve_path(candidate)
            if target and target.exists():
                return candidate
        return self.canonicalize_uri(uri)
