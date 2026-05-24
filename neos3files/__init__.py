"""
NeoS3Files - High-level async wrapper for S3-compatible storage
"""

from .models import S3Config, FileInfo, StorageClass, UploadProgress, UsageStats
from .exceptions import (
    S3Error,
    S3ConnectionError,
    S3UploadError,
    S3DownloadError,
    S3FileNotFoundError,
    S3BucketNotFoundError,
    S3PermissionError,
    S3ConfigurationError,
)
from .manager import S3Manager
from .client import S3Client
from .utils import sanitize_filename, parse_s3_url, build_s3_url, format_size

__version__ = "2.0.0"
__author__ = "Neosart Team"
__license__ = "MIT"

__all__ = [
    "S3Manager",
    "S3Client",
    "S3Config",
    "FileInfo",
    "StorageClass",
    "UploadProgress",
    "UsageStats",
    "S3Error",
    "S3ConnectionError",
    "S3UploadError",
    "S3DownloadError",
    "S3FileNotFoundError",
    "S3BucketNotFoundError",
    "S3PermissionError",
    "S3ConfigurationError",
    "sanitize_filename",
    "parse_s3_url",
    "build_s3_url",
    "format_size",
]
