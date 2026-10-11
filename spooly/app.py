import os
import datetime
import socket
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from flask import Flask, request, send_file, url_for

# Service Imports
from spooly.services.library import LibraryService, build_media_sources
from spooly.services.favorites import FavoriteService
from spooly.services.recommendation import RecommendService
from spooly.services.thumbnail import ThumbnailService
from spooly.services.metadata import ImageMetadataStore
from spooly.services.captions import CaptionSettings
from spooly.web.captions import register_caption_routes
from spooly.web.downloads import register_download_routes
from spooly.web.library import register_library_routes
from spooly.services.database import AppDatabase, MediaActivityStore
from spooly.services.library_index import LibraryIndexer, MediaIndexStore, MediaProbeWorker
from spooly.services.trash import TrashService
from spooly.services.downloader import (
    DownloadConfigStore,
    DownloadHistoryStore,
    DownloadManager,
)
from spooly.services.download_sources import DownloadSourceStore
from spooly.services.collections import CollectionStore
from spooly.services.radio import RadioProfileStore, RadioService
from spooly.services.radio_energy import RadioEnergyService
from spooly.services.auth import AuthStore
from spooly.auth import configure_auth
from spooly.paths import (
    get_metadata_path,
    get_favorites_path,
    get_prompt_config_path,
    get_llm_config_path,
    get_database_path,
    get_download_config_path,
    get_download_jobs_path,
    get_download_sources_path,
    get_collections_path,
    get_radio_profile_path,
    get_auth_path,
)
from spooly.web.flow import register_flow_routes
from spooly.web.radio import register_radio_routes
from spooly.web.media import register_media_routes
from spooly.web.settings import register_settings_routes
from spooly.config import similarity_enabled


def get_app_version():
    """Return the app version, reading pyproject.toml during development."""
    # Prefer pyproject.toml when running from a development checkout.
    pyproject_path = Path(__file__).parent.parent / 'pyproject.toml'
    if pyproject_path.exists():
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                tomllib = None

        if tomllib:
            try:
                with open(pyproject_path, 'rb') as f:
                    data = tomllib.load(f)
                    return data.get('tool', {}).get('poetry', {}).get('version', '1.0.0')
            except Exception:
                pass

    # Installed builds read their package metadata.
    try:
        return version("spooly")
    except PackageNotFoundError:
        return '1.0.0'


