"""Prepare vectors for photos and sampled video frames, then refresh photo groups."""

import shutil
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from .embedding import EmbeddingClient, VectorStore, mean_vector
from .groups import rebuild_photo_groups


SERVICE_FAILURE_LIMIT = 3


def videos_supported() -> bool:
    return shutil.which('ffmpeg') is not None and shutil.which('ffprobe') is not None


class MediaIndexer:
    def __init__(self, library, thumbnails, database, config: dict):
        self.library = library
        self.thumbnails = thumbnails
        self.database = database
        self.config = config
        self.store = VectorStore(database, config['model'])

    def records(self) -> list[dict]:
        """Photos first, then videos, each newest first."""
        scanners = [('image', self.library.scan_images)]
        if videos_supported():
            scanners.append(('video', self.library.scan_videos))
        records = []
        for media_type, scan in scanners:
            batch = []
            for path in scan():
                try:
                    stat = path.stat()
                except OSError:
                    continue
                batch.append({'uri': self.library.get_relative_path(path), 'path': path,
                              'media_type': media_type, 'mtime': stat.st_mtime, 'size_bytes': stat.st_size})
            records.extend(sorted(batch, key=lambda record: (-record['mtime'], record['uri'])))
        return records

    def pending(self, records: list[dict] | None = None) -> list[dict]:
        """Files without a vector from the configured model, or changed since they were indexed."""
        states = self.store.states()
        return [record for record in (self.records() if records is None else records)
                if states.get(record['uri']) != (record['mtime'], record['size_bytes'], True)]

    def status(self) -> dict:
        records = self.records()
        pending = len(self.pending(records))
        return {'images': sum(record['media_type'] == 'image' for record in records),
                'videos': sum(record['media_type'] == 'video' for record in records),
                'total': len(records), 'prepared': len(records) - pending, 'pending': pending,
                'videos_supported': videos_supported()}

    def index(self, record: dict, client: EmbeddingClient, *, should_stop=lambda: False) -> bool:
        frames = None
        if record['media_type'] == 'video':
            with TemporaryDirectory(prefix='spooly-video-') as directory:
                sources = self.thumbnails.sample_video_frames(record['uri'], Path(directory))
                frames = []
                for source in sources:
                    if should_stop():
                        return False
                    frames.append(client.embed_image(source))
            vector = mean_vector(frames)
        else:
            vector = client.embed_image(record['path'])
        self.store.upsert(uri=record['uri'], media_type=record['media_type'], mtime=record['mtime'],
                          size_bytes=record['size_bytes'], vector=vector, frames=frames)
        return True

    def run(self, *, limit: int = 0, should_stop=lambda: False, progress=lambda state, record=None, error='': None) -> dict:
        """Index pending files, then regroup photos; return the final state."""
        pending = self.pending()
        if limit > 0:
            pending = pending[:limit]
        client = EmbeddingClient(self.config)
        state = {'state': 'running', 'total': len(pending), 'processed': 0, 'failed': 0, 'groups': 0, 'error': ''}
        progress(dict(state))
        service_failures = 0
        for record in pending:
            if should_stop():
                return {**state, 'state': 'paused'}
            error = ''
            try:
                if not self.index(record, client, should_stop=should_stop):
                    return {**state, 'state': 'paused'}
                service_failures = 0
            except RuntimeError as exc:
                # Service errors repeat for every file, so stop instead of exhausting the queue.
                error = str(exc)
                service_failures += 1
            except Exception as exc:
                # A damaged file is skipped and retried on the next run.
                error = str(exc) or type(exc).__name__
            state['processed'] += 1
            state['failed'] += bool(error)
            progress(dict(state), record, error)
            if service_failures >= SERVICE_FAILURE_LIMIT:
                return {**state, 'state': 'failed',
                        'error': f'The embedding service failed three times in a row: {error[:300]}'}
        state['state'] = 'grouping'
        progress(dict(state))
        groups = rebuild_photo_groups(self.library, self.database, self.config['model'], should_stop=should_stop)
        if groups is None:
            return {**state, 'state': 'paused'}
        return {**state, 'state': 'done', 'groups': groups}


class IndexJob:
    """One background preparation per Spooly process; progress is kept in memory."""

    def __init__(self, indexer: MediaIndexer):
        self.indexer = indexer
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._state = {'state': 'idle', 'total': 0, 'processed': 0, 'failed': 0, 'groups': 0, 'error': ''}

    def status(self) -> dict:
        with self._lock:
            return dict(self._state)

    def start(self) -> dict:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError('Preparation is already running.')
            self._stop = threading.Event()
            self._state = {**self._state, 'state': 'running', 'total': 0, 'processed': 0,
                           'failed': 0, 'groups': 0, 'error': ''}
            self._thread = threading.Thread(target=self._run, args=(self._stop,), name='media-index', daemon=True)
            self._thread.start()
            return dict(self._state)

    def pause(self) -> dict:
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._stop.set()
                self._state['state'] = 'pausing'
            return dict(self._state)

    def _run(self, stop: threading.Event) -> None:
        def update(state, record=None, error=''):
            with self._lock:
                self._state.update(state)
                if stop.is_set() and state['state'] == 'running':
                    self._state['state'] = 'pausing'
        try:
            update(self.indexer.run(should_stop=stop.is_set, progress=update))
        except Exception as exc:
            update({'state': 'failed', 'error': str(exc)})
