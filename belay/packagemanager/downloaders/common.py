from pathlib import Path

import fsspec
from autoregistry import Registry

from belay.typing import PathType

# Downloaders should have function signature
#    def downloader(dst: Path, uri: str) -> Path
# where the return value is one of:
#    1. ``dst`` if a folder was downloaded
#    2. Path to single file if the URI was for a single file.
downloaders = Registry()


class NonMatchingURI(Exception):
    """Provided URI does not match downloading function."""


# DO NOT decorate with ``@downloaders``, since this must be last.
def _download_generic(dst: Path, uri: str) -> Path:
    """Downloads a single file to ``dst / "__init__.py"``."""
    try:
        with fsspec.open(uri, "rb") as f:
            data = f.read()

        dst /= Path(uri).name
        with dst.open("wb") as f:
            f.write(data)
    except IsADirectoryError:
        fs = fsspec.filesystem("file")
        fs.get(uri, str(dst), recursive=True)

    return dst


def download_uri(dst_folder: PathType, uri: str) -> Path:
    """Download ``uri`` by trying all downloaders on ``uri`` until one works."""
    dst_folder = Path(dst_folder)
    for processor in downloaders.values():
        try:
            return processor(dst_folder, uri)
            break
        except NonMatchingURI:
            pass
    else:
        return _download_generic(dst_folder, uri)
