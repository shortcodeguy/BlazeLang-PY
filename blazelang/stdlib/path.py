"""Native, cross-platform path manipulation for BlazeLang."""

import os
from pathlib import Path


class PathLibrary:
    @staticmethod
    def _path(value): return Path(str(value).replace("\\", os.sep).replace("/", os.sep))
    def join(self, *parts): return str(Path(*[str(part) for part in parts])) if parts else ""
    def normalize(self, path): return os.path.normpath(str(self._path(path)))
    def file_name(self, path): return self._path(path).name
    def directory(self, path): return str(self._path(path).parent)
    def extension(self, path): return self._path(path).suffix.lstrip(".")
    def parent(self, path): return str(self._path(path).parent)


def create_path_module():
    library = PathLibrary()
    return {"Join": library.join, "Normalize": library.normalize, "FileName": library.file_name,
            "Directory": library.directory, "Extension": library.extension, "Parent": library.parent}
