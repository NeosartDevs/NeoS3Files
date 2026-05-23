"""
High-level async S3 manager
"""

import os
import mimetypes
import asyncio
from typing import Optional, List, Dict, AsyncGenerator, Callable
import logging

import aiofiles

from .models import S3Config, FileInfo, UploadProgress, UsageStats, StorageClass
from .client import S3Client
from .exceptions import S3UploadError, S3DownloadError, S3FileNotFoundError

logger = logging.getLogger(__name__)


class S3Manager:
    """
    High-level async S3 manager with automatic multipart uploads.

    Provides convenient methods for common S3 operations with automatic
    handling of large files (multipart uploads), progress tracking, and
    error handling.

    Args:
        config: S3 configuration object.
        chunk_size: Size of chunks for multipart uploads in bytes. Default is 50MB.
        max_concurrent_uploads: Maximum number of concurrent part uploads. Default is 5.

    Example:
        >>> config = S3Config(...)
        >>> async with S3Manager(config) as manager:
        ...     file_info = await manager.upload_file("local.txt", "remote.txt")
        ...     await manager.download_file("remote.txt", "downloaded.txt")
    """

    DEFAULT_CHUNK_SIZE = 50 * 1024 * 1024  # 50MB
    DEFAULT_CONTENT_TYPE = "binary/octet-stream"

    def __init__(
        self,
        config: S3Config,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_concurrent_uploads: int = 5,
    ):
        self.config = config
        self.chunk_size = chunk_size
        self.max_concurrent_uploads = max_concurrent_uploads
        self._client = S3Client(config)
        self._semaphore = asyncio.Semaphore(max_concurrent_uploads)

    @classmethod
    def from_credentials(
        cls,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: Optional[str] = None,
        **kwargs,
    ) -> "S3Manager":
        """
        Create manager from credentials.

        Convenience method to create S3Manager without creating S3Config explicitly.

        Args:
            endpoint_url: S3 endpoint URL.
            bucket: Bucket name.
            access_key: AWS access key ID.
            secret_key: AWS secret access key.
            region: Optional AWS region. Defaults to us-east-1.
            **kwargs: Additional arguments passed to S3Manager constructor
                     (chunk_size, max_concurrent_uploads).

        Returns:
            Configured S3Manager instance.

        Example:
            >>> manager = await S3Manager.from_credentials(
            ...     "https://s3.example.com",
            ...     "my-bucket",
            ...     "access-key",
            ...     "secret-key",
            ...     chunk_size=10*1024*1024
            ... )
        """
        config = S3Config(
            endpoint_url=endpoint_url,
            bucket=bucket,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
        )
        return cls(config, **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """
        Close manager and release resources.

        Closes the underlying S3Client connection.
        """
        await self._client.close()

    async def exists(self, key: str) -> bool:
        """
        Check if file exists in S3.

        Args:
            key: S3 object key (path) to check.

        Returns:
            True if file exists, False otherwise.

        Raises:
            S3Error: For connection or permission errors (not for missing files).

        Example:
            >>> if await manager.exists("file.txt"):
            ...     print("File exists")
        """
        try:
            await self._client.head_object(key)
            return True
        except S3FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking existence of {key}: {e}")
            raise

    async def get_file_info(self, key: str) -> FileInfo:
        """
        Get detailed file information.

        Args:
            key: S3 object key (path).

        Returns:
            FileInfo object with file metadata.

        Raises:
            S3FileNotFoundError: If file doesn't exist.
            S3Error: For other errors.

        Example:
            >>> info = await manager.get_file_info("folder/file.txt")
            >>> print(f"Size: {info.size_mb} MB")
            >>> print(f"Type: {info.content_type}")
        """
        try:
            response = await self._client.head_object(key)

            return FileInfo(
                key=key,
                size=response["ContentLength"],
                last_modified=response["LastModified"],
                etag=response["ETag"].strip('"'),
                storage_class=StorageClass(response.get("StorageClass", "STANDARD")),
                content_type=response.get("ContentType"),
                metadata=response.get("Metadata", {}),
            )
        except Exception as e:
            logger.error(f"Error getting info for {key}: {e}")
            raise

    async def upload_file(
        self,
        local_path: str,
        s3_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None,
    ) -> FileInfo:
        """
        Upload file with automatic multipart handling and progress tracking.

        Automatically uses single-part upload for small files and multipart
        upload for large files (larger than chunk_size).

        Args:
            local_path: Path to local file to upload.
            s3_key: S3 object key (path) where to upload.
            content_type: Optional MIME type. Auto-detected from filename if not provided.
            metadata: Optional dictionary of custom metadata.
            progress_callback: Optional callback function called with UploadProgress
                             during upload. Called for each completed part.

        Returns:
            FileInfo object for the uploaded file.

        Raises:
            FileNotFoundError: If local file doesn't exist.
            S3UploadError: If upload fails.

        Example:
            >>> def on_progress(progress):
            ...     print(f"Uploaded {progress.progress_percent:.1f}%")
            >>>
            >>> info = await manager.upload_file(
            ...     "large_file.zip",
            ...     "uploads/file.zip",
            ...     content_type="application/zip",
            ...     metadata={"version": "1.0"},
            ...     progress_callback=on_progress
            ... )
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"File not found: {local_path}")

        file_size = os.path.getsize(local_path)
        filename = os.path.basename(local_path)

        if content_type is None:
            content_type, _ = mimetypes.guess_type(filename)
            if content_type is None:
                content_type = self.DEFAULT_CONTENT_TYPE

        logger.info(
            f"Uploading {filename} ({file_size / (1024**2):.2f} MB) to {s3_key}"
        )

        if file_size <= self.chunk_size:
            return await self._upload_single(
                local_path, s3_key, content_type, metadata, progress_callback
            )

        return await self._upload_multipart(
            local_path, s3_key, content_type, metadata, progress_callback
        )

    async def _upload_single(
        self,
        local_path: str,
        s3_key: str,
        content_type: str,
        metadata: Dict[str, str],
        progress_callback: Optional[Callable[[UploadProgress], None]],
    ) -> FileInfo:
        """
        Upload file in single operation (internal method).

        Used for files smaller than chunk_size.
        """
        try:
            async with aiofiles.open(local_path, "rb") as f:
                content = await f.read()

            await self._client.put_object(
                key=s3_key, body=content, content_type=content_type, metadata=metadata
            )

            if progress_callback:
                progress = UploadProgress(
                    key=s3_key,
                    total_size=len(content),
                    uploaded_size=len(content),
                    completed_parts=1,
                    total_parts=1,
                )
                progress_callback(progress)

            return await self.get_file_info(s3_key)

        except Exception as e:
            raise S3UploadError(key=s3_key, message=str(e), original_error=e)

    async def _upload_multipart(
        self,
        local_path: str,
        s3_key: str,
        content_type: str,
        metadata: Dict[str, str],
        progress_callback: Optional[Callable[[UploadProgress], None]],
    ) -> FileInfo:
        """
        Upload file using multipart upload (internal method).

        Used for files larger than chunk_size. Automatically handles
        part uploads, error recovery, and cleanup.
        """
        upload_id = None
        parts = []

        try:
            file_size = os.path.getsize(local_path)
            total_parts = (file_size + self.chunk_size - 1) // self.chunk_size

            create_response = await self._client.create_multipart_upload(
                key=s3_key, content_type=content_type, metadata=metadata
            )
            upload_id = create_response["UploadId"]

            tasks = []
            async with aiofiles.open(local_path, "rb") as f:
                for part_number in range(1, total_parts + 1):
                    task = asyncio.create_task(
                        self._upload_part_with_semaphore(
                            f,
                            s3_key,
                            upload_id,
                            part_number,
                            file_size,
                            progress_callback,
                        )
                    )
                    tasks.append(task)

                parts_results = await asyncio.gather(*tasks)

            parts_results.sort(key=lambda x: x["PartNumber"])
            parts = [
                {"PartNumber": p["PartNumber"], "ETag": p["ETag"]}
                for p in parts_results
            ]

            await self._client.complete_multipart_upload(
                key=s3_key, upload_id=upload_id, parts=parts
            )

            logger.info(f"Upload completed: {s3_key}")
            return await self.get_file_info(s3_key)

        except Exception as e:
            if upload_id:
                try:
                    await self._client.abort_multipart_upload(s3_key, upload_id)
                    logger.warning(f"Upload aborted: {s3_key}")
                except Exception as abort_error:
                    logger.error(f"Error aborting upload: {abort_error}")

            raise S3UploadError(key=s3_key, message=str(e), original_error=e)

    async def _upload_part_with_semaphore(
        self,
        file_handle,
        s3_key: str,
        upload_id: str,
        part_number: int,
        file_size: int,
        progress_callback: Optional[Callable[[UploadProgress], None]],
    ):
        """
        Upload single part with semaphore control (internal method).

        Limits concurrent part uploads using semaphore.
        """
        async with self._semaphore:
            offset = (part_number - 1) * self.chunk_size
            chunk_size = min(self.chunk_size, file_size - offset)

            await file_handle.seek(offset)
            chunk = await file_handle.read(chunk_size)

            response = await self._client.upload_part(
                key=s3_key, upload_id=upload_id, part_number=part_number, body=chunk
            )

            if progress_callback:
                progress = UploadProgress(
                    key=s3_key,
                    total_size=file_size,
                    uploaded_size=offset + len(chunk),
                    completed_parts=part_number,
                    total_parts=(file_size + self.chunk_size - 1) // self.chunk_size,
                )
                progress_callback(progress)

            return {"PartNumber": part_number, "ETag": response["ETag"]}

    async def download_file(
        self,
        s3_key: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """
        Download file from S3 to local filesystem.

        Args:
            s3_key: S3 object key (path) to download.
            local_path: Local file path where to save the file.
            progress_callback: Optional callback function called with (downloaded_bytes, total_bytes)
                             during download. Note: Currently not implemented for downloads.

        Returns:
            Local file path (same as local_path).

        Raises:
            S3FileNotFoundError: If file doesn't exist in S3.
            S3DownloadError: If download fails.

        Example:
            >>> await manager.download_file("remote/file.txt", "local/file.txt")
            'local/file.txt'
        """
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        try:
            file_info = await self.get_file_info(s3_key)

            logger.info(
                f"Downloading {s3_key} ({file_info.size_mb:.2f} MB) to {local_path}"
            )

            async with aiofiles.open(local_path, "wb") as f:
                await self._client.download_fileobj(s3_key, f)

            logger.info(f"Download completed: {local_path}")
            return local_path

        except Exception as e:
            raise S3DownloadError(key=s3_key, message=str(e), original_error=e)

    async def list_files(
        self, prefix: str = "", recursive: bool = True, limit: Optional[int] = None
    ) -> AsyncGenerator[FileInfo, None]:
        """
        List files in bucket with optional filtering.

        Args:
            prefix: Filter files by key prefix. Default is empty (all files).
            recursive: If False, treats "/" as directory separator. Default is True.
            limit: Maximum number of files to return. None means no limit.

        Yields:
            FileInfo objects for each file.

        Example:
            >>> async for file_info in manager.list_files(prefix="photos/", limit=100):
            ...     print(f"{file_info.key}: {file_info.size_mb:.2f} MB")
        """
        delimiter = "" if recursive else "/"
        count = 0

        async for obj in self._client.list_objects(prefix=prefix, delimiter=delimiter):
            yield FileInfo(
                key=obj["Key"],
                size=obj["Size"],
                last_modified=obj["LastModified"],
                etag=obj["ETag"].strip('"'),
                storage_class=StorageClass(obj.get("StorageClass", "STANDARD")),
            )

            count += 1
            if limit and count >= limit:
                break

    async def delete_file(self, key: str) -> None:
        """
        Delete single file from S3.

        Args:
            key: S3 object key (path) to delete.

        Raises:
            S3Error: If deletion fails.

        Example:
            >>> await manager.delete_file("folder/file.txt")
        """
        await self._client.delete_object(key)
        logger.info(f"Deleted: {key}")

    async def delete_files(self, keys: List[str]) -> int:
        """
        Delete multiple files efficiently.

        Files are deleted in batches of up to 1000 for efficiency.

        Args:
            keys: List of S3 object keys (paths) to delete.

        Returns:
            Number of files deleted.

        Example:
            >>> keys = ["file1.txt", "file2.txt", "file3.txt"]
            >>> count = await manager.delete_files(keys)
            >>> print(f"Deleted {count} files")
        """
        if not keys:
            return 0

        batches = [keys[i : i + 1000] for i in range(0, len(keys), 1000)]

        deleted_count = 0
        client = await self._client._get_client()
        for batch in batches:
            await client.delete_objects(
                Bucket=self.config.bucket,
                Delete={"Objects": [{"Key": key} for key in batch]},
            )
            deleted_count += len(batch)

        logger.info(f"Deleted {deleted_count} files")
        return deleted_count

    async def move_file(self, source_key: str, dest_key: str) -> None:
        """
        Move file within bucket (copy + delete).

        Args:
            source_key: Source object key (path).
            dest_key: Destination object key (path).

        Raises:
            S3FileNotFoundError: If source file doesn't exist.
            S3Error: If operation fails.

        Example:
            >>> await manager.move_file("old/path.txt", "new/path.txt")
        """
        await self._client.copy_object(source_key, dest_key)
        await self.delete_file(source_key)
        logger.info(f"Moved: {source_key} -> {dest_key}")

    async def copy_file(self, source_key: str, dest_key: str) -> None:
        """
        Copy file within bucket.

        Args:
            source_key: Source object key (path).
            dest_key: Destination object key (path).

        Raises:
            S3FileNotFoundError: If source file doesn't exist.
            S3Error: If copy fails.

        Example:
            >>> await manager.copy_file("original.txt", "backup.txt")
        """
        await self._client.copy_object(source_key, dest_key)
        logger.info(f"Copied: {source_key} -> {dest_key}")

    async def get_usage_stats(self) -> UsageStats:
        """
        Get detailed storage usage statistics for the bucket.

        Iterates through all files to calculate statistics. May take
        time for buckets with many files.

        Returns:
            UsageStats object with:
            - total_files: Total number of files
            - total_size_bytes: Total size in bytes
            - total_size_gb: Total size in GB
            - total_size_mb: Total size in MB
            - avg_file_size_mb: Average file size in MB
            - by_storage_class: Dictionary of file counts by storage class

        Example:
            >>> stats = await manager.get_usage_stats()
            >>> print(f"Total: {stats.total_files} files, {stats.total_size_gb:.2f} GB")
            >>> print(f"Average: {stats.avg_file_size_mb:.2f} MB per file")
        """
        total_size = 0
        file_count = 0
        storage_classes = {}

        async for file_info in self.list_files():
            total_size += file_info.size
            file_count += 1

            storage_class = file_info.storage_class or StorageClass.STANDARD
            storage_classes[storage_class] = storage_classes.get(storage_class, 0) + 1

        avg_file_size_mb = (
            (total_size / (1024**2) / file_count) if file_count > 0 else 0
        )

        return UsageStats(
            total_files=file_count,
            total_size_bytes=total_size,
            total_size_gb=total_size / (1024**3),
            total_size_mb=total_size / (1024**2),
            avg_file_size_mb=avg_file_size_mb,
            by_storage_class=storage_classes,
        )

    async def purge(self) -> int:
        """
        Purge all files and incomplete uploads from bucket.

        WARNING: This operation is irreversible! Deletes all objects
        and aborts all incomplete multipart uploads in the bucket.

        Returns:
            Total number of deleted objects (files + incomplete uploads).

        Example:
            >>> deleted_count = await manager.purge()
            >>> print(f"Purged {deleted_count} objects")
        """
        logger.warning(f"Purging bucket: {self.config.bucket}")

        keys = []
        async for file_info in self.list_files():
            keys.append(file_info.key)

        deleted_count = await self.delete_files(keys)

        client = await self._client._get_client()
        try:
            paginator = client.get_paginator("list_multipart_uploads")
            async for page in paginator.paginate(Bucket=self.config.bucket):
                if "Uploads" in page:
                    for upload in page["Uploads"]:
                        await client.abort_multipart_upload(
                            Bucket=self.config.bucket,
                            Key=upload["Key"],
                            UploadId=upload["UploadId"],
                        )
                        deleted_count += 1
        except Exception as e:
            logger.warning(f"Error listing incomplete uploads: {e}")

        logger.info(f"Purge completed. Deleted {deleted_count} objects")
        return deleted_count
