import os
import sys
from pathlib import Path

from spooly.config import normalize_media_sources
from spooly.paths import get_database_path
from spooly.services.database import AppDatabase
from spooly.services.library import LibraryService, build_media_sources
from spooly.services.thumbnail import ThumbnailService
from .config import load_embedding_config
from .indexing import MediaIndexer


def run_vectorize(config, args, parser):
    media_root = args.media_root or os.environ.get('MEDIA_ROOT') or config.get('media_root')
    media_sources = normalize_media_sources(config, getattr(args, 'media_source', None), media_root=media_root)
    if not media_root and not media_sources:
        parser.error('Specify a media directory:\n  - spooly vectorize /path/to/media\n  - or configure media_root/media_sources')
    media_path = Path(media_root).expanduser() if media_root else Path(media_sources[0]['path']).expanduser()
    for source in media_sources:
        source_path = Path(str(source.get('path') or '')).expanduser()
        if not source_path.is_dir():
            print(f"Error: Media source unavailable {source.get('id')}: {source_path}", file=sys.stderr)
            sys.exit(1)
    try:
        embedding = load_embedding_config(config.get('embedding') or config.get('embedding_config'))
    except ValueError as exc:
        parser.error(str(exc))

    library = LibraryService(media_path, media_sources=build_media_sources(media_path, media_sources or None))
    database = AppDatabase(get_database_path())
    database.migrate()
    indexer = MediaIndexer(library, ThumbnailService(media_path, library_service=library), database, embedding)
    status = indexer.status()
    limit = max(int(args.limit or 0), 0)
    selected = min(status['pending'], limit) if limit else status['pending']

    print('Spooly media preparation')
    print(f"  service: {embedding['base_url']}")
    print(f"  model: {embedding['model']}")
    print(f"  photos: {status['images']}")
    print(f"  videos: {status['videos'] if status['videos_supported'] else 'skipped (ffmpeg not found)'}")
    print(f"  prepared: {status['prepared']}")
    print(f"  pending: {status['pending']}")
    print(f'  selected this run: {selected}')
    if args.dry_run:
        return
    if not args.yes and selected:
        if input(f'Send {selected} files to {embedding["base_url"]}? [y/N] ').strip().lower() not in {'y', 'yes'}:
            print('Canceled.')
            return

    def report(state, record=None, error=''):
        if record is None:
            return
        line = f"[{state['processed']}/{state['total']}] {record['uri']}"
        print(f'{line} failed: {error}' if error else f'{line} prepared', file=sys.stderr if error else sys.stdout)

    result = indexer.run(limit=limit, progress=report)
    if result['state'] == 'failed':
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"Done: {result['processed'] - result['failed']} prepared, {result['failed']} failed, "
          f"{result['groups']} photo groups.")
