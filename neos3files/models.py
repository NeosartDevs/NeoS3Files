"""
Data models for S3 operations
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class StorageClass(str, Enum):
    """
    S3 storage classes.

    Defines different storage tiers with varying costs and access patterns.
    """

    STANDARD = "STANDARD"
    STANDARD_IA = "STANDARD_IA"
    GLACIER = "GLACIER"
    DEEP_ARCHIVE = "DEEP_ARCHIVE"
    INTELLIGENT_TIERING = "INTELLIGENT_TIERING"


@dataclass
class S3Config:
    """
    S3 connection configuration.

    Contains all parameters needed to connect to an S3-compatible storage service.

    Args:
        endpoint_url: S3 endpoint URL (e.g., "https://s3.amazonaws.com" or custom endpoint).
        bucket: Bucket name.
        access_key: AWS access key ID or equivalent.
        secret_key: AWS secret access key or equivalent.
        region: AWS region name. Defaults to None (us-east-1).
        verify_ssl: Whether to verify SSL certificates. Defaults to True.
        timeout: Connection and read timeout in seconds. Defaults to 30.
        max_pool_connections: Maximum number of connections in connection pool. Defaults to 10.

    Example:
        >>> config = S3Config(
        ...     endpoint_url="https://s3.example.com",
        ...     bucket="my-bucket",
        ...     access_key="AKIAIOSFODNN7EXAMPLE",
        ...     secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ...     region="us-west-2"
        ... )
    """

    endpoint_url: str
    bucket: str
    access_key: str
    secret_key: str
    region: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30
    max_pool_connections: int = 10

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "S3Config":
        """
        Create config from dictionary.

        Args:
            config: Dictionary with configuration parameters.

        Returns:
            S3Config instance.

        Example:
            >>> config_dict = {
            ...     "endpoint_url": "https://s3.example.com",
            ...     "bucket": "my-bucket",
            ...     "access_key": "key",
            ...     "secret_key": "secret"
            ... }
            >>> config = S3Config.from_dict(config_dict)
        """
        return cls(**config)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert config to dictionary.

        Returns:
            Dictionary with configuration parameters (excluding sensitive timeout/pool settings).

        Example:
            >>> config_dict = config.to_dict()
            >>> print(config_dict['bucket'])
            'my-bucket'
        """
        return {
            "endpoint_url": self.endpoint_url,
            "bucket": self.bucket,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "region": self.region,
            "verify_ssl": self.verify_ssl,
        }


@dataclass
class FileInfo:
    """
    File information from S3.

    Contains metadata about an S3 object retrieved from head_object or list_objects.

    Args:
        key: S3 object key (path).
        size: File size in bytes.
        last_modified: Last modification timestamp.
        etag: Object ETag (MD5 hash for single-part, or multipart ETag).
        storage_class: Storage class. Defaults to None.
        content_type: MIME type. Defaults to None.
        metadata: Custom metadata dictionary. Defaults to empty dict.

    Example:
        >>> info = FileInfo(
        ...     key="folder/file.txt",
        ...     size=1024,
        ...     last_modified=datetime.now(),
        ...     etag="abc123",
        ...     content_type="text/plain"
        ... )
        >>> print(f"{info.filename}: {info.size_mb:.2f} MB")
    """

    key: str
    size: int
    last_modified: datetime
    etag: str
    storage_class: Optional[StorageClass] = None
    content_type: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def size_mb(self) -> float:
        """
        Size in megabytes.

        Returns:
            File size in MB (float).
        """
        return self.size / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        """
        Size in gigabytes.

        Returns:
            File size in GB (float).
        """
        return self.size / (1024 * 1024 * 1024)

    @property
    def filename(self) -> str:
        """
        Extract filename from key.

        Returns:
            Filename (last component of key path).
        """
        return self.key.split("/")[-1] if "/" in self.key else self.key

    @property
    def directory(self) -> str:
        """
        Extract directory path from key.

        Returns:
            Directory path (all components except filename), or empty string if at root.
        """
        if "/" in self.key:
            return "/".join(self.key.split("/")[:-1])
        return ""


@dataclass
class UploadProgress:
    """
    Upload progress information.

    Passed to progress_callback during file uploads to track progress.

    Args:
        key: S3 object key being uploaded.
        total_size: Total file size in bytes.
        uploaded_size: Number of bytes uploaded so far.
        completed_parts: Number of completed parts (for multipart uploads).
        total_parts: Total number of parts (for multipart uploads).

    Example:
        >>> def on_progress(progress: UploadProgress):
        ...     print(f"{progress.key}: {progress.progress_percent:.1f}%")
        >>>
        >>> await manager.upload_file(..., progress_callback=on_progress)
    """

    key: str
    total_size: int
    uploaded_size: int
    completed_parts: int
    total_parts: int

    @property
    def progress_percent(self) -> float:
        """
        Upload progress as percentage.

        Returns:
            Progress percentage (0.0 to 100.0).
        """
        if self.total_size == 0:
            return 0.0
        return (self.uploaded_size / self.total_size) * 100


@dataclass
class UsageStats:
    """
    Storage usage statistics for a bucket.

    Contains aggregated statistics about files in the bucket.

    Args:
        total_files: Total number of files.
        total_size_bytes: Total size in bytes.
        total_size_gb: Total size in gigabytes.
        total_size_mb: Total size in megabytes.
        avg_file_size_mb: Average file size in megabytes.
        by_storage_class: Dictionary mapping storage class to file count.

    Example:
        >>> stats = await manager.get_usage_stats()
        >>> print(f"Files: {stats.total_files}")
        >>> print(f"Size: {stats.total_size_gb:.2f} GB")
        >>> print(f"By class: {stats.by_storage_class}")
    """

    total_files: int
    total_size_bytes: int
    total_size_gb: float
    total_size_mb: float
    avg_file_size_mb: float
    by_storage_class: Dict[StorageClass, int] = field(default_factory=dict)
