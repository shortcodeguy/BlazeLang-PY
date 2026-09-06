"""BlazeLang's small, self-validating binary package format (.blzp)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile
import urllib.error
import urllib.request
import zlib
from blazelang.errors.error_handler import BlazeError

MAGIC = b"BLZP\x00"
VERSION = 1
HEADER = struct.Struct(">5sHQ32s")  # magic, version, compressed length, SHA-256

REGISTRY_URL = os.environ.get("BLZ_REGISTRY_URL", "https://blazelang.netlify.app/registry")

# A one-file PyInstaller executable unpacks its code into a new temporary
# directory each run. Package installs therefore cannot live beside
# ``__file__``: an install would disappear before the next ``blz run``.
# LocalAppData is stable, user-writable, and shared by the installed CLI and
# source checkout. BLZ_PACKAGE_HOME is provided for portable/test installs.
_package_home = os.environ.get("BLZ_PACKAGE_HOME")
if _package_home:
    CACHE = Path(_package_home).expanduser().resolve()
else:
    CACHE = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".blaze"))) / "BlazeLang" / "packages"

# Installed packages are queried for every non-local import. Keep the small
# index and parsed manifests in memory for the lifetime of the CLI process;
# cache_package() explicitly refreshes both after an install, so this never
# returns stale data within a process that changes the package cache.
_INDEX_CACHE_PATH: Path | None = None
_INDEX_CACHE: dict | None = None
_MANIFEST_CACHE: dict[Path, dict] = {}


class PackageError(BlazeError, ValueError):
    """Package failures keep their Python catch compatibility and gain a CLI diagnostic."""

    def __init__(self, message: str):
        BlazeError.__init__(
            self, f"Package Error: {message}", code="BLZ3002",
            hint="Check the package manifest, archive integrity, and package path.",
        )


def _safe_name(name: str) -> str:
    if not name or any(c in name for c in "\\/\x00") or name in (".", ".."):
        raise PackageError("Package name must be a simple filename")
    return name


def _safe_relative(name: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PackageError(f"Unsafe package path: {name}")
    return path.as_posix()


def create_package(main_file: str | Path) -> Path:
    main = Path(main_file).resolve()
    if not main.is_file() or main.suffix != ".blz":
        raise PackageError("blz package requires an existing .blz main file")
    project = main.parent
    manifest_path = project / "package.json"
    if not manifest_path.is_file():
        raise PackageError("package.json is required beside the main file")
    try:
        metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageError(f"Invalid package.json: {exc.msg}") from exc
    name = _safe_name(str(metadata.get("name", "")))
    if not isinstance(metadata.get("version", "0.0.0"), str):
        raise PackageError("package.json 'version' must be a string")
    if "description" in metadata and not isinstance(metadata["description"], str):
        raise PackageError("package.json 'description' must be a string")
    declared_main = metadata.get("main", main.name)
    if not isinstance(declared_main, str) or not declared_main:
        raise PackageError("package.json 'main' must be a non-empty .blz path")
    if _safe_relative(str(declared_main)) != main.relative_to(project).as_posix():
        raise PackageError("package.json 'main' must name the supplied main.blz")
    metadata["main"] = str(declared_main).replace("\\", "/")
    metadata.setdefault("version", "0.0.0")
    metadata.setdefault("description", "")
    metadata.setdefault("dependencies", {})
    if not isinstance(metadata["dependencies"], dict):
        raise PackageError("package.json dependencies must be an object")
    files = {}
    table = []
    for source in sorted(project.rglob("*.blz")):
        relative = _safe_relative(source.relative_to(project).as_posix())
        data = source.read_bytes()
        files[relative] = data.decode("utf-8")
        table.append({"path": relative, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    if metadata["main"] not in files:
        raise PackageError("The package main file was not included")
    document = {"metadata": metadata, "files": table, "modules": files, "dependencies": metadata["dependencies"]}
    payload = zlib.compress(json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), level=9)
    binary = HEADER.pack(MAGIC, VERSION, len(payload), hashlib.sha256(payload).digest()) + payload
    output = project.parent / f"{name}.blzp"
    output.write_bytes(binary)
    return output


def read_package(path: str | Path) -> dict:
    raw = Path(path).read_bytes()
    if len(raw) < HEADER.size:
        raise PackageError("Invalid .blzp: truncated header")
    magic, version, length, digest = HEADER.unpack(raw[:HEADER.size])
    payload = raw[HEADER.size:]
    if magic != MAGIC or version != VERSION:
        raise PackageError("Unsupported or invalid .blzp format")
    if len(payload) != length or hashlib.sha256(payload).digest() != digest:
        raise PackageError("Invalid .blzp integrity checksum")
    try:
        document = json.loads(zlib.decompress(payload).decode("utf-8"))
    except (zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError("Invalid .blzp module data") from exc
    metadata, table, modules = document.get("metadata"), document.get("files"), document.get("modules")
    if not isinstance(metadata, dict) or not isinstance(table, list) or not isinstance(modules, dict):
        raise PackageError("Invalid .blzp contents")
    _safe_name(str(metadata.get("name", "")))
    expected = {entry.get("path"): entry for entry in table if isinstance(entry, dict)}
    if set(expected) != set(modules):
        raise PackageError("Invalid .blzp file table")
    for name, source in modules.items():
        safe = _safe_relative(name)
        if not safe.endswith(".blz") or not isinstance(source, str):
            raise PackageError("Invalid .blzp module entry")
        data = source.encode("utf-8")
        entry = expected[name]
        if entry.get("size") != len(data) or entry.get("sha256") != hashlib.sha256(data).hexdigest():
            raise PackageError(f"Integrity check failed for {name}")
    if _safe_relative(str(metadata.get("main", ""))) not in modules:
        raise PackageError("Package main module is missing")
    return document


def _index_path() -> Path: return CACHE / "index.json"


def _index() -> dict:
    global _INDEX_CACHE_PATH, _INDEX_CACHE
    path = _index_path()
    if _INDEX_CACHE_PATH == path and _INDEX_CACHE is not None:
        return _INDEX_CACHE
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        result = {}
    _INDEX_CACHE_PATH, _INDEX_CACHE = path, result
    return result


def cache_package(path: str | Path) -> dict:
    global _INDEX_CACHE_PATH, _INDEX_CACHE
    document = read_package(path)
    meta = document["metadata"]
    name = _safe_name(str(meta["name"]))
    version = str(meta.get("version", "0.0.0"))
    target_dir = CACHE / name / version
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Store ONLY the binary .blzp archive in the package cache directory.
    # No .blz source files are reconstructed or saved on disk.
    blzp_target = target_dir / f"{name}.blzp"
    shutil.copyfile(path, blzp_target)

    index = _index()
    index[name] = {"version": version, "path": str(blzp_target)}
    CACHE.mkdir(parents=True, exist_ok=True)
    _index_path().write_text(json.dumps(index, indent=2), encoding="utf-8")
    _INDEX_CACHE_PATH, _INDEX_CACHE = _index_path(), index
    return document


def load_installed_package(module_name: str) -> dict | None:
    """Return an installed package's raw in-memory .blzp document."""
    pkg_name = module_name.replace("\\", "/").split("/")[0] if any(c in module_name for c in "/\\") else module_name
    record = _index().get(pkg_name)
    if not record:
        return None
    try:
        blzp_path = Path(record["path"])
        if blzp_path.is_file():
            return read_package(blzp_path)
    except (OSError, PackageError):
        return None
    return None


