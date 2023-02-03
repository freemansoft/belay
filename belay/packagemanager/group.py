import ast
import shutil
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

from rich.console import Console

from belay.packagemanager.downloaders import download_uri
from belay.packagemanager.sync import sync
from belay.typing import PathType


# TODO: maybe use pydantic.dataclass
@dataclass
class GroupConfig:
    """Schema and store of a group defined in ``pyproject.toml``.

    Don't put any methods in here, they go in ``Group``.
    Don't directly instnatiate ``GroupConfig`` outside of ``Config``.
    This class is primarily for namespacing and validation.
    """

    name: str
    optional: bool = False
    dependencies: Dict[str, Union[list, dict, str]] = field(default_factory=dict)


class Group:
    """Represents a group defined in ``pyproject.toml``."""

    def __init__(self, *args, **kwargs):
        from belay.project import find_dependencies_folder

        self.config = GroupConfig(*args, **kwargs)

        self.folder = find_dependencies_folder() / self.config.name

        if self.config.optional:
            raise NotImplementedError("Optional groups not implemented yet.")

    def __eq__(self, other):
        if not isinstance(other, Group):
            return False
        return self.config.__dict__ == other.config.__dict__

    def __repr__(self):
        kws = [f"{key}={value!r}" for key, value in self.config.__dict__.items()]
        return f"{type(self).__name__}({', '.join(kws)})"

    @property
    def dependencies(self):
        return self.config.dependencies

    def clean(self):
        """Delete any dependency module not specified in ``self.config.dependencies``."""
        dependencies = set(self.dependencies)
        existing_deps = []

        if not self.folder.exists():
            return

        existing_deps.extend(self.folder.glob("*"))

        for existing_dep in existing_deps:
            if existing_dep.name in dependencies:
                continue
            existing_dep.unlink()

    def copy_to(self, dst):
        """Copy Dependencies folder to destination directory."""
        if self.folder.exists():
            shutil.copytree(self.folder, dst, dirs_exist_ok=True)

    def download(
        self,
        packages: Optional[List[str]] = None,
        console: Optional[Console] = None,
    ):
        """Download dependencies.

        Parameters
        ----------
        packages: Optional[List[str]]
            Only download these package.
        console: Optional[Console]
            Print progress out to console.
        """
        if packages is None:
            # Update all packages
            packages = list(self.dependencies.keys())

        if not packages:
            return

        if console:
            cm = console.status("[bold green]Updating Dependencies")
        else:
            cm = nullcontext()

        def log(*args, **kwargs):
            if console:
                console.log(*args, **kwargs)

        with cm:
            for package_name in packages:
                local_folder = self.folder / package_name
                local_folder.mkdir(exist_ok=True, parents=True)

                dep_src = self.dependencies[package_name]

                if isinstance(dep_src, str):
                    # TODO: as we allow dict dependency specifiers, this should mirror it.
                    dep_src = {"remote": dep_src}
                elif isinstance(dep_src, list):
                    raise NotImplementedError("List dependencies not yet supported.")
                elif not isinstance(dep_src, dict):
                    raise NotImplementedError(
                        "Dictionary dependencies not yet supported."
                    )

                log(f"{package_name}: Updating...")

                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_dir = Path(tmp_dir)
                    download_uri(tmp_dir, dep_src["remote"])
                    _verify_files(tmp_dir)
                    changed = sync(tmp_dir, local_folder)

                if changed:
                    log(f"[bold green]{package_name}: Updated.")
                else:
                    log(f"{package_name}: No changes detected.")


def _verify_files(folder: PathType):
    """Sanity checks downloaded files.

    Currently just checks if ".py" files are valid python code.
    """
    folder = Path(folder)
    for f in folder.rglob("*"):
        if f.suffix == ".py":
            code = f.read_text()
            ast.parse(code)
