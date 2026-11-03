import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import pytest
import yaml

from spooly.app import create_app
from spooly.config import normalize_media_sources
from spooly.paths import get_database_path
from spooly.services.database import AppDatabase
from spooly.services.library import LibraryService


def write_media(root: Path, names: list[str]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'media')


def library_names(client, **query) -> set[str]:
    response = client.get('/api/library/items', query_string=query)
    assert response.status_code == 200
    return {item['name'] for item in response.json['data']['items']}


@pytest.mark.parametrize('patterns,hidden', [
    ([], set()),
    (['folder.jpg'], {'folder.jpg', 'Album/Folder.JPG'}),
    (['*.PNG'], {'Album/cover.png'}),
    (['album/photo.jpg'], {'Album/photo.jpg'}),
    (['Album/*.jpg'], {'Album/Folder.JPG', 'Album/photo.jpg', 'Album/Extras/extra.jpg'}),
    (['Extras/'], {'Album/Extras/extra.jpg', 'Extras/root.jpg'}),
    (['Archive.jpg/'], {'Archive.jpg/inside.jpg'}),
    (['photo?.[jp][pn]g'], {'photo1.jpg'}),
])
def test_scan_matches_names_paths_and_directory_patterns(tmp_path, patterns, hidden):
    names = [
        'folder.jpg', 'Album/Folder.JPG', 'Album/cover.png', 'Album/photo.jpg',
        'Album/Extras/extra.jpg', 'Extras/root.jpg', 'elsewhere/Album/photo.jpg',
        'Archive.jpg/inside.jpg', 'elsewhere/Archive.jpg', 'photo1.jpg', 'song.mp3',
    ]
    write_media(tmp_path, names)
    library = LibraryService(tmp_path, exclude=patterns)
    found = {path.relative_to(tmp_path).as_posix() for path in library.scan_source(library.sources[0])}
    assert found == set(names) - hidden


def test_excluded_directory_is_not_traversed(tmp_path, monkeypatch):
    write_media(tmp_path, ['private/photo.jpg', 'photo.jpg'])
    original_scandir = os.scandir

    def scandir(path):
        if Path(path) == tmp_path / 'private':
            raise PermissionError('excluded directory must not be opened')
        return original_scandir(path)

    monkeypatch.setattr(os, 'scandir', scandir)
    library = LibraryService(tmp_path, exclude=['private/'])
    assert library.scan_images() == [tmp_path / 'photo.jpg']


@pytest.mark.parametrize('invalid', [
    'folder.jpg', 12, [None], [''], ['  '], ['/absolute/'], [r'C:\Music'],
    ['../photo.jpg'], ['!folder.jpg'],
])
def test_invalid_rules_are_rejected_globally_and_per_source(tmp_path, invalid):
    with pytest.raises(ValueError, match='exclude'):
        LibraryService(tmp_path, exclude=invalid)
    with pytest.raises(ValueError, match=r'media_sources\[music\].exclude'):
        normalize_media_sources({'media_sources': [{'id': 'music', 'path': str(tmp_path), 'exclude': invalid}]})


def test_global_rules_combine_with_rules_for_only_one_source(tmp_path):
    main, music = tmp_path / 'main', tmp_path / 'music'
    for root in (main, music):
        write_media(root, ['folder.jpg', 'photo.jpg', 'cover.png', 'song.mp3'])
    sources = normalize_media_sources({'media_sources': [
        {'id': 'default', 'path': str(main)},
        {'id': 'music', 'path': str(music), 'exclude': ['*.png']},
    ]})
    client = create_app({
        'TESTING': True, 'MEDIA_ROOT': main, 'MEDIA_SOURCES': sources,
        'MEDIA_EXCLUDE': ['folder.jpg'],
    }).test_client()
    assert library_names(client) == {
        '@default/photo.jpg', '@default/cover.png', '@music/photo.jpg',
    }
    assert {item['name'] for item in client.get('/api/radio/items').json['data']['items']} == {
        '@default/song.mp3', '@music/song.mp3',
    }


def test_cli_loads_yaml_rules_and_default_alias_keeps_source_rules(tmp_path, monkeypatch):
    import spooly.run as run

    media = tmp_path / 'music'
    write_media(media, ['folder.jpg', 'cover.png', 'photo.jpg'])
    config_path = Path(os.environ['SPOOLY_INSTANCE']) / 'config.yaml'
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump({
        'exclude': ['folder.jpg'],
        'media_sources': [{'id': 'music', 'path': str(media), 'exclude': ['*.png']}],
    }))
    monkeypatch.delenv('MEDIA_ROOT', raising=False)
    monkeypatch.setattr(sys, 'argv', ['spooly'])
    monkeypatch.setattr(run, 'create_app', lambda config: create_app({**config, 'TESTING': True}))
    served = []

    def serve(app, **kwargs):
        served.append(library_names(app.test_client()))

    monkeypatch.setattr(run, 'serve', serve)
    run.main()
    assert served == [{'@music/photo.jpg'}]


