"""
Utility functions for S3 operations
"""

import os
import hashlib
import re
from typing import Optional
from urllib.parse import urlparse
import io


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for S3 by removing invalid characters.

    Replaces spaces with underscores and removes all characters except
    word characters, hyphens, and dots.

    Args:
        filename: Original filename to sanitize.

    Returns:
        Sanitized filename safe for S3.

    Example:
        >>> sanitize_filename("my file (1).txt")
        'my_file_1.txt'
        >>> sanitize_filename("test@#$file.pdf")
        'testfile.pdf'
    """
    filename = filename.replace(" ", "_")
    filename = re.sub(r"[^\w\-\.]", "", filename)
    return filename


def calculate_etag(file_path: str, chunk_size: int = 8388608) -> str:
    """
    Calculate S3 ETag for a file.

    For single-part uploads (file size <= chunk_size), returns MD5 hexdigest.
    For multipart uploads, returns MD5 of concatenated part digests with part count.

    Args:
        file_path: Path to the file to calculate ETag for.
        chunk_size: Size of each chunk in bytes. Default is 8MB (8388608 bytes).

    Returns:
        ETag string. For single-part: "md5hex", for multipart: "md5hex-partcount".

    Example:
        >>> calculate_etag("small_file.txt")
        '65a8e27d8879283831b664bd8b7f0ad4'
        >>> calculate_etag("large_file.bin", chunk_size=10485760)
        'a1b2c3d4e5f6-3'
    """
    md5_hashes = []

    with open(file_path, "rb") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            md5_hashes.append(hashlib.md5(data))

    if len(md5_hashes) == 1:
        # For single-part files, return hexdigest directly
        return md5_hashes[0].hexdigest()

    # For multipart, concatenate digests and calculate MD5 of the concatenation
    digests = b"".join(md5.digest() for md5 in md5_hashes)
    digests_md5 = hashlib.md5(digests).hexdigest()
    return f"{digests_md5}-{len(md5_hashes)}"


def parse_s3_url(url: str) -> tuple[str, str]:
    """Parse S3 URL into bucket and key"""
    parsed = urlparse(url)

    if parsed.scheme not in ("s3", "http", "https"):
        raise ValueError(f"Invalid S3 URL scheme: {parsed.scheme}")

    # s3://bucket/key
    if parsed.scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    # https://s3.amazonaws.com/bucket/key or https://bucket.s3.amazonaws.com/key
    else:
        hostname = parsed.netloc

        # Format 1: https://bucket.s3.amazonaws.com/key
        if hostname.endswith(".s3.amazonaws.com"):
            bucket = hostname.split(".")[0]
            key = parsed.path.lstrip("/")
        # Format 2: https://s3.amazonaws.com/bucket/key
        elif hostname == "s3.amazonaws.com" or hostname.endswith(".s3.amazonaws.com"):
            path_parts = parsed.path.lstrip("/").split("/", 1)
            if len(path_parts) >= 1:
                bucket = path_parts[0]
                key = path_parts[1] if len(path_parts) > 1 else ""
            else:
                bucket = ""
                key = ""
        else:
            # Custom endpoint: https://storage.example.com/bucket/key
            path_parts = parsed.path.lstrip("/").split("/", 1)
            if len(path_parts) == 2:
                bucket, key = path_parts
            else:
                bucket = ""
                key = path_parts[0] if path_parts else ""

    return bucket, key


def build_s3_url(bucket: str, key: str, endpoint_url: str = None) -> str:
    """
    Build S3 URL from bucket and key.

    Args:
        bucket: S3 bucket name.
        key: S3 object key (path).
        endpoint_url: Optional custom endpoint URL. If not provided, returns s3:// URL.

    Returns:
        S3 URL string.

    Example:
        >>> build_s3_url("my-bucket", "folder/file.txt")
        's3://my-bucket/folder/file.txt'
        >>> build_s3_url("my-bucket", "file.txt", "https://s3.example.com")
        'https://s3.example.com/my-bucket/file.txt'
    """
    if endpoint_url:
        endpoint_url = endpoint_url.rstrip("/")

        if "s3.amazonaws.com" in endpoint_url:
            return f"{endpoint_url}/{bucket}/{key.lstrip('/')}"
        else:
            return f"{endpoint_url}/{bucket}/{key.lstrip('/')}"
    return f"s3://{bucket}/{key.lstrip('/')}"


def format_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.

    Converts bytes to appropriate unit (B, KB, MB, GB, TB, PB) with 2 decimal places.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted size string with unit.

    Example:
        >>> format_size(1024)
        '1.00 KB'
        >>> format_size(1073741824)
        '1.00 GB'
        >>> format_size(0)
        '0 B'
    """
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0

    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024.0
        unit_index += 1

    return f"{size_bytes:.2f} {units[unit_index]}"
