"""
LocalStorage persistence for BlazeLang
Small, file-backed key/value store for simple AI/program state
(epoch, loss, accuracy, hyperparameters, config, ...) that survives
program restarts.

Exposed to BlazeLang as six namespace objects, matching how other
grouped builtins are surfaced (e.g. Math.floor-style dotted access):

    Save.LocalStorage(key, value)
    Load.LocalStorage(key)
    Delete.LocalStorage(key)
    Exists.LocalStorage(key)
    Clear.LocalStorage()
    List.LocalStorage()

Storage is a single JSON file per BlazeLang installation, written with
Python's `json` module only -- values are serialized as data, never as
code, so nothing stored on disk is ever executed (str/int/float/bool/
None/list/dict round-trip losslessly; anything else is rejected before
it reaches disk).
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from blazelang.errors.error_handler import ArgumentError, StorageError


# Values that JSON (and therefore LocalStorage) can represent faithfully.
# dict/list are checked recursively in _validate so nested structures of
# these same types are also accepted.
_SCALAR_TYPES = (str, int, float, bool, type(None))


def _default_storage_path() -> Path:
    """Where BlazeLang's LocalStorage file lives.

    Honors BLAZELANG_HOME if set (matches how other BlazeLang tooling
    locates its config/cache directory); otherwise falls back to a
    per-user directory under the home folder, mirroring the convention
    other language runtimes use for local app state.
    """
    home = os.environ.get("BLAZELANG_HOME")
    base = Path(home) if home else Path.home() / ".blazelang"
    return base / "localstorage.json"


def _validate(value: Any, key: str) -> None:
    """Reject values LocalStorage can't safely persist as data.

    Anything that made it into this function running as a live Python
    object executed no attacker-controlled code to get here -- this
    check is about round-trip fidelity (only JSON-safe shapes survive
    Save -> disk -> Load unchanged), not sandboxing.
    """
    if isinstance(value, _SCALAR_TYPES):
        return
    if isinstance(value, list):
        for item in value:
            _validate(item, key)
        return
    if isinstance(value, dict):
        for sub_key, sub_value in value.items():
            if not isinstance(sub_key, str):
                raise ArgumentError.for_type_mismatch(
                    "Save.LocalStorage", "string (map key)", sub_key
                )
            _validate(sub_value, key)
        return
    raise ArgumentError.for_type_mismatch(
        "Save.LocalStorage", "string, int, float, bool, null, list, or map", value
    )


class LocalStorageStore:
    """Backs Save/Load/Delete/Exists/Clear/List.LocalStorage with a single
    JSON file on disk. All reads/writes go through this one class so file
    handling (locations, atomic writes, corruption handling) lives in
    exactly one place.

    Keeps a small in-process cache of the last data read from disk so that
    several LocalStorage calls within one program run don't each re-read
    and re-parse the file: the cache is filled lazily on first read and
    invalidated (dropped) on any write this store performs, so a fresh
    read only happens when the on-disk file might actually have changed
    -- either because this store wrote it, or because it hasn't been read
    yet this run. It never assumes the file *can't* have changed
    externally between two of this store's own calls; every write still
    re-reads first (see _read_all/_write_all below) so two calls in the
    same run don't silently clobber each other's changes.
    """

    def __init__(self, path: Path = None):
        self.path = Path(path) if path else _default_storage_path()
        self._cache: dict = None  # None = not loaded yet (or invalidated)

    # --- low-level file I/O -------------------------------------------------

    def _read_all(self) -> dict:
        """Load the whole store as a dict, using the in-process cache when
        it's still valid. Missing file -> empty store. A corrupted/
        unreadable file raises a BlazeLang StorageError rather than
        crashing the interpreter or silently discarding data."""
        if self._cache is not None:
            return self._cache

        if not self.path.exists():
            self._cache = {}
            return self._cache
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"could not read LocalStorage file '{self.path}': {exc}")

        if not text.strip():
            self._cache = {}
            return self._cache

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StorageError(
                f"LocalStorage file '{self.path}' is corrupted and could not be parsed ({exc})"
            )

        if not isinstance(data, dict):
            raise StorageError(
                f"LocalStorage file '{self.path}' is corrupted (expected a JSON object at the top level)"
            )
        self._cache = data
        return self._cache

    def _write_all(self, data: dict) -> None:
        """Atomically overwrite the store file: write to a temp file in the
        same directory, then rename over the original. Avoids ever leaving
        a half-written/corrupted file behind if the process dies mid-write.
        Updates the in-process cache to the just-written data on success --
        the next read in this run reflects the write without touching disk
        again -- and invalidates it on failure, so a subsequent read falls
        back to re-reading whatever is actually on disk."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self.path.parent), prefix=".localstorage-", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                    json.dump(data, tmp_file, indent=2, sort_keys=True)
                os.replace(tmp_name, self.path)
            except BaseException:
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
                self._cache = None
                raise
        except OSError as exc:
            self._cache = None
            raise StorageError(f"could not write LocalStorage file '{self.path}': {exc}")
        self._cache = data

    # --- public operations ---------------------------------------------------

    def save(self, key: str, value: Any) -> None:
        _validate(value, key)
        data = self._read_all()
        # Skip the write entirely when the value is unchanged -- keeps
        # repeated Save() calls with the same key/value (a common pattern,
        # e.g. re-saving config every loop iteration) from touching disk
        # each time.
        if key in data and data[key] == value and type(data[key]) is type(value):
            return
        data = dict(data)
        data[key] = value
        self._write_all(data)

    def load(self, key: str) -> Any:
        data = self._read_all()
        return data.get(key, None)

    def delete(self, key: str) -> None:
        data = self._read_all()
        if key in data:
            data = dict(data)
            del data[key]
            self._write_all(data)
        # Missing key: safe no-op, nothing to write.

    def exists(self, key: str) -> bool:
        return key in self._read_all()

    def clear(self) -> None:
        # Skip the write if there's already nothing to clear.
        if not self._read_all():
            return
        self._write_all({})

    def list_keys(self) -> list:
        return list(self._read_all().keys())


