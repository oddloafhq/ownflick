import sys

import pytest

from spooly.app import app_version, create_app
from spooly.run import load_config, main


def test_browser_cache_policy_and_media_range(tmp_path):
    (tmp_path / 'clip.mp4').write_bytes(b'0123456789')
    client = create_app({'TESTING': True, 'MEDIA_ROOT': tmp_path}).test_client()
    versioned = client.get('/static/csrf_fetch.js', query_string={'v': app_version})
    plain = client.get('/static/csrf_fetch.js')
    media = client.get('/media/clip.mp4', headers={'Range': 'bytes=2-5'})
    assert versioned.headers['Cache-Control'] == 'public, max-age=31536000, immutable'
    assert plain.headers['Cache-Control'] == 'public, max-age=0, must-revalidate'
    assert client.get('/api/library/stats').headers['Cache-Control'] == 'private, no-store'
    assert media.status_code == 206 and media.data == b'2345'
    assert media.headers['Cache-Control'] == 'private, no-cache'
    assert media.headers['Content-Range'] == 'bytes 2-5/10'
    assert client.get('/install').status_code == 404
    assert client.get('/app.webmanifest').status_code == 404
    assert client.get('/service-worker.js').status_code == 404
    assert client.get('/api/v1/pair').status_code == 404


@pytest.mark.parametrize('key,value', [
    ('https', True), ('tls_cert', 'cert.pem'), ('tls_key', 'key.pem'), ('hostnames', ['studio.local']),
])
def test_old_tls_config_does_not_silently_start_http(monkeypatch, capsys, key, value):
    monkeypatch.setattr('spooly.run.load_config', lambda: {key: value})
    monkeypatch.setattr(sys, 'argv', ['spooly'])
    with pytest.raises(SystemExit) as stopped:
        main()
    assert stopped.value.code == 2
    assert 'Built-in HTTPS has been removed' in capsys.readouterr().err


def test_instance_config_takes_priority(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    instance = tmp_path / 'instance'
    (home / '.config' / 'spooly').mkdir(parents=True)
    (home / '.config' / 'spooly' / 'config.yaml').write_text('name: Global\n')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('SPOOLY_INSTANCE', str(instance))
    assert load_config() == {'name': 'Global'}

    instance.mkdir()
    (instance / 'config.yaml').write_text('name: Container\nport: 9000\n')
    assert load_config() == {'name': 'Container', 'port': 9000}
