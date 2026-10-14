"""Download verified GGUF files into the isolated model volume."""

import hashlib
from pathlib import Path
import urllib.request


REVISION = 'bfcd298762cc34d0357ece5ebdd31791a3a374d8'
FILES = {
    'model.gguf': (
        'embeddinggemma-2-Q8_0.gguf',
        '2188ac1deca4b77dffefd603c2776a9d76d9d74ec01841392982ebb840b09135',
    ),
    'mmproj.gguf': (
        'mmproj-embeddinggemma-2-Q8_0.gguf',
        'c4a8a52691ecef40618438928bdf9e68379b854e24166f292592353db0aab64f',
    ),
}


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download_models() -> None:
    root = Path('/models')
    root.mkdir(parents=True, exist_ok=True)
    for name, (remote, expected) in FILES.items():
        target = root / name
        if target.exists() and checksum(target) == expected:
            print(f'{name}: already verified', flush=True)
            continue
        url = f'https://huggingface.co/ggml-org/embeddinggemma-2-GGUF/resolve/{REVISION}/{remote}'
        partial = target.with_suffix('.part')
        print(f'{name}: downloading', flush=True)
        try:
            with urllib.request.urlopen(url, timeout=60) as response, partial.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if checksum(partial) != expected:
                raise RuntimeError(f'{name}: checksum mismatch')
            partial.replace(target)
            target.chmod(0o644)
            print(f'{name}: verified', flush=True)
        finally:
            partial.unlink(missing_ok=True)


if __name__ == '__main__':
    download_models()
