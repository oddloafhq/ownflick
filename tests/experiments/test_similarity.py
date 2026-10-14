import base64
import io
import json
import shutil
import subprocess
import sys
import threading
import time
from array import array
from types import SimpleNamespace

import pytest
from PIL import Image
from requests import Response

from spooly.app import create_app
from spooly.experiments.similarity.config import load_embedding_config
from spooly.experiments.similarity.embedding import DIMENSIONS, EmbeddingClient, VectorStore, mean_vector
from spooly.experiments.similarity.groups import choose_groups
from spooly.paths import get_database_path
from spooly.run import main
from spooly.services.database import AppDatabase, MIGRATIONS
from spooly.web.flow import build_mix_feed_page


def unit(index: int) -> list[float]:
    return [float(position == index) for position in range(DIMENSIONS)]


@pytest.fixture
def similarity(tmp_path, monkeypatch):
    media = tmp_path / 'media'
    media.mkdir()
    for name in ('a.jpg', 'b.jpg', 'c.jpg'):
        Image.new('RGB', (640, 320), 'red').save(media / name)
    config = {'base_url': 'https://embedding.example/v1', 'model_name': 'fixture-embedding'}
    # Numerical protocol fixture: this does not evaluate model or retrieval quality.
    wire = SimpleNamespace(calls=[], status=200, body={'data': [{'embedding': unit(0)}]})

    def post(url, **kwargs):
        wire.calls.append({'url': url, **kwargs})
        response = Response()
        response.status_code = wire.status
        response._content = json.dumps(wire.body).encode()
        return response

    monkeypatch.setattr('spooly.experiments.similarity.embedding.requests.post', post)
    monkeypatch.setattr('spooly.experiments.similarity.indexing.shutil.which', lambda _name: None)
    monkeypatch.setenv('SPOOLY_EMBEDDING_API_KEY', 'test-key')
    monkeypatch.setenv('HOME', str(tmp_path))
    yaml_config = {'experiments': {'similarity': {'enabled': True}}, 'embedding': config}
    config_path = tmp_path / '.config/spooly/config.yaml'
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(yaml_config))

    def open_app(embedding=config):
        return create_app({'TESTING': True, 'MEDIA_ROOT': media, 'EMBEDDING_CONFIG': embedding,
                           'EXPERIMENTS': yaml_config['experiments']}).test_client()

    def run_cli(*args):
        monkeypatch.setattr(sys, 'argv', ['spooly', 'vectorize', str(media), *args])
        main()

    client = open_app()
    return SimpleNamespace(client=client, open_app=open_app, media=media, wire=wire, run_cli=run_cli,
                           store=VectorStore(AppDatabase(get_database_path()), 'fixture-embedding'))


def wait_for_job(client, states=('done', 'failed')):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get('/api/ai/embedding-index/job').json['data']
        if job['state'] in states:
            return job
        time.sleep(0.01)
    raise AssertionError(job)


def test_preparation_builds_vectors_and_groups_once(similarity):
    assert similarity.client.get('/experiments/similarity').status_code == 200
    assert similarity.client.get('/api/recommend/similar?uri=a.jpg').json['data']['items'] == []
    assert similarity.wire.calls == []

    assert similarity.client.post('/api/ai/embedding-index/run').status_code == 202
    job = wait_for_job(similarity.client)
    assert (job['state'], job['processed'], job['failed'], job['groups']) == ('done', 3, 0, 1)
    groups = similarity.client.get('/api/library/similar-groups').json['data']['items']
    assert len(groups) == 1 and groups[0]['count'] == 3
    assert len(similarity.client.get('/api/recommend/similar?uri=a.jpg').json['data']['items']) == 2
    assert similarity.client.get('/library?view=explore').status_code == 200

    # Current files are skipped; a second run only regroups.
    assert similarity.client.post('/api/ai/embedding-index/run').status_code == 202
    assert wait_for_job(similarity.client)['processed'] == 0
    assert len(similarity.wire.calls) == 3


