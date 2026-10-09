from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path


class StorageBackend(ABC):
    @abstractmethod
    def write(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalFileBackend(StorageBackend):
    """Stores files under base_path/key.

    Legacy keys that are absolute paths (stored before relative keys were
    introduced) resolve correctly because Path(absolute) / absolute == absolute.
    """

    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)

    def write(self, key: str, data: bytes) -> None:
        path = self._base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return (self._base / key).read_bytes()

    def delete(self, key: str) -> None:
        p = self._base / key
        if p.exists():
            p.unlink()


class MinioBackend(StorageBackend):
    """S3-compatible object storage via MinIO.

    key format: {patient_id}/{doc_id}.enc  (relative, no leading slash)
    """

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        secure: bool = True,
    ) -> None:
        from minio import Minio

        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def write(self, key: str, data: bytes) -> None:
        import io

        self._client.put_object(self._bucket, key, io.BytesIO(data), length=len(data))

    def read(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, key: str) -> None:
        self._client.remove_object(self._bucket, key)


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    from app.core.config import settings

    if settings.storage_backend == "minio":
        return MinioBackend(
            endpoint=settings.minio_endpoint,
            bucket=settings.minio_bucket,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return LocalFileBackend(settings.document_storage_path)
