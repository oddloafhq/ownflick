"""Check the standalone service with synthetic images; never read private media."""

import base64
import json
import math
import struct
import time
import urllib.request
import zlib


def image_url(color: tuple[int, int, int]) -> str:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack('!I', len(data)) + kind + data
                + struct.pack('!I', zlib.crc32(kind + data)))

    size = 128
    pixels = (b'\x00' + bytes(color) * size) * size
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))
    return 'data:image/png;base64,' + base64.b64encode(png).decode()


def embed(value: str | dict | list) -> list[float]:
    request = urllib.request.Request(
        'http://127.0.0.1:9379/v1/embeddings',
        data=json.dumps({'model': 'embeddinggemma-2', 'input': value,
                         'dimensions': 768, 'encoding_format': 'float'}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=180) as response:
        vector = json.load(response)['data'][0]['embedding']
    assert len(vector) == 768 and all(math.isfinite(x) for x in vector)
    assert sum(x * x for x in vector) > 0
    print(f'valid vector: 768 dimensions, {time.monotonic() - started:.2f}s')
    return vector


if __name__ == '__main__':
    vectors = [embed([{'content': [{'type': 'image_url', 'image_url': {'url': image_url(color)}}]}])
               for color in [(255, 0, 0), (0, 0, 255)]]
    assert vectors[0] != vectors[1], 'Different images returned identical vectors'
    text = embed('A red square')
    for color, vector in zip(['red', 'blue'], vectors):
        score = sum(a * b for a, b in zip(text, vector)) / math.sqrt(
            sum(a * a for a in text) * sum(b * b for b in vector)
        )
        print(f'Text "A red square" vs {color} image: cosine={score:.4f}')
    print('Image and text requests passed; this is not a retrieval quality benchmark.')