def materialize_installed_module(module_name: str) -> Path | None:
    """Return the installed .blzp archive path for an installed module name."""
    pkg_name = module_name.replace("\\", "/").split("/")[0] if any(c in module_name for c in "/\\") else module_name
    record = _index().get(pkg_name)
    if not record:
        return None
    blzp_path = Path(record["path"])
    return blzp_path if blzp_path.is_file() else None


def _download_github_package(repo: str) -> Path:
    if repo.startswith("github:"):
        repo = repo[7:]
    pieces = repo.strip("/").split("/")
    if len(pieces) != 2 or not all(pieces):
        raise PackageError("GitHub package must be githubuser/repo")
    owner, project = pieces
    api = f"https://api.github.com/repos/{owner}/{project}"
    try:
        info = json.loads(urllib.request.urlopen(api, timeout=30).read().decode("utf-8"))
        branch = info["default_branch"]
        tree_url = f"{api}/git/trees/{branch}?recursive=1"
        tree = json.loads(urllib.request.urlopen(tree_url, timeout=30).read().decode("utf-8"))["tree"]
        choices = [item["path"] for item in tree if item.get("type") == "blob" and item.get("path", "").endswith(".blzp")]
        if not choices:
            raise PackageError("GitHub repository contains no .blzp package")
        wanted = project + ".blzp"
        selected = next((x for x in choices if x == wanted), next((x for x in choices if "/" not in x), choices[0]))
        url = f"https://raw.githubusercontent.com/{owner}/{project}/{branch}/{selected}"
        data = urllib.request.urlopen(url, timeout=60).read()
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise PackageError(f"Unable to download GitHub package '{repo}': {exc}") from exc
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".blzp")
    try:
        temp.write(data)
        return Path(temp.name)
    finally:
        temp.close()


