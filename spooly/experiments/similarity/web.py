from types import SimpleNamespace

from flask import render_template, request

from spooly.web import read_int_arg
from spooly.web.media_payloads import build_feed_media_item
from .config import load_embedding_config
from .embedding import EmbeddingClient
from .groups import read_photo_groups
from .indexing import IndexJob, MediaIndexer


SEARCH_RESULT_LIMIT = 48


def register_similarity_routes(app, library_service, thumbnail_service, app_database):
    """Register the experiment and return the hooks other pages use."""
    config = load_embedding_config(app.config.get('EMBEDDING_CONFIG'))
    indexer = MediaIndexer(library_service, thumbnail_service, app_database, config)
    job = IndexJob(indexer)

    def photo_groups(*, offset: int = 0, limit: int = 24) -> dict:
        return read_photo_groups(library_service, app_database, offset=offset, limit=limit)

    def groups_page(*, offset: int = 0, limit: int = 24) -> dict:
        payload = photo_groups(offset=offset, limit=limit)
        return {**payload, 'items': [
            {**group, 'items': [build_feed_media_item(item['uri'], 'image') for item in group['items']]}
            for group in payload['items']
        ]}

    def existing_items(candidates, limit: int) -> list[dict]:
        items = []
        for candidate in candidates:
            uri = library_service.find_existing_uri(candidate['uri'])
            path = library_service.resolve_path(uri)
            if not path or not path.is_file():
                continue
            items.append({**build_feed_media_item(uri, candidate['media_type']), 'score': candidate['score']})
            if len(items) >= limit:
                break
        return items

    @app.route('/experiments/similarity')
    def similarity_view():
        return render_template(
            'experiments/similarity.html', menu='library',
            page=groups_page(offset=read_int_arg('offset', 0, minimum=0)),
            status=indexer.status(), job=job.status(),
            connection={key: config[key] for key in ('base_url', 'model', 'key_source')},
        )

    @app.route('/api/library/similar-groups')
    def api_library_similar_groups():
        return {'success': True, 'data': groups_page(offset=read_int_arg('offset', 0, minimum=0),
                                                     limit=read_int_arg('limit', 24, minimum=1, maximum=48))}

    @app.route('/api/recommend/similar')
    def api_similar_images():
        uri = library_service.find_existing_uri(request.args.get('uri') or '')
        if not uri or not library_service.resolve_path(uri):
            return {'success': False, 'error': 'File not found'}, 404
        candidates = indexer.store.similar(uri)
        items = existing_items(candidates, read_int_arg('limit', 12, minimum=1, maximum=48))
        return {'success': True, 'data': {'indexed': bool(candidates), 'items': items}}

    @app.route('/api/library/media-search', methods=['POST'])
    def api_media_search():
        payload = request.get_json(silent=True) or {}
        query = payload.get('query') if isinstance(payload, dict) else None
        media_type = payload.get('media_type', 'all') if isinstance(payload, dict) else 'all'
        if media_type not in ('all', 'image', 'video'):
            return {'success': False, 'error': 'Invalid media type.'}, 400
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            return {'success': False, 'error': 'Enter a description of 1–200 characters.'}, 400
        media_type = None if media_type == 'all' else media_type
        if not indexer.store.count(media_type):
            return {'success': False, 'error': f'No media is prepared for {config["model"]} yet. '
                    'Prepare media in Similar Images first.'}, 409
        try:
            vector = EmbeddingClient(config).embed_text(query.strip())
        except RuntimeError as exc:
            return {'success': False, 'error': f'The embedding service could not encode this search: {exc}'}, 503
        return {'success': True, 'data': {
            'items': existing_items(indexer.store.rank(vector, media_type), SEARCH_RESULT_LIMIT)}}

    @app.route('/api/ai/embedding-index/run', methods=['POST'])
    def api_embedding_index_run():
        try:
            return {'success': True, 'data': job.start()}, 202
        except RuntimeError as exc:
            return {'success': False, 'error': str(exc)}, 409

    @app.route('/api/ai/embedding-index/job')
    def api_embedding_index_job():
        return {'success': True, 'data': job.status()}

    @app.route('/api/ai/embedding-index/pause', methods=['POST'])
    def api_embedding_index_pause():
        return {'success': True, 'data': job.pause()}

    return SimpleNamespace(photo_groups=photo_groups, has_vectors=lambda: indexer.store.count() > 0)
