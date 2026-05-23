"""
Custom exceptions for S3 operations
"""


class S3Error(Exception):
    """
    Base S3 exception.

    All S3-related exceptions inherit from this class.

    Args:
        message: Error message.
        original_error: Optional original exception that caused this error.

    Attributes:
        message: Error message string.
        original_error: Original exception if available.
    """

    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class S3ConnectionError(S3Error):
    """
    S3 connection error.

    Raised when unable to connect to S3 service or create client.
    """


class S3UploadError(S3Error):
    """
    File upload error.

    Raised when file upload operation fails.

    Args:
        key: S3 object key that failed to upload.
        message: Error message.
        original_error: Optional original exception.

    Attributes:
        key: S3 object key that failed.
    """

    def __init__(self, key: str, message: str, original_error: Exception = None):
        self.key = key
        super().__init__(f"Failed to upload '{key}': {message}", original_error)


class S3DownloadError(S3Error):
    """
    File download error.

    Raised when file download operation fails.

    Args:
        key: S3 object key that failed to download.
        message: Error message.
        original_error: Optional original exception.

    Attributes:
        key: S3 object key that failed.
    """

    def __init__(self, key: str, message: str, original_error: Exception = None):
        self.key = key
        super().__init__(f"Failed to download '{key}': {message}", original_error)


class S3FileNotFoundError(S3Error):
    """
    File not found in S3.

    Raised when attempting to access a non-existent object.

    Args:
        key: S3 object key that was not found.
    """

    def __init__(self, key: str):
        super().__init__(f"File '{key}' not found in S3")


class S3BucketNotFoundError(S3Error):
    """
    Bucket not found.

    Raised when attempting to access a non-existent bucket.

    Args:
        bucket: Bucket name that was not found.
    """

    def __init__(self, bucket: str):
        super().__init__(f"Bucket '{bucket}' not found")


class S3PermissionError(S3Error):
    """
    Permission denied error.

    Raised when access is denied due to insufficient permissions.
    """


class S3ConfigurationError(S3Error):
    """
    Invalid configuration error.

    Raised when S3 configuration is invalid or missing required parameters.
    """