def test_image_request_sends_small_jpeg_without_metadata(similarity):
    exif = Image.Exif()
    exif[0x010F] = 'Private Camera'
    Image.new('RGB', (2000, 1000), 'blue').save(similarity.media / 'a.jpg', exif=exif)
    similarity.run_cli('--yes')
    call = similarity.wire.calls[0]  # The rewritten photo is newest, so it is sent first.
    assert call['url'] == 'https://embedding.example/v1/embeddings'
    assert call['headers']['Authorization'] == 'Bearer test-key'
    assert call['json']['dimensions'] == DIMENSIONS
    encoded = call['json']['input'][0]['content'][0]['image_url']['url'].split(',', 1)[1]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as sent:
        assert sent.format == 'JPEG' and max(sent.size) <= 512
        assert not sent.getexif()


def test_service_failures_stop_the_run_and_keep_previous_vectors(similarity):
    similarity.run_cli('--yes')
    for name in ('d.jpg', 'e.jpg', 'f.jpg', 'g.jpg'):
        Image.new('RGB', (64, 64), 'green').save(similarity.media / name)
    similarity.wire.status = 503
    similarity.wire.body = {'error': 'Service unavailable'}
    similarity.wire.calls.clear()
    assert similarity.client.post('/api/ai/embedding-index/run').status_code == 202
    job = wait_for_job(similarity.client)
    assert job['state'] == 'failed' and 'Service unavailable' in job['error']
    assert len(similarity.wire.calls) == 3
    assert similarity.store.count() == 3


def test_damaged_file_is_skipped_without_stopping(similarity):
    for name in ('broken-1.jpg', 'broken-2.jpg', 'broken-3.jpg'):
        (similarity.media / name).write_bytes(b'not an image')
    assert similarity.client.post('/api/ai/embedding-index/run').status_code == 202
    job = wait_for_job(similarity.client)
    assert (job['state'], job['processed'], job['failed']) == ('done', 6, 3)
    assert similarity.store.count() == 3


@pytest.mark.parametrize('vector', [[0.0] * DIMENSIONS, [float('nan')] * DIMENSIONS, [1.0] * 128])
def test_unusable_vectors_are_not_stored(similarity, vector):
    similarity.wire.body = {'data': [{'embedding': vector}]}
    assert similarity.client.post('/api/ai/embedding-index/run').status_code == 202
    assert wait_for_job(similarity.client)['state'] == 'failed'
    assert similarity.store.count() == 0


