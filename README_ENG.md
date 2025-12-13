# NeoS3Files Documentation

## Introduction

`NeoS3Files` is a high-level asynchronous wrapper designed to work seamlessly with S3-compatible object storage services such as AWS S3, MinIO, Yandex Object Storage, VK Cloud Storage, and others. It simplifies the process of managing files within these storages by providing an easy-to-use API that abstracts away complexities associated with low-level operations like multipart uploads, deletions, and more.

### Features Overview

- Asynchronous methods for all operations
- Support for multiple S3-compatible providers
- Built-in handling of multipart uploads/downloads
- Customizable configurations via class attributes
- Robust error handling through custom exceptions (`S3Exception`, `S3UploadError`, etc.)
- Logging capabilities for debugging purposes

---

## Installation & Usage

Install using pip:

```bash
pip install neos3files
```

### Example Configuration

#### Creating an instance:

```python
from neos3files import S3Manager, S3Config

config = S3Config.from_dict({
    "endpoint_url": "https://storage.yandexcloud.net",
    "bucket": "your-bucket-name",
    "access_key": "...",
    "secret_key": "..."
})

manager = S3Manager.from_config(config)
```

---

## Methods Overview

### Core Operations

- **exists**: Check if a file exists at a given path
- **get_file_info**: Retrieve details about a specific file
- **purge**: Clear entire contents of the bucket
- **clear_incomplete_uploads**: Remove unfinished multipart uploads
- **get_usage_gb**: Get total usage in gigabytes
- **move**: Move a file from one location to another
- **copy**: Duplicate a file within the same bucket
- **upload**: Upload a file to the specified directory/path
- **download**: Download a file locally
- **delete**: Remove a single file
- **delete_multiple**: Batch deletion of multiple files
- **list_files**: List available files under a certain prefix/directory
- **generate_presigned_url**: Create temporary URLs for accessing resources securely

---

## Advanced Functionality

- **Multipart Uploads**: Automatically splits large files into chunks during upload processes
- **Custom Metadata Handling**: Optionally attach additional metadata when uploading files
- **Parallel Processing**: Implemented via asyncio for faster concurrent operations

---

## Error Handling

All critical errors are raised as subclasses of `S3Exception`. Specific cases include:

- **S3UploadError**: Thrown upon failure during upload attempts
- **S3DownloadError**: Encountered issues related to downloading a resource

These exceptions provide meaningful context, allowing developers to handle failures gracefully.

---

## Security Considerations

The library uses AI-driven security mechanisms to ensure proper validation and encryption where applicable. However, it’s important to follow best practices regarding credentials management and secure deployment environments.

---

## Contributing

We welcome contributions! Please submit pull requests following our contribution guidelines outlined in the repository's CONTRIBUTING.md file.

---

## License

This project is licensed under the terms of the MIT license. See LICENSE file for further information.

---

For any questions or feedback, feel free to reach out via GitHub Issues or Discussions channels.
```

**Note:** This documentation serves both as README and reference guide for users. Additional examples can be found in the project's example folder.


