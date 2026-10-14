"""Choose a few related-photo groups locally, without an all-pairs scan of the library."""

from spooly.services.database import AppDatabase
from .embedding import VectorStore, cosine


THRESHOLD = 0.84
MIN_GROUP_SIZE = 3
MAX_GROUP_SIZE = 8
MAX_GROUPS = 24
SCAN_LIMIT = 5000
WINDOW_SIZE = 64
DUPLICATE_SEED_SCORE = 0.96


def choose_groups(rows: list[dict], *, should_stop=lambda: False) -> list[list[str]] | None:
    """Group neighbours inside windows of recent photos, then keep a varied selection."""
    candidates = []
    for start in range(0, len(rows), WINDOW_SIZE):
        if should_stop():
            return None
        candidates.extend(_greedy_groups(rows[start:start + WINDOW_SIZE]))
    candidates.sort(key=lambda group: (-len(group['members']), -group['score'], group['members'][0]['uri']))
    selected = []
    for group in candidates:
        seed = group['members'][0]
        # Consecutive windows can produce many cards of the same scene.
        if any(cosine(seed['vector'], seed['norm'], other[0]['vector'], other[0]['norm']) >= DUPLICATE_SEED_SCORE
               for other in selected):
            continue
        selected.append(group['members'])
        if len(selected) >= MAX_GROUPS:
            break
    return [[row['uri'] for row in members] for members in selected]


def _greedy_groups(rows: list[dict]) -> list[dict]:
    used = set()
    groups = []
    for seed in rows:
        if seed['uri'] in used:
            continue
        scored = sorted(((cosine(seed['vector'], seed['norm'], row['vector'], row['norm']), row['uri'], row)
                         for row in rows if row['uri'] != seed['uri'] and row['uri'] not in used),
                        key=lambda item: (-item[0], item[1]))
        neighbours = [(score, row) for score, _uri, row in scored if score >= THRESHOLD][:MAX_GROUP_SIZE - 1]
        if len(neighbours) + 1 < MIN_GROUP_SIZE:
            continue
        members = [seed, *(row for _score, row in neighbours)]
        used.update(row['uri'] for row in members)
        groups.append({'members': members, 'score': sum(score for score, _row in neighbours) / len(neighbours)})
    return groups


def rebuild_photo_groups(library, database: AppDatabase, model: str, *, should_stop=lambda: False) -> int | None:
    """Replace saved groups in one transaction; return None when stopped early."""
    rows = [row for row in VectorStore(database, model).vectors('image', limit=SCAN_LIMIT)
            if _exists(library, row['uri'])]
    groups = choose_groups(rows, should_stop=should_stop)
    if groups is None:
        return None
    with database.connect() as conn:
        conn.execute('DELETE FROM photo_groups')
        conn.executemany('INSERT INTO photo_groups(position, rank, uri) VALUES (?, ?, ?)',
                         [(position, rank, uri) for position, uris in enumerate(groups)
                          for rank, uri in enumerate(uris)])
    return len(groups)


def read_photo_groups(library, database: AppDatabase, *, offset: int = 0, limit: int = 24) -> dict:
    """Return saved groups whose files are still present; groups that shrink below three are hidden."""
    with database.connect() as conn:
        total = conn.execute('SELECT COUNT(DISTINCT position) FROM photo_groups').fetchone()[0]
        rows = conn.execute('SELECT position, uri FROM photo_groups WHERE position >= ? AND position < ? '
                            'ORDER BY position, rank', (offset, offset + limit)).fetchall()
    members: dict[int, list[str]] = {}
    for row in rows:
        uri = library.find_existing_uri(row['uri'])
        if _exists(library, uri):
            members.setdefault(row['position'], []).append(uri)
    groups = [{'group_key': str(position), 'count': len(uris), 'items': [{'uri': uri} for uri in uris]}
              for position, uris in members.items() if len(uris) >= MIN_GROUP_SIZE]
    return {'items': groups, 'total': total, 'offset': offset, 'limit': limit,
            'next_offset': offset + limit, 'has_more': offset + limit < total}


def _exists(library, uri: str) -> bool:
    path = library.resolve_path(uri)
    return bool(path and path.is_file())
