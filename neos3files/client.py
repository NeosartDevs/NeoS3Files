"""
Low-level async S3 client
"""

import asyncio
from typing import Dict, Any, AsyncGenerator, List
import logging

import aioboto3
import botocore.config
from botocore.exceptions import ClientError

from .models import S3Config
from .exceptions import (
    S3Error,
    S3ConnectionError,
    S3FileNotFoundError,
    S3BucketNotFoundError,
    S3PermissionError,
)

logger = logging.getLogger(__name__)


class S3Client:
    """
    Async S3 client with connection pooling.

    Low-level client for S3 operations using aioboto3. Provides async methods
    for all basic S3 operations with automatic connection pooling and error handling.

    Args:
        config: S3 configuration object with connection parameters.

    Example:
        >>> config = S3Config(
        ...     endpoint_url="https://s3.example.com",
        ...     bucket="my-bucket",
        ...     access_key="key",
        ...     secret_key="secret"
        ... )
        >>> async with S3Client(config) as client:
        ...     info = await client.head_object("file.txt")
    """

    def __init__(self, config: S3Config):
        self.config = config
        self.session = aioboto3.Session()
        self._client = None
        self._lock = asyncio.Lock()

    async def _get_client(self):
        """
        Get or create S3 client with connection pooling.

        Creates a new client on first call and reuses it for subsequent calls.
        Thread-safe with asyncio.Lock.

        Returns:
            Configured aioboto3 S3 client instance.

        Raises:
            S3ConnectionError: If client creation fails.
        """

        if self._client is not None:
            return self._client

        async with self._lock:
            if self._client is None:
                try:
                    self._client = self.session.client(
                        "s3",
                        endpoint_url=self.config.endpoint_url,
                        aws_access_key_id=self.config.access_key,
                        aws_secret_access_key=self.config.secret_key,
                        region_name=self.config.region or "us-east-1",
                        verify=self.config.verify_ssl,
                        config=botocore.config.Config(
                            max_pool_connections=self.config.max_pool_connections,
                            connect_timeout=self.config.timeout,
                            read_timeout=self.config.timeout,
                            retries={"max_attempts": 3, "mode": "adaptive"},
                            request_checksum_calculation="when_required",
                            response_checksum_validation="when_required",
                        ),
                    )

                    self._client = await self._client.__aenter__()

                except Exception as e:
                    raise S3ConnectionError(
                        f"Failed to create S3 client: {e}", original_error=e
                    )
            return self._client

    async def close(self):
        """
        Close S3 client and release resources.

        Safely closes the underlying boto3 client connection.
        Can be called multiple times safely.
        """
        async with self._lock:
            if self._client:
                try:
                    await self._client.close()
                except AttributeError:
                    try:
                        await self._client.__aexit__(None, None, None)
                    except:  # noqa: E722
                        pass
                finally:
                    self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _handle_client_error(self, error: ClientError, operation: str, key: str = None):
        """
        Handle boto3 client errors and convert to custom exceptions.

        Args:
            error: Botocore ClientError instance.
            operation: Name of the operation that failed.
            key: Optional S3 object key for error context.

        Raises:
            S3BucketNotFoundError: If bucket doesn't exist.
            S3FileNotFoundError: If file/key doesn't exist.
            S3PermissionError: If access is denied.
            S3Error: For other S3 errors.
        """
        error_code = error.response.get("Error", {}).get("Code", "Unknown")

        if error_code == "NoSuchBucket":
            raise S3BucketNotFoundError(self.config.bucket)
        elif error_code == "NoSuchKey":
            if key:
                raise S3FileNotFoundError(key)
            else:
                raise S3FileNotFoundError("Unknown key")
        elif error_code in ("AccessDenied", "403"):
            raise S3PermissionError(f"Permission denied for operation: {operation}")
        elif error_code == "404":
            raise S3FileNotFoundError(key or "Unknown key")
        else:
            raise S3Error(
                f"S3 operation '{operation}' failed: {error_code} - {error}",
                original_error=error,
            )

    async def head_object(self, key: str) -> Dict[str, Any]:
        """
        Get object metadata without downloading the object.

        Args:
            key: S3 object key (path).

        Returns:
            Dictionary with object metadata including:
            - ContentLength: File size in bytes
            - LastModified: Last modification timestamp
            - ETag: Object ETag
            - StorageClass: Storage class
            - ContentType: MIME type
            - Metadata: Custom metadata dictionary

        Raises:
            S3FileNotFoundError: If object doesn't exist.
            S3Error: For other errors.

        Example:
            >>> info = await client.head_object("folder/file.txt")
            >>> print(info['ContentLength'])
            1024
        """
        try:
            client = await self._get_client()
            response = await client.head_object(Bucket=self.config.bucket, Key=key)
            return response
        except ClientError as e:
            self._handle_client_error(e, "head_object", key)
        except Exception as e:
            raise S3Error(f"Failed to head object {key}: {e}", original_error=e)

    async def list_objects(
        self, prefix: str = "", delimiter: str = "", max_keys: int = 1000
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        List objects in bucket with pagination support.

        Args:
            prefix: Filter objects by key prefix. Default is empty (all objects).
            delimiter: Character to group keys. Use "/" for directory-like structure.
            max_keys: Maximum number of keys per page. Default is 1000.

        Yields:
            Dictionary for each object containing:
            - Key: Object key (path)
            - Size: Object size in bytes
            - LastModified: Last modification timestamp
            - ETag: Object ETag
            - StorageClass: Storage class

        Raises:
            S3Error: If listing fails.

        Example:
            >>> async for obj in client.list_objects(prefix="photos/"):
            ...     print(obj['Key'], obj['Size'])
        """
        client = await self._get_client()

        paginator = client.get_paginator("list_objects_v2")

        page_iterator = paginator.paginate(
            Bucket=self.config.bucket,
            Prefix=prefix,
            Delimiter=delimiter,
            MaxKeys=max_keys,
        )

        try:
            async for page in page_iterator:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        yield obj
        except Exception as e:
            raise S3Error(f"Failed to list objects: {e}", original_error=e)

    async def upload_part(
        self, key: str, upload_id: str, part_number: int, body: bytes
    ) -> Dict[str, Any]:
        """
        Upload a part in multipart upload.

        Args:
            key: S3 object key (path).
            upload_id: Multipart upload ID from create_multipart_upload.
            part_number: Part number (1-indexed).
            body: Part data as bytes.

        Returns:
            Dictionary with 'ETag' key for the uploaded part.

        Raises:
            S3Error: If upload fails.

        Note:
            Part numbers must be between 1 and 10000. Parts can be uploaded
            in any order, but must be completed in order.
        """
        try:
            client = await self._get_client()
            return await client.upload_part(
                Bucket=self.config.bucket,
                Key=key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=body,
            )
        except ClientError as e:
            self._handle_client_error(e, "upload_part", key)
        except Exception as e:
            raise S3Error(
                f"Failed to upload part {part_number} for {key}: {e}", original_error=e
            )

    async def download_fileobj(self, key: str, fileobj) -> None:
        """
        Download object to file-like object.

        Args:
            key: S3 object key (path) to download.
            fileobj: File-like object opened in binary write mode (e.g., file handle).

        Raises:
            S3FileNotFoundError: If object doesn't exist.
            S3Error: For other errors.

        Example:
            >>> async with aiofiles.open("local_file.txt", "wb") as f:
            ...     await client.download_fileobj("remote/file.txt", f)
        """
        try:
            client = await self._get_client()
            await client.download_fileobj(
                Bucket=self.config.bucket, Key=key, Fileobj=fileobj
            )
        except ClientError as e:
            self._handle_client_error(e, "download_fileobj", key)
        except Exception as e:
            raise S3Error(f"Failed to download {key}: {e}", original_error=e)

    async def put_object(
        self,
        key: str,
        body: bytes,
        content_type: str = None,
        metadata: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Upload object in single operation.

        Suitable for small files. For large files, use multipart upload.

        Args:
            key: S3 object key (path) where to upload.
            body: Object content as bytes.
            content_type: Optional MIME type (e.g., "text/plain", "image/jpeg").
            metadata: Optional dictionary of custom metadata (string keys and values).

        Returns:
            Dictionary with 'ETag' key for the uploaded object.

        Raises:
            S3Error: If upload fails.

        Example:
            >>> data = b"Hello, World!"
            >>> result = await client.put_object(
            ...     "file.txt",
            ...     data,
            ...     content_type="text/plain",
            ...     metadata={"author": "user"}
            ... )
        """
        try:
            client = await self._get_client()
            params = {"Bucket": self.config.bucket, "Key": key, "Body": body}
            if content_type:
                params["ContentType"] = content_type
            if metadata:
                params["Metadata"] = metadata

            return await client.put_object(**params)
        except ClientError as e:
            self._handle_client_error(e, "put_object", key)
        except Exception as e:
            raise S3Error(f"Failed to put object {key}: {e}", original_error=e)

    async def delete_object(self, key: str) -> Dict[str, Any]:
        """
        Delete object from S3.

        Args:
            key: S3 object key (path) to delete.

        Returns:
            Empty dictionary on success.

        Raises:
            S3Error: If deletion fails.

        Note:
            Deleting a non-existent object does not raise an error.
        """
        try:
            client = await self._get_client()
            return await client.delete_object(Bucket=self.config.bucket, Key=key)
        except ClientError as e:
            self._handle_client_error(e, "delete_object", key)
        except Exception as e:
            raise S3Error(f"Failed to delete object {key}: {e}", original_error=e)

    async def copy_object(
        self, source_key: str, destination_key: str
    ) -> Dict[str, Any]:
        """
        Copy object within the same bucket.

        Args:
            source_key: Source object key (path).
            destination_key: Destination object key (path).

        Returns:
            Dictionary with copy operation result including 'ETag'.

        Raises:
            S3FileNotFoundError: If source object doesn't exist.
            S3Error: For other errors.

        Example:
            >>> await client.copy_object("old/path.txt", "new/path.txt")
        """
        try:
            client = await self._get_client()
            return await client.copy_object(
                Bucket=self.config.bucket,
                CopySource={"Bucket": self.config.bucket, "Key": source_key},
                Key=destination_key,
            )
        except ClientError as e:
            self._handle_client_error(e, "copy_object", source_key)
        except Exception as e:
            raise S3Error(
                f"Failed to copy {source_key} to {destination_key}: {e}",
                original_error=e,
            )

    async def create_multipart_upload(
        self, key: str, content_type: str = None, metadata: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Initialize a multipart upload.

        Args:
            key: S3 object key (path) for the upload.
            content_type: Optional MIME type.
            metadata: Optional dictionary of custom metadata.

        Returns:
            Dictionary with 'UploadId' key required for subsequent part uploads.

        Raises:
            S3Error: If initialization fails.

        Note:
            After creating, upload parts using upload_part, then complete
            with complete_multipart_upload or abort with abort_multipart_upload.
        """
        try:
            client = await self._get_client()
            params = {"Bucket": self.config.bucket, "Key": key}
            if content_type:
                params["ContentType"] = content_type
            if metadata:
                params["Metadata"] = metadata

            return await client.create_multipart_upload(**params)
        except Exception as e:
            raise S3Error(
                f"Failed to create multipart upload for {key}: {e}", original_error=e
            )

    async def complete_multipart_upload(
        self, key: str, upload_id: str, parts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Complete a multipart upload.

        Args:
            key: S3 object key (path).
            upload_id: Upload ID from create_multipart_upload.
            parts: List of part dictionaries, each with 'PartNumber' and 'ETag'.
                   Parts must be sorted by PartNumber.

        Returns:
            Dictionary with completed upload information including 'ETag'.

        Raises:
            S3Error: If completion fails.

        Example:
            >>> parts = [
            ...     {"PartNumber": 1, "ETag": "etag1"},
            ...     {"PartNumber": 2, "ETag": "etag2"}
            ... ]
            >>> result = await client.complete_multipart_upload("file.txt", upload_id, parts)
        """
        try:
            client = await self._get_client()
            return await client.complete_multipart_upload(
                Bucket=self.config.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except Exception as e:
            raise S3Error(
                f"Failed to complete multipart upload for {key}: {e}", original_error=e
            )

    async def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        """
        Abort an incomplete multipart upload.

        Cleans up all uploaded parts and frees storage space.

        Args:
            key: S3 object key (path).
            upload_id: Upload ID from create_multipart_upload.

        Raises:
            S3Error: If abort fails.

        Note:
            Use this to clean up incomplete uploads or on upload errors.
        """
        try:
            client = await self._get_client()
            await client.abort_multipart_upload(
                Bucket=self.config.bucket, Key=key, UploadId=upload_id
            )
        except Exception as e:
            raise S3Error(
                f"Failed to abort multipart upload for {key}: {e}", original_error=e
            )