def install_github_package(repo: str, _seen=None) -> dict:
    """Download, validate, cache, then recursively install dependencies."""
    seen = _seen if _seen is not None else set()
    if repo in seen:
        return {}
    seen.add(repo)
    downloaded = _download_github_package(repo)
    try:
        document = cache_package(downloaded)
    finally:
        downloaded.unlink(missing_ok=True)
    for dependency in document["metadata"].get("dependencies", {}).values():
        if isinstance(dependency, str):
            install_package(dependency)
    return document["metadata"]


def install_package(spec: str) -> dict:
    """
    Install a package from the BlazeLang Registry, a local .blzp file path,
    or a GitHub repository shorthand (user/repo).
    """
    spec_path = Path(spec)
    if spec_path.is_file() or spec.endswith(".blzp"):
        if not spec_path.is_file():
            raise PackageError(f"Local package file not found: {spec}")
        document = cache_package(spec_path)
        meta = document["metadata"]
        print(f"Package installed successfully: {meta['name']}@{meta.get('version', '0.0.0')}")
        return meta

    # Handle requested exact version syntax (e.g. blz-utils@1.0.0)
    if "@" in spec and "/" not in spec:
        pkg_name, requested_version = spec.split("@", 1)
    else:
        pkg_name, requested_version = spec, None

    if "/" in pkg_name:
        return install_github_package(spec)

    _safe_name(pkg_name)
    print(f"Resolving package: {pkg_name}")

    reg_base = os.environ.get("BLZ_REGISTRY_URL", REGISTRY_URL).rstrip("/")
    pkg_url = f"{reg_base}/packages/{pkg_name}.json"

    req = urllib.request.Request(pkg_url, headers={"User-Agent": "BlazeLang-CLI/2.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_json = resp.read().decode("utf-8")
            pkg_meta = json.loads(raw_json)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            raise PackageError(f"Package '{pkg_name}' not found in registry") from err
        raise PackageError(f"Registry HTTP error {err.code} while fetching '{pkg_name}'") from err
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise PackageError(f"Failed to connect to BlazeLang Registry: {err}") from err
    except json.JSONDecodeError as err:
        raise PackageError(f"Invalid registry JSON response for '{pkg_name}'") from err

    if not isinstance(pkg_meta, dict) or "versions" not in pkg_meta:
        raise PackageError(f"Malformed registry metadata for '{pkg_name}'")

    versions = pkg_meta.get("versions", {})
    if not isinstance(versions, dict) or not versions:
        raise PackageError(f"No versions available for package '{pkg_name}'")

    if requested_version:
        if requested_version not in versions:
            raise PackageError(f"Version '{requested_version}' of package '{pkg_name}' not found in registry")
        target_version = requested_version
    else:
        target_version = pkg_meta.get("latest")
        if not target_version or target_version not in versions:
            target_version = sorted(versions.keys())[-1]

    # Check if already installed
    installed_record = _index().get(pkg_name)
    if installed_record and installed_record.get("version") == target_version:
        blzp_p = Path(installed_record["path"])
        if blzp_p.is_file():
            print(f"Package already installed: {pkg_name}@{target_version}")
            print("Skipped.")
            return read_package(blzp_p)["metadata"]

    if not requested_version:
        print(f"Latest version: {target_version}")

    version_info = versions[target_version]
    download_url = version_info.get("download")
    if not download_url or not isinstance(download_url, str):
        raise PackageError(f"Missing download URL for {pkg_name}@{target_version}")

    print(f"Downloading {pkg_name}@{target_version}...")
    try:
        dl_req = urllib.request.Request(download_url, headers={"User-Agent": "BlazeLang-CLI/2.1.0"})
        with urllib.request.urlopen(dl_req, timeout=60) as resp:
            pkg_bytes = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise PackageError(f"Failed to download package '{pkg_name}@{target_version}': {err}") from err

    print("Verifying package...")
    expected_sha256 = version_info.get("sha256")
    if expected_sha256 and isinstance(expected_sha256, str):
        actual_sha256 = hashlib.sha256(pkg_bytes).hexdigest()
        if actual_sha256.lower() != expected_sha256.lower():
            print("Package integrity verification failed.")
            print("SHA-256 checksum does not match the registry.")
            print("Installation aborted.")
            raise PackageError(f"SHA-256 checksum mismatch for {pkg_name}@{target_version}")

    print("Installing...")
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".blzp")
    try:
        temp_file.write(pkg_bytes)
        temp_file.close()
        doc = cache_package(Path(temp_file.name))
        print(f"Package installed successfully: {pkg_name}@{target_version}")
        return doc["metadata"]
    finally:
        if os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass
