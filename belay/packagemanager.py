import ast
from contextlib import nullcontext
from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse

import httpx
import tomli
from rich.console import Console
from typer import Option


class NonMatchingURL(Exception):
    pass


def _strip_www(url: str):
    if url.startswith("www."):
        url = url[4:]
    return url


def _process_url_github(url: str):
    """Transforms github-like url into githubusercontent."""
    url = str(url)
    parsed = urlparse(url)
    netloc = _strip_www(parsed.netloc)
    if netloc == "github.com":
        # Transform to raw.githubusercontent
        _, user, project, mode, branch, *path = parsed.path.split("/")
        return f"https://raw.githubusercontent.com/{user}/{project}/{branch}/{'/'.join(path)}"
    elif netloc == "raw.githubusercontent.com":
        return f"https://raw.githubusercontent.com{parsed.path}"
    else:
        # TODO: Try and be a little helpful if url contains github.com
        raise NonMatchingURL


def _process_url(url: str):
    parsers = [
        _process_url_github,
    ]
    for parser in parsers:
        try:
            return parser(url)
        except NonMatchingURL:
            pass

    # Unmodified URL
    return url


def _get_text(url: str):
    res = httpx.get(url)
    res.raise_for_status()
    return res.text


def download_dependencies(
    dependencies: Dict[str, Union[str, Dict]],
    packages: Optional[List[str]] = None,
    local_dir: Union[str, Path] = ".belay-lib",
    console: Optional[Console] = None,
):
    """Download dependencies.

    Parameters
    ----------
    dependencies: dict
        Dependencies to install (probably parsed from TOML file).
    packages: Optional[List[str]]
        Only download this package.
    local_dir: Union[str, Path]
        Download dependencies to this directory.
        Will create directories as necessary.
    console: Optional[Console]
        Print progress out to console.
    """
    local_dir = Path(local_dir)
    if not packages:
        # Update all packages
        packages = list(dependencies.keys())

    if console:
        cm = console.status("[bold green]Updating Dependencies")
    else:
        cm = nullcontext()

    def log(*args, **kwargs):
        if console:
            console.log(*args, **kwargs)

    with cm:
        from time import sleep

        for pkg_name in packages:
            dep = dependencies[pkg_name]
            if isinstance(dep, str):
                dep = {"path": dep}
            elif not isinstance(dep, dict):
                raise ValueError(f"Invalid value for key {pkg_name}.")

            log(f"{pkg_name}: Updating...")

            sleep(1)
            url = _process_url(dep["path"])
            ext = Path(url).suffix
            if ext == ".py":
                # Single file
                dst = local_dir / (pkg_name + ext)
                dst.parent.mkdir(parents=True, exist_ok=True)

                new_code = _get_text(url)
                ast.parse(new_code)  # Check for valid python code

                try:
                    old_code = dst.read_text()
                except FileNotFoundError:
                    old_code = ""

                if new_code == old_code:
                    log(f"{pkg_name}: No changes detected.")
                else:
                    log(f"{pkg_name}: Updated.")
                    dst.write_text(new_code)
            else:
                raise NotImplementedError(f"Don't know how to process {url}.")
