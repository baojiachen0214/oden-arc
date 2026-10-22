"""Bounded input, strict JSON, safe paths and exclusive output transactions."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from typing import Any, Iterator
from urllib.parse import urlsplit

MAX_JSON = 16 * 1024 * 1024
MAX_ASSET = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_NODES = 5000
MAX_DEPTH = 512
MAX_PIXELS = 40_000_000
HEX256 = re.compile(r"^[0-9a-f]{64}$")


class SkillError(ValueError):
    """Expected, actionable validation failure; not a programmer exception."""
    def __init__(self, code: str, message: str, location: str = "") -> None:
        self.code, self.message, self.location = code, message, location
        super().__init__(f"{code}: {message}" + (f" [{location}]" if location else ""))

    def as_dict(self) -> dict[str, Any]:
        return {"ok": False, "code": self.code, "message": self.message,
                "location": self.location}


def require(condition: bool, message: str, location: str = "", code: str = "invalid") -> None:
    if not condition:
        raise SkillError(code, message, location)


def obj(value: Any, location: str) -> dict:
    require(isinstance(value, dict), "Expected an object", location)
    return value


def arr(value: Any, location: str, limit: int = 10000) -> list:
    require(isinstance(value, list), "Expected an array", location)
    require(len(value) <= limit, f"Array exceeds limit {limit}", location, "limit")
    return value


def text(value: Any, location: str, *, blank: bool = False, limit: int = 100000) -> str:
    require(isinstance(value, str), "Expected a string", location)
    require(len(value) <= limit, f"Text exceeds {limit} characters", location, "limit")
    require(blank or bool(value.strip()), "Expected nonempty text", location)
    require(not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
            "Unpaired Unicode surrogate", location)
    require(not any(ord(c) < 32 and c not in "\n\t\r" for c in value),
            "Unsupported control character", location)
    return value


def boolean(value: Any, location: str) -> bool:
    require(type(value) is bool, "Expected a boolean", location)
    return value


def number(value: Any, location: str, low: float, high: float) -> float:
    require(type(value) in (int, float), "Expected a number, not a boolean", location)
    require(low <= value <= high, f"Expected finite {low} <= value <= {high}", location)
    require(math.isfinite(value), "Expected a finite number", location)
    return value


def enum(value: Any, choices: set[str], location: str) -> str:
    require(isinstance(value, str) and value in choices,
            f"Expected one of {sorted(choices)}", location)
    return value


def only_keys(value: dict, keys: set[str], location: str) -> None:
    extra = set(value) - keys
    require(not extra, f"Unknown fields: {sorted(extra)}; use extensions for metadata", location)


def identifier(value: Any, location: str) -> str:
    value = text(value, location, limit=160)
    require(not any(c in value for c in "/\\\r\n\t") and value not in {".", ".."},
            "Identifier cannot be a path", location)
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key {key!r}", code="json")
        result[key] = value
    return result


def bad_constant(value: str) -> None:
    raise SkillError("json", f"Non-finite JSON number: {value}")


def reject_symlinks(path: Path) -> None:
    path = Path(os.path.abspath(path))
    for part in [path, *path.parents]:
        require(not part.is_symlink(), "Symlink paths are not accepted", str(part), "path")


def read_bytes(path: Path, limit: int = MAX_ASSET) -> bytes:
    reject_symlinks(path)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode), "Expected a regular file", str(path), "path")
            require(info.st_size <= limit, f"File exceeds {limit} bytes", str(path), "limit")
            parts = []
            total = 0
            while True:
                part = stream.read(min(1024 * 1024, limit - total + 1))
                if not part:
                    break
                total += len(part)
                require(total <= limit, f"File exceeds {limit} bytes", str(path), "limit")
                parts.append(part)
            return b"".join(parts)
    except OSError as exc:
        raise SkillError("io", str(exc), str(path)) from exc


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_bytes(path, MAX_JSON).decode("utf-8-sig"),
                          object_pairs_hook=strict_pairs, parse_constant=bad_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SkillError("json", str(exc), str(path)) from exc


def json_bytes(value: Any) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                           allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, UnicodeEncodeError, RecursionError) as exc:
        raise SkillError("json", f"Cannot serialize JSON: {exc}") from exc


def write_new(path: Path, data: bytes) -> None:
    """Never truncate an existing output (including a symlink)."""
    reject_symlinks(path)
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except OSError as exc:
        raise SkillError("output", str(exc), str(path)) from exc


def safe_relative(base: Path, value: Any) -> Path:
    value = text(value, "relative path", limit=4096)
    require("\\" not in value and ":" not in value and "\x00" not in value,
            "Use POSIX relative paths without drive or URI prefixes", value, "path")
    p = PurePosixPath(value)
    require(not p.is_absolute() and ".." not in p.parts and p.parts and p.parts != (".",),
            "Path must remain inside the material directory", value, "path")
    path = Path(os.path.abspath(base)) / Path(*p.parts)
    reject_symlinks(path)
    require(path.is_relative_to(Path(os.path.abspath(base))), "Path escapes base", value, "path")
    return path


def safe_link(value: Any, location: str = "link") -> str:
    value = text(value, location, limit=8192)
    require(not any(c.isspace() for c in value), "URL cannot contain whitespace", location)
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
    except ValueError as exc:
        raise SkillError("url", str(exc), location) from exc
    require(parts.scheme.lower() in {"https", "http", "mailto"},
            "Only http, https and mailto links are accepted; nothing is fetched", location)
    if parts.scheme.lower() in {"http", "https"}:
        require(bool(parts.hostname) and not parts.username and not parts.password,
                "URL requires a host and must not contain credentials", location)
    return value


def is_remote(value: str) -> bool:
    try:
        return urlsplit(value).scheme.lower() in {"http", "https", "mailto"}
    except ValueError as exc:
        raise SkillError("url", str(exc), "source URI") from exc


@contextmanager
def exclusive_directory(destination: Path) -> Iterator[Path]:
    """Reserve once with mkdir. Incomplete outputs are visibly marked.

    Cooperative writers cannot overwrite each other. This is NOT a filesystem
    sandbox or an atomic directory rename. SIGKILL can leave .incomplete behind.
    Validators refuse incomplete deliveries; no recovery deletes unknown files.
    """
    destination = Path(os.path.abspath(destination))
    reject_symlinks(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.mkdir()
    except FileExistsError as exc:
        raise SkillError("exists", "Output exists; choose a new directory", str(destination)) from exc
    owner = destination.stat()
    marker = destination / ".incomplete"
    try:
        write_new(marker, b"Incomplete OdenMap skill output. Do not open or deliver.\n")
        yield destination
        marker.unlink()
    except BaseException:
        try:
            current = destination.lstat()
            if (current.st_ino, current.st_dev) == (owner.st_ino, owner.st_dev):
                shutil.rmtree(destination)
        except OSError:
            pass
        raise


def file_digest(path: Path, limit: int = 8 * 1024**3) -> str:
    """Bounded streaming digest for snapshots; never allocates the declared limit."""
    reject_symlinks(path)
    with path.open("rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, "Not a bounded regular file", str(path))
        h = hashlib.sha256()
        total = 0
        while True:
            part = stream.read(1024 * 1024)
            if not part:
                break
            total += len(part)
            require(total <= limit, "File grew beyond hashing budget", str(path), "limit")
            h.update(part)
        return h.hexdigest()