def test_preparation_pauses_after_current_request_and_resumes(similarity, monkeypatch):
    from spooly.experiments.similarity import embedding
    original_post = embedding.requests.post
    entered, release = threading.Event(), threading.Event()

    def slow_post(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original_post(*args, **kwargs)

    monkeypatch.setattr(embedding.requests, 'post', slow_post)
    assert similarity.client.post('/api/ai/embedding-index/run').status_code == 202
    assert entered.wait(3)
    assert similarity.client.post('/api/ai/embedding-index/pause').json['data']['state'] == 'pausing'
    release.set()
    job = wait_for_job(similarity.client, ('paused',))
    assert job['processed'] == 1 and similarity.store.count() == 1
    assert similarity.client.post('/api/ai/embedding-index/run').status_code == 202
    assert wait_for_job(similarity.client)['state'] == 'done'
    assert similarity.store.count() == 3


def test_changed_model_ignores_old_vectors_until_rebuilt(similarity):
    similarity.run_cli('--yes')
    other = similarity.open_app({'base_url': 'https://embedding.example/v1', 'model_name': 'other-model'})
    assert other.get('/api/recommend/similar?uri=a.jpg').json['data']['items'] == []
    similarity.wire.calls.clear()
    assert other.post('/api/library/media-search', json={'query': 'red'}).status_code == 409
    assert similarity.wire.calls == []
    assert other.post('/api/ai/embedding-index/run').status_code == 202
    assert wait_for_job(other)['processed'] == 3
    assert similarity.store.count() == 0
    assert VectorStore(similarity.store.database, 'other-model').count() == 3


def test_changed_file_is_prepared_again(similarity):
    similarity.run_cli('--yes')
    Image.new('RGB', (64, 64), 'blue').save(similarity.media / 'b.jpg')
    similarity.wire.calls.clear()
    similarity.run_cli('--yes')
    assert len(similarity.wire.calls) == 1


def test_text_search_ranks_existing_media_with_one_request(similarity):
    similarity.run_cli('--yes')
    similarity.store.upsert(uri='@default/b.jpg', media_type='image', mtime=0, size_bytes=0, vector=unit(1))
    similarity.wire.calls.clear()
    result = similarity.client.post('/api/library/media-search', json={'query': '海边的日落'})
    items = result.json['data']['items']
    assert len(items) == 3 and items[-1]['name'] == '@default/b.jpg'
    assert items[0]['score'] > items[-1]['score']
    assert similarity.wire.calls[0]['json']['input'] == ['海边的日落']
    (similarity.media / 'a.jpg').unlink()
    result = similarity.client.post('/api/library/media-search', json={'query': '海边', 'media_type': 'image'})
    assert '@default/a.jpg' not in [item['name'] for item in result.json['data']['items']]
    assert len(similarity.wire.calls) == 2


def test_text_search_matches_a_video_by_its_closest_frame(similarity):
    photo = [0.0] * DIMENSIONS
    photo[0], photo[1] = 0.8, 0.6
    frames = [unit(0), unit(1), unit(2)]
    (similarity.media / 'clip.mp4').write_bytes(b'video')
    similarity.store.upsert(uri='@default/a.jpg', media_type='image', mtime=0, size_bytes=0, vector=photo)
    similarity.store.upsert(uri='@default/clip.mp4', media_type='video', mtime=0, size_bytes=5,
                            vector=mean_vector(frames), frames=frames)
    items = similarity.client.post('/api/library/media-search', json={'query': 'red'}).json['data']['items']
    assert [(item['name'], item['score']) for item in items] == [
        ('@default/clip.mp4', pytest.approx(1)), ('@default/a.jpg', pytest.approx(0.8))]


@pytest.mark.parametrize('payload', [{'query': ''}, {'query': '  '}, {'query': None}, {'query': 123},
                                     {'query': 'x' * 201}, {'query': 'red', 'media_type': 'audio'}])
def test_text_search_validates_input_without_calling_the_model(similarity, payload):
    assert similarity.client.post('/api/library/media-search', json=payload).status_code == 400
    assert similarity.wire.calls == []


def test_offline_search_keeps_saved_similarity(similarity):
    similarity.run_cli('--yes')
    similarity.wire.status = 503
    assert similarity.client.post('/api/library/media-search', json={'query': 'red'}).status_code == 503
    assert len(similarity.client.get('/api/recommend/similar?uri=a.jpg').json['data']['items']) == 2


def test_embeddinggemma_query_uses_search_prompt(similarity):
    EmbeddingClient({'base_url': 'http://localhost/v1', 'model': 'embeddinggemma-2', 'api_key': None}).embed_text('红色')
    call = similarity.wire.calls[0]
    assert call['json']['input'] == ['task: search result | query: 红色']
    assert 'Authorization' not in call['headers']


def test_api_key_is_never_shown_or_echoed(similarity):
    secret = 'sensitive-key-value'
    client = similarity.open_app({'base_url': 'https://embedding.example/v1',
                                 'model_name': 'fixture-embedding', 'api_key': secret})
    assert secret not in client.get('/experiments/similarity').get_data(as_text=True)
    similarity.run_cli('--yes')
    similarity.wire.status = 401
    similarity.wire.body = {'error': {'message': f'Invalid key: {secret}'}}
    response = client.post('/api/library/media-search', json={'query': 'red'})
    assert response.status_code == 503 and secret not in response.get_data(as_text=True)


def test_config_prefers_yaml_key_and_rejects_unusable_urls(monkeypatch):
    monkeypatch.setenv('SPOOLY_EMBEDDING_API_KEY', 'env-key')
    assert load_embedding_config({'api_key': 'yaml-key'})['api_key'] == 'yaml-key'
    assert load_embedding_config({})['key_source'] == 'environment'
    for url in ('ftp://example.com', 'https://user:pass@example.com', 'https://example.com/?a=1'):
        with pytest.raises(ValueError, match='base_url'):
            load_embedding_config({'base_url': url})


def test_invalid_config_fails_at_startup(tmp_path):
    with pytest.raises(ValueError, match='base_url'):
        create_app({'TESTING': True, 'MEDIA_ROOT': tmp_path,
                    'EXPERIMENTS': {'similarity': {'enabled': True}},
                    'EMBEDDING_CONFIG': {'base_url': 'ftp://invalid'}})


@pytest.mark.parametrize('experiments,embedding,expected', [
    ({'similarity': {'enabled': False}}, {'enabled': True}, False),
    (None, {'enabled': True}, True),
    (None, {'base_url': 'https://example.com'}, False),
])
def test_startup_switch_accepts_the_legacy_flag(experiments, embedding, expected):
    from spooly.config import similarity_enabled
    assert similarity_enabled(experiments, embedding) is expected


def test_default_core_startup_and_routes_do_not_load_vector_runtime(tmp_path):
    script = """
import sys
from spooly.app import create_app
app = create_app({'TESTING': True, 'MEDIA_ROOT': sys.argv[1]})
client = app.test_client()
for url in ('/', '/flow', '/library', '/radio', '/download'):
    assert client.get(url).status_code == 200, url
for part in ('embedding', 'groups', 'web', 'cli', 'indexing'):
    assert 'spooly.experiments.similarity.' + part not in sys.modules, part
for url in ('/experiments/similarity', '/api/ai/embedding-index/job', '/api/recommend/similar?uri=a.jpg'):
    assert client.get(url).status_code == 404, url
"""
    subprocess.run([sys.executable, '-c', script, str(tmp_path)], check=True, capture_output=True, text=True)


def test_cli_dry_run_does_not_call_the_model(similarity, capsys):
    similarity.run_cli('--dry-run', '--limit', '1')
    output = capsys.readouterr().out
    assert 'pending: 3' in output and 'selected this run: 1' in output
    assert similarity.wire.calls == []


def test_cli_and_web_publish_the_same_groups(similarity):
    similarity.run_cli('--yes')
    cli_groups = similarity.client.get('/api/library/similar-groups').json['data']['items']
    assert similarity.client.post('/api/ai/embedding-index/run').status_code == 202
    wait_for_job(similarity.client)
    assert similarity.client.get('/api/library/similar-groups').json['data']['items'] == cli_groups


def test_cli_refuses_when_experiment_is_disabled(similarity, monkeypatch):
    monkeypatch.setattr('spooly.run.load_config', lambda: {'experiments': {'similarity': {'enabled': False}}})
    with pytest.raises(SystemExit) as error:
        similarity.run_cli('--yes')
    assert error.value.code == 2 and similarity.wire.calls == []


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg and ffprobe required')
def test_videos_prepare_distinct_frames_without_changing_the_cover(similarity, monkeypatch):
    from spooly.services.thumbnail import ThumbnailService
    make_video(similarity.media / 'clip.mp4', ['red', 'green', 'blue'])
    thumbnails = ThumbnailService(similarity.media)
    cover = thumbnails.generate_thumbnail('clip.mp4', timestamp=0)
    before = cover.read_bytes()
    assert similarity.client.get('/experiments/similarity').status_code == 200
    assert similarity.store.count('video') == 0
    monkeypatch.setattr('spooly.experiments.similarity.indexing.shutil.which', lambda name: name)
    similarity.run_cli('--yes')
    assert similarity.store.count('video') == 1
    sent_colors = []
    for call in similarity.wire.calls[3:]:
        encoded = call['json']['input'][0]['content'][0]['image_url']['url'].split(',', 1)[1]
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
            sent_colors.append(max(range(3), key=lambda channel: image.getpixel((32, 32))[channel]))
    assert sent_colors == [0, 1, 2]
    assert cover.read_bytes() == before
    with similarity.store.database.connect() as conn:
        row = conn.execute('SELECT video_frames FROM media_vectors WHERE media_type = ?', ('video',)).fetchone()
        assert len(row['video_frames']) == 3 * DIMENSIONS * 4
    similarity.wire.calls.clear()
    similarity.run_cli('--yes')
    assert similarity.wire.calls == []
    result = similarity.client.post('/api/library/media-search', json={'query': 'red', 'media_type': 'video'})
    assert [item['name'] for item in result.json['data']['items']] == ['@default/clip.mp4']


def make_video(path, colors, *, duration=1):
    command = ['ffmpeg', '-y', '-v', 'error']
    for color in colors:
        command.extend(['-f', 'lavfi', '-i', f'color=c={color}:s=64x64:r=10:d={duration}'])
    inputs = ''.join(f'[{index}:v]' for index in range(len(colors)))
    command.extend(['-filter_complex', f'{inputs}concat=n={len(colors)}:v=1:a=0[out]',
                    '-map', '[out]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)])
    subprocess.run(command, check=True, capture_output=True, timeout=15)


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg and ffprobe required')
def test_short_video_prepares_one_frame(similarity, monkeypatch):
    make_video(similarity.media / 'short.mp4', ['red'], duration=0.2)
    monkeypatch.setattr('spooly.experiments.similarity.indexing.shutil.which', lambda name: name)
    similarity.run_cli('--yes')
    assert len(similarity.wire.calls) == 4
    with similarity.store.database.connect() as conn:
        row = conn.execute('SELECT video_frames FROM media_vectors WHERE media_type = ?', ('video',)).fetchone()
        assert len(row['video_frames']) == DIMENSIONS * 4


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg and ffprobe required')
def test_video_keeps_readable_frames_when_one_cannot_be_extracted(similarity, monkeypatch):
    from spooly.services.thumbnail import ThumbnailService
    make_video(similarity.media / 'clip.mp4', ['red', 'green', 'blue'])
    generate = ThumbnailService._generate

    def flaky(self, source, output, timestamp, *, auto_timestamp):
        return output.name != 'frame-1.jpg' and generate(self, source, output, timestamp,
                                                         auto_timestamp=auto_timestamp)

    monkeypatch.setattr(ThumbnailService, '_generate', flaky)
    monkeypatch.setattr('spooly.experiments.similarity.indexing.shutil.which', lambda name: name)
    similarity.run_cli('--yes')
    with similarity.store.database.connect() as conn:
        row = conn.execute('SELECT video_frames FROM media_vectors WHERE media_type = ?', ('video',)).fetchone()
        assert len(row['video_frames']) == 2 * DIMENSIONS * 4
    similarity.wire.calls.clear()
    similarity.run_cli('--yes')
    assert similarity.wire.calls == []


def test_video_similarity_uses_all_frames_and_only_existing_same_model_videos(similarity):
    samples = {'query.mp4': [unit(0), unit(1), unit(2)],
               'related.mp4': [unit(2), unit(0), unit(1)],
               'one-shot.mp4': [unit(0), unit(3), unit(4)],
               'deleted.mp4': [unit(0), unit(1), unit(2)]}
    for name, frames in samples.items():
        (similarity.media / name).write_bytes(b'video')
        similarity.store.upsert(uri=f'@default/{name}', media_type='video', mtime=0, size_bytes=5,
                                vector=mean_vector(frames), frames=frames)
    (similarity.media / 'deleted.mp4').unlink()
    (similarity.media / 'other-model.mp4').write_bytes(b'video')
    VectorStore(similarity.store.database, 'other-model').upsert(
        uri='@default/other-model.mp4', media_type='video', mtime=0, size_bytes=5,
        vector=mean_vector(samples['query.mp4']), frames=samples['query.mp4'])
    similarity.run_cli('--yes')  # Add image vectors; they must not enter video results.
    similarity.wire.calls.clear()
    result = similarity.client.get('/api/recommend/similar?uri=query.mp4')
    items = result.json['data']['items']
    assert [item['name'] for item in items] == ['@default/related.mp4', '@default/one-shot.mp4']
    assert items[0]['score'] == pytest.approx(1)
    assert items[1]['score'] == pytest.approx(1 / 3)
    assert items[0]['title'] == 'related'
    assert all(item['type'] == 'video' and item['detail_url'].startswith('/detail/') for item in items)
    assert similarity.client.get('/api/recommend/similar?uri=query.mp4&limit=1').json['data']['items'] == items[:1]
    assert similarity.client.get('/detail/query.mp4').status_code == 200
    assert similarity.client.get('/api/recommend/similar?uri=deleted.mp4').status_code == 404
    assert similarity.wire.calls == []


@pytest.fixture
def pending_video(similarity, monkeypatch):
    from spooly.services.thumbnail import ThumbnailService
    similarity.run_cli('--yes')
    video = similarity.media / 'clip.mp4'
    video.write_bytes(b'video')
    stat = video.stat()
    similarity.store.upsert(uri='@default/clip.mp4', media_type='video', mtime=stat.st_mtime,
                            size_bytes=stat.st_size, vector=unit(7))
    paths = []

    def sample(self, uri, directory):
        frames = [directory / f'{index}.jpg' for index in range(3)]
        for frame in frames:
            Image.new('RGB', (32, 32), 'red').save(frame)
        paths.extend(frames)
        return frames

    monkeypatch.setattr('spooly.experiments.similarity.indexing.shutil.which', lambda name: name)
    monkeypatch.setattr(ThumbnailService, 'sample_video_frames', sample)
    similarity.wire.calls.clear()
    return paths


def test_pause_between_video_requests_keeps_the_old_vector_and_cleans_frames(similarity, pending_video, monkeypatch):
    from spooly.experiments.similarity import embedding
    original_post = embedding.requests.post
    entered, release = threading.Event(), threading.Event()

    def slow_post(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original_post(*args, **kwargs)

    monkeypatch.setattr(embedding.requests, 'post', slow_post)
    similarity.client.post('/api/ai/embedding-index/run')
    assert entered.wait(3)
    similarity.client.post('/api/ai/embedding-index/pause')
    release.set()
    job = wait_for_job(similarity.client, ('paused',))
    assert job['processed'] == 0 and job['failed'] == 0
    assert list(similarity.store.vectors('video')[0]['vector']) == unit(7)
    assert not similarity.store.states()['@default/clip.mp4'][2]
    assert len(similarity.wire.calls) == 1
    assert all(not path.exists() for path in pending_video)
    similarity.client.post('/api/ai/embedding-index/run')
    assert wait_for_job(similarity.client)['processed'] == 1
    assert len(similarity.wire.calls) == 4
    assert similarity.store.states()['@default/clip.mp4'][2]
    assert all(not path.exists() for path in pending_video)


def test_failed_video_request_does_not_publish_partial_vectors(similarity, pending_video, monkeypatch):
    from spooly.experiments.similarity import embedding
    original_post = embedding.requests.post
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            similarity.wire.status = 503
        return original_post(*args, **kwargs)

    monkeypatch.setattr(embedding.requests, 'post', fail_second)
    similarity.client.post('/api/ai/embedding-index/run')
    job = wait_for_job(similarity.client)
    assert (job['processed'], job['failed']) == (1, 1)
    assert list(similarity.store.vectors('video')[0]['vector']) == unit(7)
    assert not similarity.store.states()['@default/clip.mp4'][2]
    assert all(not path.exists() for path in pending_video)


def test_thumbnail_video_migration_reuses_photos_and_schedules_only_video(similarity):
    from spooly.experiments.similarity.indexing import MediaIndexer
    from spooly.services.library import LibraryService
    from spooly.services.thumbnail import ThumbnailService
    video = similarity.media / 'legacy.mp4'
    video.write_bytes(b'video')
    database = AppDatabase(similarity.media.parent / 'v0847.sqlite3')
    with database.connect() as conn:
        conn.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)')
        for migration in MIGRATIONS:
            if migration.version < 12:
                migration.up(conn)
                conn.execute('INSERT INTO schema_migrations VALUES (?, ?, ?)', (migration.version, migration.name, 'old'))
        for path in similarity.media.iterdir():
            stat = path.stat()
            conn.execute('INSERT INTO media_vectors VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                         (f'@default/{path.name}', 'video' if path == video else 'image', 'fixture-embedding',
                          stat.st_mtime, stat.st_size, array('f', unit(0)).tobytes(), 1, 'old'))
    database.migrate()
    database.migrate()
    library = LibraryService(similarity.media)
    indexer = MediaIndexer(library, ThumbnailService(similarity.media), database, {'model': 'fixture-embedding'})
    # Explicit video record works even on installations without ffmpeg.
    stat = video.stat()
    records = [{'uri': '@default/legacy.mp4', 'mtime': stat.st_mtime, 'size_bytes': stat.st_size}]
    assert indexer.pending(records) == records
    assert all(state[2] for uri, state in indexer.store.states().items() if uri.endswith('.jpg'))
    assert indexer.store.count() == 4


def test_groups_are_bounded_and_varied():
    rows = [{'uri': f'{group}-{image}', 'vector': unit(group), 'norm': 1.0}
            for group in range(40) for image in range(3)]
    groups = choose_groups(rows)
    assert len(groups) == 24 and all(len(group) == 3 for group in groups)
    # Near-identical scenes in different windows collapse into one card.
    assert len(choose_groups([{**row, 'vector': unit(0)} for row in rows])) == 1


def test_flow_reuses_gallery_slot_for_related_photos():
    def select(*, file_type, limit, seed):
        return [f'video-{index}.mp4' for index in range(limit)] if file_type == 'video' else []

    recommendation = SimpleNamespace(get_weighted_selection=select, get_forgotten_selection=select,
                                     reasons_for=lambda _names: {})
    groups = lambda **_kwargs: {'items': [{
        'group_key': '0', 'items': [{'uri': f'photo-{index}.jpg'} for index in range(3)],
    }]}
    options = dict(size=8, seed='fixed', recommend_service=recommendation,
                   media_index=SimpleNamespace(records=lambda: []), download_source_store=None,
                   related_photo_groups=groups)
    assert len([item for item in build_mix_feed_page(page=2, **options)['items']
                if item['type'] == 'image_group']) == 1
    assert build_mix_feed_page(page=1, **options)['items'][0]['type'] != 'image_group'
    assert all(item['type'] != 'image_group' for item in
               build_mix_feed_page(page=2, mode='forgotten', **options)['items'])


def test_released_vectors_migrate_without_re_encoding(tmp_path):
    db = AppDatabase(tmp_path / 'released.sqlite3')
    blob = array('f', unit(0)).tobytes()
    with db.connect() as conn:
        conn.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)')
        for migration in MIGRATIONS:
            if migration.version < 11:
                migration.up(conn)
                conn.execute('INSERT INTO schema_migrations VALUES (?, ?, ?)', (migration.version, migration.name, 'old'))
        conn.execute('INSERT INTO image_vectors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     ('@default/a.jpg', 'default', 'a.jpg', 'legacy-model', 768, 512, 82, 1, 100, blob, 1, 'old'))
        conn.execute('INSERT INTO image_vectors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     ('@default/b.jpg', 'default', 'b.jpg', 'legacy-model', 2, 512, 82, 1, 100, b'xx', 1, 'old'))
    db.migrate()
    db.migrate()
    rows = VectorStore(db, 'legacy-model').vectors()
    assert [(row['uri'], row['media_type'], row['vector'].tobytes()) for row in rows] == [
        ('@default/a.jpg', 'image', blob)]


def test_schema_migration_rolls_back_ddl_on_failure(tmp_path):
    from spooly.services.database import Migration
    db = AppDatabase(tmp_path / 'rollback.sqlite3')
    db.migrate()

    def fail(conn):
        conn.execute('CREATE TABLE unfinished_migration(value TEXT)')
        raise RuntimeError('migration interrupted')

    with pytest.raises(RuntimeError, match='interrupted'):
        db._apply(Migration(99, 'fixture', fail))
    with db.connect() as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'unfinished_migration'").fetchone()
        assert not conn.execute('SELECT 1 FROM schema_migrations WHERE version = 99').fetchone()