app_version = get_app_version()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY = None,
        MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', '.')),
        MEDIA_SOURCES = None,
        DOWNLOAD_SOURCE = 'default',
        VISION_CONFIG = None,
        EMBEDDING_CONFIG = None,
        EXPERIMENTS = None,
        AUTH_ENABLED = None,
        AUTH_COOKIE_SECURE = False,
        INSTANCE_NAME = None,
    )
    app.config.from_pyfile('config.py', silent=True)
    app.config.from_prefixed_env()
    if test_config is not None:
        app.config.update(test_config)

    similarity_active = similarity_enabled(app.config.get('EXPERIMENTS'), app.config.get('EMBEDDING_CONFIG'))

    instance_name = str(
        app.config.get('INSTANCE_NAME')
        or os.environ.get('SPOOLY_NAME')
        or socket.gethostname()
        or 'Local'
    ).strip()[:48] or 'Local'
    app.config['INSTANCE_NAME'] = instance_name
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    configured_auth = app.config.get('AUTH_ENABLED')
    auth_enabled = not bool(app.config.get('TESTING')) if configured_auth is None else bool(configured_auth)
    auth_store = AuthStore(app.config.get('AUTH_PATH') or get_auth_path())
    bootstrap = None
    if auth_enabled:
        bootstrap = auth_store.ensure(os.environ.get('SPOOLY_AUTH_PASSWORD'))
    configure_auth(
        app,
        auth_store,
        enabled=auth_enabled,
    )
    app.extensions['auth_bootstrap'] = bootstrap

    @app.template_global()
    def static_asset(filename: str) -> str:
        return url_for('static', filename=filename, v=app_version)

    @app.context_processor
    def app_identity_context():
        return {
            'app_version': app_version,
            'instance_name': instance_name,
            'similarity_enabled': similarity_active,
        }

    @app.after_request
    def apply_cache_policy(response):
        endpoint = request.endpoint or ''
        if endpoint == 'static':
            if request.args.get('v') == app_version:
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            else:
                response.headers['Cache-Control'] = 'public, max-age=0, must-revalidate'
        elif endpoint == 'retired_service_worker':
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Service-Worker-Allowed'] = '/'
        elif request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'private, no-store'
        elif request.path.startswith('/media'):
            response.headers['Cache-Control'] = 'private, no-cache'
        elif request.path == '/thumb':
            response.headers['Cache-Control'] = 'private, max-age=3600, must-revalidate'
        elif response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'private, no-cache'
        return response

    # Initialize Services
    media_sources = build_media_sources(app.config['MEDIA_ROOT'], app.config.get('MEDIA_SOURCES'))
    library_service = LibraryService(app.config['MEDIA_ROOT'], media_sources=media_sources)
    default_media_root = library_service.media_root
    media_root_str = str(default_media_root)
    app.config['MEDIA_ROOT'] = default_media_root
    favorite_service = FavoriteService(media_root_str, db_path=get_favorites_path(), library_service=library_service)
    thumbnail_service = ThumbnailService(Path(media_root_str), library_service=library_service)
    metadata_store = ImageMetadataStore(get_metadata_path())
    caption_settings = CaptionSettings(app.config.get('VISION_CONFIG'), get_prompt_config_path(), get_llm_config_path())
    register_caption_routes(app, library_service, metadata_store, caption_settings)
    app_database = app.config.get('APP_DATABASE') or AppDatabase(get_database_path())
    app_database.migrate()
    media_index = MediaIndexStore(app_database)
    library_indexer = LibraryIndexer(library_service, media_index)
    index_sync_result = library_indexer.sync()
    app.extensions["media_index_sync"] = index_sync_result
    media_probe = MediaProbeWorker(library_service, media_index)
    library_indexer.on_change = media_probe.wake
    app.extensions["media_probe"] = media_probe
    if not app.config.get('TESTING'):
        media_probe.start()
    if index_sync_result["unavailable_sources"]:
        app.logger.warning(
            "Media source unavailable; preserving its existing index: %s",
            ", ".join(index_sync_result["unavailable_sources"]),
        )
    activity_store = MediaActivityStore(app_database)
    recommend_service = RecommendService(
        library_service,
        favorite_service,
        activity_store,
        media_index=media_index,
    )
    radio_profile_store = RadioProfileStore(get_radio_profile_path())
    radio_service = RadioService(
        library_service,
        favorite_service,
        media_index,
        radio_profile_store,
        activity_store=activity_store,
    )
    if similarity_active:
        from spooly.experiments.similarity.web import register_similarity_routes
        register_similarity_routes(app, library_service, app_database)
    download_config_store = DownloadConfigStore(get_download_config_path())
    download_history_store = DownloadHistoryStore(get_download_jobs_path())
    download_source_store = DownloadSourceStore(get_download_sources_path())
    collection_store = CollectionStore(get_collections_path())
    download_source_id = str(app.config.get('DOWNLOAD_SOURCE') or library_service.default_source_id).strip() or library_service.default_source_id
    download_source = library_service.sources_by_id.get(download_source_id) or library_service.sources_by_id[library_service.default_source_id]
    download_manager = DownloadManager(
        download_source.path,
        download_config_store,
        download_history_store,
        source_store=download_source_store,
        output_source_id=download_source.id,
        on_outputs=library_indexer.register_uris,
    )

    app.extensions['download_manager'] = download_manager
    register_download_routes(app, download_manager, library_service)
    register_library_routes(
        app, library_service=library_service, media_index=media_index,
        library_indexer=library_indexer, favorite_service=favorite_service,
        collection_store=collection_store, activity_store=activity_store,
        similarity_active=similarity_active,
    )

    register_flow_routes(
        app, media_index=media_index, recommend_service=recommend_service,
        download_source_store=download_source_store,
        activity_store=activity_store,
    )

    register_radio_routes(app, library_service, radio_service, thumbnail_service, RadioEnergyService(library_service))
    register_media_routes(
        app, library_service, media_index, thumbnail_service, download_manager,
        TrashService(library_service), library_indexer, activity_store,
    )
    register_settings_routes(app, media_index, favorite_service, thumbnail_service, app_version)

    # --- Template Filters ---
    @app.template_filter('timestamp_to_date')
    def timestamp_to_date(timestamp):
        try:
            return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OSError):
            return 'Unknown time'

    @app.template_filter('filesizeformat')
    def filesizeformat(num_bytes):
        if num_bytes is None: return '0 B'
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if num_bytes < 1024.0:
                return f"{int(num_bytes) if unit == 'B' else f'{num_bytes:.1f}'} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} PB"

    @app.get('/favicon.ico')
    def favicon():
        return send_file(
            Path(app.static_folder) / 'brand' / 'favicon.ico',
            mimetype='image/vnd.microsoft.icon',
            max_age=86400,
        )

    @app.get('/service-worker.js')
    def retired_service_worker():
        return send_file(
            Path(app.static_folder) / 'service_worker.js',
            mimetype='application/javascript',
        )

    return app
