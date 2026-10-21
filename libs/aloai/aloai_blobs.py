"""Audio, clips and book files in object storage (PRD 3, 5.1, 9).

A blob is named by a URI: gs://bucket/name on Google Cloud, az://container/name on Azure
(the contracts accept both). Blobs is what the services use; GcsBlobs and AzureBlobs talk
to the clouds and MemoryBlobs stands in for them in tests. Each cloud's SDK is imported
only when its client is built. A blob that is not there is a BlobNotFound on every
backend, whatever the SDK raises. Names are used as given: a clip key such as
"tunde~%CB%88tund%C9%9B.mp3" is stored under exactly that name.
"""

from typing import Protocol

from aloai_env import Config, require_setting

SCHEMES = ("gs", "az")
SCHEME_OF = {"gcp": "gs", "azure": "az"}  # the URI scheme of each cloud's storage


class BlobNotFound(LookupError):
    pass


class Blobs(Protocol):
    def read(self, uri: str) -> bytes: ...

    def write(self, uri: str, data: bytes, content_type: str | None = None) -> None: ...

    def write_if_absent(self, uri: str, data: bytes, content_type: str | None = None) -> bool:
        """Write only if the blob does not exist. True if this call wrote it."""
        ...

    def exists(self, uri: str) -> bool: ...


def split_uri(uri: str) -> tuple[str, str, str]:
    """(scheme, bucket or container, name) of a blob URI; ValueError if it is not one."""
    scheme, separator, rest = uri.partition("://")
    container, slash, name = rest.partition("/")
    if scheme not in SCHEMES or not separator or not container or not slash or not name:
        raise ValueError(f"not a blob URI (gs://bucket/name or az://container/name): {uri!r}")
    return scheme, container, name


def blob_uri(cloud: str, container: str, name: str) -> str:
    """The URI of a blob on this cloud: gs:// for gcp, az:// for azure."""
    scheme = SCHEME_OF.get(cloud)
    if scheme is None:
        raise ValueError(f"unknown cloud {cloud!r}")
    return f"{scheme}://{container}/{name}"


class MemoryBlobs:
    def __init__(self, blobs: dict[str, bytes] | None = None) -> None:
        self.blobs: dict[str, bytes] = {} if blobs is None else blobs
        self.content_types: dict[str, str | None] = {}

    def read(self, uri: str) -> bytes:
        split_uri(uri)
        try:
            return self.blobs[uri]
        except KeyError:
            raise BlobNotFound(uri) from None

    def write(self, uri: str, data: bytes, content_type: str | None = None) -> None:
        split_uri(uri)
        self.blobs[uri] = bytes(data)
        self.content_types[uri] = content_type

    def write_if_absent(self, uri: str, data: bytes, content_type: str | None = None) -> bool:
        if uri in self.blobs:
            return False
        self.write(uri, data, content_type)
        return True

    def exists(self, uri: str) -> bool:
        split_uri(uri)
        return uri in self.blobs


def _only(uri: str, scheme: str) -> tuple[str, str]:
    found, container, name = split_uri(uri)
    if found != scheme:
        raise ValueError(f"expected a {scheme}:// URI, got {uri!r}")
    return container, name


class GcsBlobs:
    """Cloud Storage, or its emulator when STORAGE_EMULATOR_HOST is set."""

    def __init__(self, client) -> None:  # a google.cloud.storage.Client
        self._client = client

    def _blob(self, uri: str):
        bucket, name = _only(uri, "gs")
        return self._client.bucket(bucket).blob(name)

    def read(self, uri: str) -> bytes:
        from google.api_core.exceptions import NotFound

        try:
            return self._blob(uri).download_as_bytes()
        except NotFound:
            raise BlobNotFound(uri) from None

    def write(self, uri: str, data: bytes, content_type: str | None = None) -> None:
        self._blob(uri).upload_from_string(data, content_type=content_type)

    def write_if_absent(self, uri: str, data: bytes, content_type: str | None = None) -> bool:
        from google.api_core.exceptions import PreconditionFailed

        try:
            self._blob(uri).upload_from_string(
                data, content_type=content_type, if_generation_match=0
            )
        except PreconditionFailed:
            return False
        return True

    def exists(self, uri: str) -> bool:
        return self._blob(uri).exists()


class AzureBlobs:
    """Blob Storage, or Azurite when a connection string is given."""

    def __init__(self, service) -> None:  # an azure.storage.blob.BlobServiceClient
        self._service = service

    def _blob(self, uri: str):
        container, name = _only(uri, "az")
        return self._service.get_blob_client(container, name)

    def read(self, uri: str) -> bytes:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._blob(uri).download_blob().readall()
        except ResourceNotFoundError:
            raise BlobNotFound(uri) from None

    def write(self, uri: str, data: bytes, content_type: str | None = None) -> None:
        self._blob(uri).upload_blob(data, overwrite=True, content_settings=_settings(content_type))

    def write_if_absent(self, uri: str, data: bytes, content_type: str | None = None) -> bool:
        from azure.core.exceptions import ResourceExistsError

        try:
            self._blob(uri).upload_blob(
                data, overwrite=False, content_settings=_settings(content_type)
            )
        except ResourceExistsError:
            return False
        return True

    def exists(self, uri: str) -> bool:
        return self._blob(uri).exists()


def _settings(content_type: str | None):
    if content_type is None:
        return None
    from azure.storage.blob import ContentSettings

    return ContentSettings(content_type=content_type)


def open_blobs(config: Config) -> Blobs:  # pragma: no cover - builds a real client
    """The storage client for this cloud. Google picks up Application Default Credentials
    (or STORAGE_EMULATOR_HOST); Azure uses the managed identity, or Azurite locally."""
    if config.cloud == "gcp":
        import os

        from google.cloud import storage

        if os.environ.get("STORAGE_EMULATOR_HOST"):  # the emulator takes no credentials
            from google.auth.credentials import AnonymousCredentials

            return GcsBlobs(
                storage.Client(project=config.project, credentials=AnonymousCredentials())
            )
        return GcsBlobs(storage.Client(project=config.project))
    from azure.storage.blob import BlobServiceClient

    if config.storage_connection_string:
        service = BlobServiceClient.from_connection_string(config.storage_connection_string)
        return AzureBlobs(service)
    from azure.identity import DefaultAzureCredential

    account = require_setting(config.storage_account, "AZURE_STORAGE_ACCOUNT")
    return AzureBlobs(
        BlobServiceClient(f"https://{account}.blob.core.windows.net", DefaultAzureCredential())
    )
