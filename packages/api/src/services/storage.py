# This project was developed with assistance from AI tools.
"""S3-compatible object storage service backed by S4.

Uses boto3 synchronous client run in a thread-pool executor for async
compatibility. The module exposes a singleton initialised at app startup
via ``init_storage_service()``.
"""

import asyncio
import logging
import os
from functools import partial

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from ..core.config import Settings

logger = logging.getLogger(__name__)


class StorageService:
    """Thin wrapper around a boto3 S3 client."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ):
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(
                signature_version="s3v4",
                s3={
                    "addressing_style": "path",
                    "use_accelerate_endpoint": False,
                },
            ),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the bucket if it doesn't already exist (dev convenience)."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            logger.info("Creating S3 bucket: %s", self._bucket)
            self._client.create_bucket(Bucket=self._bucket)

    async def upload_file(
        self,
        file_data: bytes,
        object_key: str,
        content_type: str,
    ) -> str:
        """Upload bytes to S3 and return the object key."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(
                self._client.put_object,
                Bucket=self._bucket,
                Key=object_key,
                Body=file_data,
                ContentType=content_type,
            ),
        )
        return object_key

    async def download_file(self, object_key: str) -> bytes:
        """Download file bytes from S3."""
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            partial(self._client.get_object, Bucket=self._bucket, Key=object_key),
        )
        return response["Body"].read()

    async def get_download_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Return a presigned GET URL for the given object key."""
        loop = asyncio.get_running_loop()
        url: str = await loop.run_in_executor(
            None,
            partial(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self._bucket, "Key": object_key},
                ExpiresIn=expires_in,
            ),
        )
        return url

    @staticmethod
    def build_object_key(application_id: int, document_id: int, filename: str) -> str:
        """Build the S3 object key: {application_id}/{document_id}/{filename}.

        Strips path components from filename to prevent path traversal attacks.
        """
        safe_name = os.path.basename(filename) or f"doc-{document_id}"
        return f"{application_id}/{document_id}/{safe_name}"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: StorageService | None = None


def init_storage_service(cfg: Settings) -> StorageService:
    """Initialise the singleton (called once from app lifespan)."""
    global _service  # noqa: PLW0603
    _service = StorageService(
        endpoint=cfg.S3_ENDPOINT,
        access_key=cfg.S3_ACCESS_KEY,
        secret_key=cfg.S3_SECRET_KEY,
        bucket=cfg.S3_BUCKET,
        region=cfg.S3_REGION,
    )
    logger.info("StorageService initialised (bucket=%s)", cfg.S3_BUCKET)
    return _service


def get_storage_service() -> StorageService:
    """Return the initialised StorageService singleton."""
    if _service is None:
        raise RuntimeError("StorageService not initialised -- call init_storage_service() first")
    return _service
