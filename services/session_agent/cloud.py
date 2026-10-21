"""The session's object storage behind the small interface it uses.

The turn audio and the clip store write through a Bucket (clips/store.Bucket): a name
inside one bucket or container. BlobBucket is that over aloai_blobs.Blobs, so it is the
same code on Cloud Storage and on Blob Storage. The documents (aloai_store) and the events
(aloai_events) come from the shared clients too, chosen by CLOUD (aloai_env).
"""

from aloai_blobs import Blobs, blob_uri


class BlobBucket:
    """A bucket (gcp) or container (azure) of Blobs, by object name."""

    def __init__(self, blobs: Blobs, cloud: str, container: str) -> None:
        self._blobs = blobs
        self._cloud = cloud
        self._container = container

    def _uri(self, name: str) -> str:
        return blob_uri(self._cloud, self._container, name)

    def exists(self, name: str) -> bool:
        return self._blobs.exists(self._uri(name))

    def upload_if_absent(self, name: str, data: bytes, content_type: str) -> bool:
        return self._blobs.write_if_absent(self._uri(name), data, content_type)

    def upload(self, name: str, data: bytes, content_type: str) -> None:
        self._blobs.write(self._uri(name), data, content_type)