def test_rule_changes_update_index_and_previews_without_losing_user_state(tmp_path):
    media = tmp_path / 'media'
    write_media(media, ['folder.jpg', 'photo.jpg'])
    config = {'TESTING': True, 'MEDIA_ROOT': media}
    client = create_app(config).test_client()
    assert client.post('/api/favorite/folder.jpg').json['favorite'] is True
    activity = client.post('/api/activity', json={
        'uri': '@default/folder.jpg', 'media_type': 'image', 'event': 'complete',
    })
    assert activity.json['data']['accepted'] == 1
    collection = client.post('/api/collections', json={'name': 'Album'}).json['data']['item']
    collection_url = f"/api/collections/{collection['id']}"
    client.post(f'{collection_url}/items', json={'uris': ['photo.jpg', 'folder.jpg']})

    app = create_app({**config, 'MEDIA_EXCLUDE': ['folder.jpg']})
    client = app.test_client()
    assert app.extensions['media_index_sync']['deleted'] == 1
    assert library_names(client) == {'@default/photo.jpg'}
    assert {item['name'] for item in client.get('/api/feed/mix?seed=excluded').json['items']} == {
        '@default/photo.jpg',
    }
    assert library_names(client, scope='favorite') == set()
    assert library_names(client, scope='collection', collection_id=collection['id']) == {'@default/photo.jpg'}
    summary = client.get(collection_url).json['data']['item']
    assert summary['cover_uri'] == '@default/photo.jpg'
    assert [item['uri'] for item in summary['preview_items']] == ['@default/photo.jpg']
    assert client.get('/api/favorite/folder.jpg').json['favorite'] is True
    with AppDatabase(get_database_path()).connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM media_events WHERE uri = '@default/folder.jpg'").fetchone()[0] == 1
    assert (media / 'folder.jpg').read_bytes() == b'media'
    assert client.get('/media/@default/folder.jpg').status_code == 200

    client = create_app(config).test_client()
    assert library_names(client, scope='favorite') == {'@default/folder.jpg'}
    assert library_names(client, scope='collection', collection_id=collection['id']) == {
        '@default/folder.jpg', '@default/photo.jpg',
    }
    assert client.get(collection_url).json['data']['item']['cover_uri'] == '@default/folder.jpg'


def test_rule_changes_preserve_offline_source_index_until_successful_sync(tmp_path):
    main, music = tmp_path / 'main', tmp_path / 'music'
    main.mkdir()
    write_media(music, ['folder.jpg', 'photo.jpg'])
    config = {
        'TESTING': True, 'MEDIA_ROOT': main,
        'MEDIA_SOURCES': [{'id': 'music', 'path': str(music)}],
    }
    create_app(config)
    offline = tmp_path / 'offline'
    music.rename(offline)
    config['MEDIA_EXCLUDE'] = ['folder.jpg']
    app = create_app(config)
    client = app.test_client()
    assert app.extensions['media_index_sync']['unavailable_sources'] == ['music']
    assert library_names(client) == {'@music/folder.jpg', '@music/photo.jpg'}

    offline.rename(music)
    assert client.post('/api/library/sync').json['data']['deleted'] == 1
    assert library_names(client) == {'@music/photo.jpg'}


@pytest.mark.parametrize('outputs', [['folder.jpg'], ['folder.jpg', 'photo.jpg']])
def test_downloads_succeed_while_excluded_outputs_stay_out_of_index(tmp_path, monkeypatch, outputs):
    media = tmp_path / 'media'
    media.mkdir()

    def execute(manager, job_id):
        write_media(manager.media_root, outputs)
        return 0, '', outputs

    monkeypatch.setattr('spooly.services.downloader.DownloadManager._execute_download', execute)
    app = create_app({'TESTING': True, 'MEDIA_ROOT': media, 'MEDIA_EXCLUDE': ['folder.jpg']})
    client = app.test_client()
    manager = app.extensions['download_manager']
    manager.start()
    try:
        job_id = client.post('/api/download/jobs', json={'url': 'https://example.com/album'}).json['data']['job']['id']
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = client.get(f'/api/download/jobs/{job_id}').json['data']['job']
            if job['status'] in {'success', 'failed', 'canceled'}:
                break
            time.sleep(0.01)
        assert job['status'] == 'success', job
        assert job['file_count'] == len(outputs)
        assert library_names(client) == {f'@default/{name}' for name in outputs if name != 'folder.jpg'}
        assert (media / 'folder.jpg').read_bytes() == b'media'
    finally:
        manager.close()


def test_restoring_excluded_media_keeps_file_without_registering_it(tmp_path):
    media = tmp_path / 'media'
    write_media(media, ['Album/folder.jpg'])
    config = {'TESTING': True, 'MEDIA_ROOT': media}
    client = create_app(config).test_client()
    deleted = client.post('/delete/' + quote('@default/Album/folder.jpg'), headers={'Accept': 'application/json'})
    entry_id = deleted.json['id']

    client = create_app({**config, 'MEDIA_EXCLUDE': ['Album/']}).test_client()
    assert client.post(f'/api/trash/{entry_id}/restore').status_code == 200
    assert client.get('/api/trash').json['items'] == []
    assert library_names(client) == set()
    assert (media / 'Album/folder.jpg').read_bytes() == b'media'
    assert library_names(create_app(config).test_client()) == {'@default/Album/folder.jpg'}
