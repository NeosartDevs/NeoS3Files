# NeoS3Files

Высокоуровневая асинхронная Python-библиотека для работы с S3-совместимыми хранилищами.

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0.0-orange)](https://pypi.org/project/neos3files/)

NeoS3Files предоставляет удобный асинхронный интерфейс для работы с AWS S3, MinIO и другими S3-совместимыми хранилищами. Библиотека построена на базе `aioboto3` и `aiofiles`, обеспечивая полностью неблокирующие операции ввода-вывода.

## Возможности

- **Полностью асинхронный API** — все операции ввода-вывода неблокирующие, построены на `asyncio`
- **Автоматическая многокомпонентная загрузка** — большие файлы автоматически разбиваются на части и загружаются параллельно
- **Отслеживание прогресса** — колбэки для мониторинга прогресса загрузки
- **Пул соединений** — автоматическое переиспользование соединений для максимальной производительности
- **Иерархия исключений** — типизированные исключения для всех видов ошибок S3
- **Утилиты** — санитизация имён файлов, парсинг S3 URL, форматирование размеров, расчёт ETag
- **Поддержка S3-совместимых хранилищ** — AWS S3, MinIO, DigitalOcean Spaces, Яндекс.Облако, VK Cloud и другие

## Установка

```bash
pip install neos3files
```

## Требования

- Python 3.7+
- `aioboto3` >= 11.0.0
- `aiofiles` >= 23.0.0
- `botocore` >= 1.29.0

## Быстрый старт

```python
import asyncio
from neos3files import S3Config, S3Manager

async def main():
    # Создание конфигурации
    config = S3Config(
        endpoint_url="https://s3.example.com",
        bucket="my-bucket",
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1",
    )

    async with S3Manager(config) as manager:
        # Загрузка файла
        info = await manager.upload_file("local_file.txt", "remote/file.txt")
        print(f"Загружен: {info.key}, размер: {info.size_mb:.2f} МБ")

        # Проверка существования
        exists = await manager.exists("remote/file.txt")
        print(f"Файл существует: {exists}")

        # Получение информации о файле
        info = await manager.get_file_info("remote/file.txt")
        print(f"Тип: {info.content_type}, Изменён: {info.last_modified}")

        # Скачивание файла
        await manager.download_file("remote/file.txt", "downloaded.txt")

        # Перемещение/копирование
        await manager.copy_file("remote/file.txt", "remote/backup.txt")
        await manager.move_file("remote/file.txt", "remote/renamed.txt")

        # Удаление
        await manager.delete_file("remote/backup.txt")

asyncio.run(main())
```

## Архитектура

Библиотека состоит из двух основных слоёв:

| Компонент | Назначение |
|-----------|------------|
| `S3Client` | Низкоуровневый асинхронный клиент с пулом соединений. Предоставляет прямой доступ к операциям S3 |
| `S3Manager` | Высокоуровневый менеджер с автоматической многокомпонентной загрузкой, отслеживанием прогресса и удобными методами |

### S3Config

Конфигурация подключения к S3-хранилищу:

```python
from neos3files import S3Config

config = S3Config(
    endpoint_url="https://s3.example.com",  # URL S3-совместимого хранилища
    bucket="my-bucket",                      # Имя бакета
    access_key="AKIAIOSFODNN7EXAMPLE",       # Ключ доступа
    secret_key="wJalrXUtnFEMI/K7MDENG/...",  # Секретный ключ
    region="us-west-2",                      # Регион (опционально)
    verify_ssl=True,                         # Проверка SSL-сертификатов
    timeout=30,                              # Таймаут соединения в секундах
    max_pool_connections=10,                 # Максимальное число соединений в пуле
)

# Создание из словаря
config = S3Config.from_dict({
    "endpoint_url": "https://s3.example.com",
    "bucket": "my-bucket",
    "access_key": "key",
    "secret_key": "secret",
})

# Экспорт в словарь
config_dict = config.to_dict()
```

### S3Manager

Высокоуровневый интерфейс для повседневных операций.

#### Создание

```python
# Стандартный способ
manager = S3Manager(
    config,
    chunk_size=50 * 1024 * 1024,  # Размер части: 50 МБ
    max_concurrent_uploads=5,     # Максимум одновременных загрузок частей
)

# Быстрое создание из учётных данных
manager = S3Manager.from_credentials(
    endpoint_url="https://s3.example.com",
    bucket="my-bucket",
    access_key="key",
    secret_key="secret",
    chunk_size=10 * 1024 * 1024,
)
```

#### Загрузка файлов с отслеживанием прогресса

```python
from neos3files import UploadProgress

def on_progress(progress: UploadProgress):
    print(f"{progress.key}: {progress.progress_percent:.1f}% "
          f"({progress.completed_parts}/{progress.total_parts} частей)")

info = await manager.upload_file(
    "large_video.mp4",
    "videos/video.mp4",
    content_type="video/mp4",
    metadata={"author": "user123", "version": "1.0"},
    progress_callback=on_progress,
)
print(f"Готово! Размер: {info.size_mb:.2f} МБ")
```

#### Список файлов

```python
# Все файлы в бакете
async for file_info in manager.list_files():
    print(f"{file_info.key}: {file_info.size_mb:.2f} МБ")

# Фильтрация по префиксу
async for file_info in manager.list_files(prefix="photos/2024/"):
    print(f"{file_info.key}: {file_info.filename}")

# Без рекурсии (только файлы в корне префикса)
async for file_info in manager.list_files(prefix="data/", recursive=False, limit=100):
    print(file_info.key)
```

#### Массовое удаление

```python
keys = ["file1.txt", "file2.txt", "file3.txt"]
deleted = await manager.delete_files(keys)
print(f"Удалено файлов: {deleted}")
```

#### Статистика использования

```python
stats = await manager.get_usage_stats()

print(f"Всего файлов: {stats.total_files}")
print(f"Общий размер: {stats.total_size_gb:.2f} ГБ")
print(f"Средний размер: {stats.avg_file_size_mb:.2f} МБ")
print(f"По классам хранения: {stats.by_storage_class}")
```

#### Полная очистка бакета

```python
# ⚠️ Внимание: операция необратима!
deleted = await manager.purge()
print(f"Удалено объектов: {deleted}")
```

### S3Client

Низкоуровневый клиент для прямых операций с S3. Используйте, когда нужен полный контроль.

```python
from neos3files import S3Client

async with S3Client(config) as client:
    # Метаданные объекта
    info = await client.head_object("file.txt")
    print(f"Размер: {info['ContentLength']} байт")

    # Загрузка небольшого файла
    await client.put_object(
        "data.txt",
        b"Hello, World!",
        content_type="text/plain",
        metadata={"source": "api"},
    )

    # Потоковое скачивание
    import aiofiles
    async with aiofiles.open("local.txt", "wb") as f:
        await client.download_fileobj("remote.txt", f)

    # Копирование и удаление
    await client.copy_object("source.txt", "dest.txt")
    await client.delete_object("old.txt")

    # Ручная многокомпонентная загрузка
    upload = await client.create_multipart_upload("large.bin")
    upload_id = upload["UploadId"]

    parts = []
    for i, chunk in enumerate(chunks, 1):
        result = await client.upload_part("large.bin", upload_id, i, chunk)
        parts.append({"PartNumber": i, "ETag": result["ETag"]})

    await client.complete_multipart_upload("large.bin", upload_id, parts)

    # Или отмена при ошибке
    await client.abort_multipart_upload("large.bin", upload_id)
```

## Модели данных

### FileInfo

```python
info = await manager.get_file_info("path/file.txt")

print(info.key)             # "path/file.txt"
print(info.size)            # размер в байтах
print(info.size_mb)         # размер в МБ
print(info.size_gb)         # размер в ГБ
print(info.filename)         # "file.txt"
print(info.directory)        # "path"
print(info.content_type)    # "text/plain"
print(info.last_modified)   # datetime объект
print(info.etag)            # ETag без кавычек
print(info.storage_class)   # StorageClass.STANDARD
print(info.metadata)         # dict[str, str]
```

### UploadProgress

```python
@dataclass
class UploadProgress:
    key: str                # Ключ загружаемого объекта
    total_size: int         # Общий размер в байтах
    uploaded_size: int      # Загружено байт
    completed_parts: int    # Завершено частей
    total_parts: int        # Всего частей
    progress_percent: float # Процент выполнения (0.0 - 100.0)
```

### UsageStats

```python
@dataclass
class UsageStats:
    total_files: int                              # Количество файлов
    total_size_bytes: int                         # Общий размер в байтах
    total_size_gb: float                          # Общий размер в ГБ
    total_size_mb: float                          # Общий размер в МБ
    avg_file_size_mb: float                       # Средний размер файла в МБ
    by_storage_class: dict[StorageClass, int]     # Распределение по классам
```

### StorageClass

```python
class StorageClass(str, Enum):
    STANDARD            # Стандартное хранение
    STANDARD_IA         # Редкий доступ
    GLACIER             # Архивное хранение
    DEEP_ARCHIVE        # Глубокий архив
    INTELLIGENT_TIERING # Автоматический выбор класса
```

## Исключения

Все исключения наследуются от базового класса `S3Error`:

| Исключение | Описание |
|-----------|----------|
| `S3Error` | Базовое исключение для всех ошибок S3 |
| `S3ConnectionError` | Ошибка подключения к S3-сервису |
| `S3UploadError` | Ошибка при загрузке файла |
| `S3DownloadError` | Ошибка при скачивании файла |
| `S3FileNotFoundError` | Файл не найден в хранилище |
| `S3BucketNotFoundError` | Бакет не найден |
| `S3PermissionError` | Ошибка доступа (недостаточно прав) |
| `S3ConfigurationError` | Неверная конфигурация |

Пример обработки:

```python
from neos3files import (
    S3FileNotFoundError,
    S3PermissionError,
    S3ConnectionError,
    S3Error,
)

try:
    info = await manager.get_file_info("important.txt")
except S3FileNotFoundError:
    print("Файл не найден")
except S3PermissionError:
    print("Нет доступа к файлу")
except S3ConnectionError:
    print("Ошибка подключения к S3")
except S3Error as e:
    print(f"Ошибка S3: {e.message}")
    if e.original_error:
        print(f"Исходная ошибка: {e.original_error}")
```

## Утилиты

```python
from neos3files import sanitize_filename, parse_s3_url, build_s3_url, format_size

# Санитизация имени файла
safe = sanitize_filename("мой файл (1).txt")
print(safe)  # "мой_файл_1.txt"

# Парсинг S3 URL
bucket, key = parse_s3_url("s3://my-bucket/path/to/file.txt")
print(bucket, key)  # "my-bucket", "path/to/file.txt"

bucket, key = parse_s3_url("https://s3.amazonaws.com/bucket/key.txt")
print(bucket, key)  # "bucket", "key.txt"

# Построение S3 URL
url = build_s3_url("my-bucket", "folder/file.txt")
print(url)  # "s3://my-bucket/folder/file.txt"

url = build_s3_url("my-bucket", "file.txt", "https://s3.example.com")
print(url)  # "https://s3.example.com/my-bucket/file.txt"

# Форматирование размера
print(format_size(1024))        # "1.00 KB"
print(format_size(1073741824))  # "1.00 GB"
print(format_size(0))           # "0 B"
```

## Поддерживаемые хранилища

Библиотека работает с любыми S3-совместимыми хранилищами:

- **AWS S3**
- **MinIO**
- **DigitalOcean Spaces**
- **Яндекс.Облако (Yandex Object Storage)**
- **VK Cloud (Cloud Storage)**
- **Selectel Object Storage**
- **Ceph (RADOS Gateway)**
- и другие S3-совместимые сервисы

## Разработка

```bash
# Клонирование репозитория
git clone https://github.com/NeosartDevs/NeoS3Files.git
cd NeoS3Files

# Установка зависимостей для разработки
pip install -e .[dev]

# Запуск тестов
pytest

# Запуск тестов с покрытием
pytest --cov=neos3files --cov-report=html

# Форматирование кода
black neos3files tests

# Проверка типов
mypy neos3files
```

## Лицензия

MIT License. Подробности в файле [LICENSE](LICENSE).

## Ссылки

- [Исходный код](https://github.com/NeosartDevs/NeoS3Files)
- [Баг-трекер](https://github.com/NeosartDevs/NeoS3Files/issues)
- [PyPI](https://pypi.org/project/neos3files/)
