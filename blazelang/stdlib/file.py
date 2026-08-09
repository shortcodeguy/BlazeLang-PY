"""Cross-platform UTF-8 file-system support for the BlazeLang standard library."""

import errno
import os
import shutil
from pathlib import Path

from blazelang.errors.error_handler import FileSystemError


class FileLibrary:
    """Expose synchronous text-file operations relative to a BlazeLang source file.

    All public methods accept strings or values convertible to strings.  Relative
    paths are resolved from ``base_dir`` so running a program from another working
    directory never changes where its data files are stored.
    """

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path.cwd()).resolve()

    def read(self, path):
        target = self._path(path)
        try:
            with target.open("r", encoding="utf-8", buffering=64 * 1024) as handle:
                return handle.read()
        except OSError as error:
            self._raise("Unable to open file", path, error)

    def write(self, path, content):
        target = self._path(path)
        try:
            self._require_parent(target)
            with target.open("w", encoding="utf-8", buffering=64 * 1024) as handle:
                handle.write(str(content))
            return True
        except OSError as error:
            self._raise("Unable to write file", path, error)

    def append(self, path, content):
        target = self._path(path)
        try:
            self._require_parent(target)
            with target.open("a", encoding="utf-8", buffering=64 * 1024) as handle:
                handle.write(str(content))
            return True
        except OSError as error:
            self._raise("Unable to append file", path, error)

    def exists(self, path):
        return self._path(path).is_file()

    def delete(self, path):
        target = self._path(path)
        try:
            target.unlink()
            return True
        except OSError as error:
            self._raise("Unable to delete file", path, error)

    def copy(self, source, destination):
        source_path, destination_path = self._path(source), self._path(destination)
        try:
            self._require_parent(destination_path)
            shutil.copyfile(source_path, destination_path)
            shutil.copystat(source_path, destination_path)
            return True
        except OSError as error:
            self._raise("Unable to copy file", source, error)

    def move(self, source, destination):
        source_path, destination_path = self._path(source), self._path(destination)
        try:
            self._require_parent(destination_path)
            shutil.move(str(source_path), str(destination_path))
            return True
        except OSError as error:
            self._raise("Unable to move file", source, error)

    def rename(self, source, destination):
        source_path, destination_path = self._path(source), self._path(destination)
        try:
            self._require_parent(destination_path)
            source_path.rename(destination_path)
            return True
        except OSError as error:
            self._raise("Unable to rename file", source, error)

    def size(self, path):
        target = self._path(path)
        try:
            return target.stat().st_size
        except OSError as error:
            self._raise("Unable to read file size", path, error)

    def extension(self, path):
        return self._path(path).suffix.lstrip(".")

    def create_directory(self, path):
        target = self._path(path)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as error:
            self._raise("Unable to create directory", path, error)

    def delete_directory(self, path, recursive=False):
        target = self._path(path)
        try:
            if recursive:
                shutil.rmtree(target)
            else:
                target.rmdir()
            return True
        except OSError as error:
            self._raise("Unable to delete directory", path, error)

    def exists_directory(self, path):
        return self._path(path).is_dir()

    def list_files(self, path="."):
        target = self._path(path)
        try:
            return sorted(entry.name for entry in target.iterdir() if entry.is_file())
        except OSError as error:
            self._raise("Unable to list files", path, error)

    def list_directories(self, path="."):
        target = self._path(path)
        try:
            return sorted(entry.name for entry in target.iterdir() if entry.is_dir())
        except OSError as error:
            self._raise("Unable to list directories", path, error)

    def _path(self, path):
        candidate = Path(str(path).replace("\\", os.sep).replace("/", os.sep))
        return (candidate if candidate.is_absolute() else self.base_dir / candidate).resolve()

    @staticmethod
    def _require_parent(target):
        if not target.parent.is_dir():
            raise FileNotFoundError(errno.ENOENT, "Parent directory does not exist", str(target.parent))

    @staticmethod
    def _raise(action, path, error):
        raise FileSystemError(
            f"{action}\n\n{path}\n\nReason\n\n{FileLibrary._reason(error)}",
            hint=FileLibrary._hint(error),
        )

    @staticmethod
    def _reason(error):
        if isinstance(error, FileNotFoundError):
            return "File or directory does not exist."
        if isinstance(error, PermissionError):
            return "Permission was denied."
        if getattr(error, "errno", None) == errno.ENOSPC:
            return "The disk is full."
        if getattr(error, "errno", None) in (errno.EEXIST, errno.ENOTEMPTY):
            return "A file or non-empty directory already exists at that path."
        return str(error)

    @staticmethod
    def _hint(error):
        if isinstance(error, FileNotFoundError):
            return "Check that the file and its parent directory exist and the path is correct."
        if isinstance(error, PermissionError):
            return "Check the file permissions and whether another program is locking the file."
        if getattr(error, "errno", None) == errno.ENOSPC:
            return "Free disk space and try again."
        if getattr(error, "errno", None) in (errno.EEXIST, errno.ENOTEMPTY):
            return "Use a different path or remove the existing item first."
        return "Check the path and the operating system error shown above."


def create_file_module(base_dir=None):
    """Return the public BlazeLang ``File`` namespace."""
    library = FileLibrary(base_dir)
    return {
        "Read": library.read, "Write": library.write, "Append": library.append,
        "Exists": library.exists, "Delete": library.delete, "Copy": library.copy,
        "Move": library.move, "Rename": library.rename, "Size": library.size,
        "Extension": library.extension, "CreateDirectory": library.create_directory,
        "DeleteDirectory": library.delete_directory, "ExistsDirectory": library.exists_directory,
        "ListFiles": library.list_files, "ListDirectories": library.list_directories,
    }
