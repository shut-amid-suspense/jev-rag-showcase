"""Content-addressed PDF indexes stored as data-only JSON, never pickle.

Only the most recently used indexes are retained. Credentials are not part of
an index. The sharing copy starts with no indexes or uploaded documents.
"""
import hashlib
import json
import math
import os
import re
import tempfile

from poc import BM25, EMBED_MODEL

DIR = os.environ.get('ASK_PDF_INDEX_DIR') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data', 'indexes')
MAX_SAVED = 10
VERSION = 2


def fingerprint(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _path(fp):
    if not isinstance(fp, str) or not re.fullmatch(r'[0-9a-f]{64}', fp):
        raise ValueError('Invalid PDF fingerprint')
    return os.path.join(DIR, fp + '.json')


def _valid(record):
    if not isinstance(record, dict) or record.get('version') != VERSION:
        return False
    if record.get('embedding_model') != EMBED_MODEL:
        return False
    if not isinstance(record.get('name'), str) or type(record.get('pages')) is not int or record['pages'] < 1:
        return False
    chunks, vectors = record.get('chunks'), record.get('uvecs')
    if not isinstance(chunks, list) or not chunks or not isinstance(vectors, list) or len(vectors) != len(chunks):
        return False
    ids = set()
    dim = None
    for chunk, vector in zip(chunks, vectors):
        if not isinstance(chunk, dict) or not all(isinstance(chunk.get(key), str) for key in ['id', 'text', 'label', 'section']):
            return False
        if not chunk['text'].strip() or chunk['id'] in ids or type(chunk.get('page')) is not int or not 1 <= chunk['page'] <= record['pages']:
            return False
        ids.add(chunk['id'])
        if not isinstance(vector, list) or not vector:
            return False
        if dim is None:
            dim = len(vector)
        try:
            finite = all(type(value) in (int, float) and math.isfinite(value) for value in vector)
        except OverflowError:
            return False
        if len(vector) != dim or not finite:
            return False
    return True


def save(fp, index):
    target = _path(fp)
    record = {'version': VERSION, 'embedding_model': EMBED_MODEL,
              'name': index['name'], 'pages': index['pages'],
              'chunks': index['chunks'], 'uvecs': index['uvecs']}
    if not _valid(record):
        raise ValueError('Invalid PDF index')
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=DIR,
                                         prefix=fp + '-', suffix='.tmp', delete=False) as output:
            temporary = output.name
            json.dump(record, output, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            try:
                os.remove(temporary)
            except FileNotFoundError:
                pass
    saved = sorted((os.path.join(DIR, name) for name in os.listdir(DIR)
                    if re.fullmatch(r'[0-9a-f]{64}\.json', name)),
                   key=os.path.getmtime, reverse=True)
    for old in saved[MAX_SAVED:]:
        os.remove(old)


def load(fp):
    try:
        path = _path(fp)
        with open(path, encoding='utf-8') as source:
            record = json.load(source)
        if not _valid(record):
            return None
        os.utime(path)
        return {'name': record['name'], 'pages': record['pages'],
                'chunks': record['chunks'], 'uvecs': record['uvecs'],
                'bm25': BM25([chunk['text'] for chunk in record['chunks']])}
    except (OSError, ValueError, TypeError):
        return None