class _SaveNamespace:
    """Backs the `Save` identifier: Save.LocalStorage(key, value)."""

    def __init__(self, store: LocalStorageStore):
        self._store = store

    def LocalStorage(self, *args):
        if len(args) != 2:
            raise ArgumentError("Save.LocalStorage", 2, len(args))
        key, value = args
        if not isinstance(key, str):
            raise ArgumentError.for_type_mismatch("Save.LocalStorage", "string", key)
        self._store.save(key, value)
        return None


class _LoadNamespace:
    """Backs the `Load` identifier: Load.LocalStorage(key)."""

    def __init__(self, store: LocalStorageStore):
        self._store = store

    def LocalStorage(self, *args):
        if len(args) != 1:
            raise ArgumentError("Load.LocalStorage", 1, len(args))
        key = args[0]
        if not isinstance(key, str):
            raise ArgumentError.for_type_mismatch("Load.LocalStorage", "string", key)
        return self._store.load(key)


class _DeleteNamespace:
    """Backs the `Delete` identifier: Delete.LocalStorage(key)."""

    def __init__(self, store: LocalStorageStore):
        self._store = store

    def LocalStorage(self, *args):
        if len(args) != 1:
            raise ArgumentError("Delete.LocalStorage", 1, len(args))
        key = args[0]
        if not isinstance(key, str):
            raise ArgumentError.for_type_mismatch("Delete.LocalStorage", "string", key)
        self._store.delete(key)
        return None


class _ExistsNamespace:
    """Backs the `Exists` identifier: Exists.LocalStorage(key)."""

    def __init__(self, store: LocalStorageStore):
        self._store = store

    def LocalStorage(self, *args):
        if len(args) != 1:
            raise ArgumentError("Exists.LocalStorage", 1, len(args))
        key = args[0]
        if not isinstance(key, str):
            raise ArgumentError.for_type_mismatch("Exists.LocalStorage", "string", key)
        return self._store.exists(key)


class _ClearNamespace:
    """Backs the `Clear` identifier: Clear.LocalStorage()."""

    def __init__(self, store: LocalStorageStore):
        self._store = store

    def LocalStorage(self, *args):
        if len(args) != 0:
            raise ArgumentError("Clear.LocalStorage", 0, len(args))
        self._store.clear()
        return None


class _ListNamespace:
    """Backs the `List` identifier: List.LocalStorage()."""

    def __init__(self, store: LocalStorageStore):
        self._store = store

    def LocalStorage(self, *args):
        if len(args) != 0:
            raise ArgumentError("List.LocalStorage", 0, len(args))
        return self._store.list_keys()


def build_localstorage_namespaces(store: LocalStorageStore = None) -> dict:
    """Return the {'Save': ..., 'Load': ..., ...} namespace objects to
    register in the interpreter's global scope, all sharing one
    LocalStorageStore (and therefore one on-disk file)."""
    store = store or LocalStorageStore()
    return {
        "Save": _SaveNamespace(store),
        "Load": _LoadNamespace(store),
        "Delete": _DeleteNamespace(store),
        "Exists": _ExistsNamespace(store),
        "Clear": _ClearNamespace(store),
        "List": _ListNamespace(store),
    }