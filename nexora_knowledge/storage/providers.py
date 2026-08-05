from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from io import BytesIO
import os
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from ..config import Settings, get_settings
from ..models.enums import StorageProviderType


class AbstractStorageProvider(ABC):
    """Backend-neutral byte storage contract."""

    provider_type: StorageProviderType

    @abstractmethod
    def store(self, stream: BinaryIO, storage_path: str) -> int:
        """Persist bytes from the current stream position and return their size."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Delete an object if it exists."""

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """Return whether an object exists."""

    @abstractmethod
    def open(self, storage_path: str) -> BinaryIO:
        """Open an object for bounded, read-only streaming."""

    @abstractmethod
    def size(self, storage_path: str) -> int:
        """Return the current object size in bytes."""


class LocalStorageProvider(AbstractStorageProvider):
    provider_type = StorageProviderType.LOCAL

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        relative = PurePosixPath(storage_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Storage path must be a safe relative path")
        candidate = self.root.joinpath(*relative.parts).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Storage path escapes the configured root") from exc
        return candidate

    def store(self, stream: BinaryIO, storage_path: str) -> int:
        target = self._resolve(storage_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"Storage object already exists: {storage_path}")
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        size = 0
        try:
            with temporary.open("xb") as destination:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
                    size += len(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return size

    def delete(self, storage_path: str) -> None:
        self._resolve(storage_path).unlink(missing_ok=True)

    def exists(self, storage_path: str) -> bool:
        return self._resolve(storage_path).is_file()

    def open(self, storage_path: str) -> BinaryIO:
        return self._resolve(storage_path).open("rb")

    def size(self, storage_path: str) -> int:
        return self._resolve(storage_path).stat().st_size


class NullStorageProvider(AbstractStorageProvider):
    """In-memory provider for deterministic tests."""

    provider_type = StorageProviderType.NULL

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    @staticmethod
    def _validate_path(storage_path: str) -> str:
        relative = PurePosixPath(storage_path)
        if (
            not storage_path.strip()
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            raise ValueError("Storage path must be a safe relative path")
        return relative.as_posix()

    def store(self, stream: BinaryIO, storage_path: str) -> int:
        storage_path = self._validate_path(storage_path)
        if storage_path in self.objects:
            raise FileExistsError(f"Storage object already exists: {storage_path}")
        content = stream.read()
        self.objects[storage_path] = content
        return len(content)

    def delete(self, storage_path: str) -> None:
        storage_path = self._validate_path(storage_path)
        self.objects.pop(storage_path, None)

    def exists(self, storage_path: str) -> bool:
        storage_path = self._validate_path(storage_path)
        return storage_path in self.objects

    def open(self, storage_path: str) -> BytesIO:
        storage_path = self._validate_path(storage_path)
        return BytesIO(self.objects[storage_path])

    def size(self, storage_path: str) -> int:
        storage_path = self._validate_path(storage_path)
        return len(self.objects[storage_path])


def build_storage_provider(
    provider_type: StorageProviderType | str | None = None,
    *,
    settings: Settings | None = None,
) -> AbstractStorageProvider:
    resolved_settings = settings or get_settings()
    raw_type = (
        provider_type
        if provider_type is not None
        else resolved_settings.default_storage_provider
    )
    try:
        normalized = StorageProviderType(str(raw_type).strip().casefold())
    except ValueError as exc:
        raise ValueError("Unsupported storage provider configuration") from exc
    if normalized == StorageProviderType.LOCAL:
        return LocalStorageProvider(resolved_settings.local_storage_root)
    if normalized == StorageProviderType.NULL:
        return NullStorageProvider()
    raise ValueError(
        f"Storage provider '{normalized.value}' is not implemented"
    )


@lru_cache
def get_default_storage_provider() -> AbstractStorageProvider:
    return build_storage_provider()


__all__ = [
    "AbstractStorageProvider",
    "LocalStorageProvider",
    "NullStorageProvider",
    "build_storage_provider",
    "get_default_storage_provider",
]
