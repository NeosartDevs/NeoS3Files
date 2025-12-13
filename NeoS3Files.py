"""
NeoS3Files - High-level async wrapper for S3-compatible storage
Высокоуровневый асинхронный wrapper для работы с S3-совместимыми хранилищами

Author: Neosart Team
Version: 1.0.0
License: MIT
"""

import os
import mimetypes
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging

import aioboto3
import aiofiles
import botocore.config
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


@dataclass
class S3Config:
    """Конфигурация для подключения к S3"""
    endpoint_url: str
    bucket: str
    access_key: str
    secret_key: str
    region: Optional[str] = None
    
    @classmethod
    def from_dict(cls, config: Dict[str, str]) -> 'S3Config':
        """Создать конфигурацию из словаря"""
        return cls(**config)


@dataclass
class FileInfo:
    """Информация о файле в S3"""
    key: str
    size: int
    last_modified: str
    etag: str
    storage_class: Optional[str] = None
    
    @property
    def size_mb(self) -> float:
        """Размер файла в МБ"""
        return self.size / (1024 * 1024)
    
    @property
    def size_gb(self) -> float:
        """Размер файла в ГБ"""
        return self.size / (1024 * 1024 * 1024)


class S3Exception(Exception):
    """Базовое исключение для S3Manager"""
    pass


class S3UploadError(S3Exception):
    """Ошибка при загрузке файла"""
    pass


class S3DownloadError(S3Exception):
    """Ошибка при скачивании файла"""
    pass


class S3Manager:
    """
    Высокоуровневый менеджер для работы с S3-совместимыми хранилищами
    
    Поддерживает:
    - AWS S3
    - MinIO
    - Yandex Object Storage
    - VK Cloud Storage
    - И другие S3-совместимые хранилища
    """
    
    CHUNK_SIZE = 50 * 1024 * 1024  # 50MB
    DEFAULT_CONTENT_TYPE = "binary/octet-stream"
    
    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: Optional[str] = None,
        verify_ssl: bool = True
    ):
        """
        Инициализация S3 менеджера
        
        Args:
            endpoint_url: URL эндпоинта S3 хранилища
            bucket: Имя bucket в S3
            access_key: Ключ доступа
            secret_key: Секретный ключ
            region: Регион AWS (опционально). Для AWS S3 обязательно указывать корректный регион.
                   Для других хранилищ (MinIO, Yandex, VK Cloud) можно не указывать.
                   По умолчанию используется 'us-east-1'
            verify_ssl: Проверять SSL сертификат (по умолчанию True)
        
        Examples:
            # Yandex Object Storage (регион не важен)
            s3 = S3Manager(
                endpoint_url="https://storage.yandexcloud.net",
                bucket="my-bucket",
                access_key="...",
                secret_key="..."
            )
            
            # AWS S3 (регион важен!)
            s3 = S3Manager(
                endpoint_url="https://s3.amazonaws.com",
                bucket="my-bucket",
                access_key="...",
                secret_key="...",
                region="eu-west-1"  # Обязательно для AWS!
            )
        """
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region or "us-east-1"  # Дефолтный регион если не указан
        self.verify_ssl = verify_ssl
        self.session = aioboto3.Session()
        
        logger.info(f"S3Manager инициализирован для bucket: {bucket}")
    
    @classmethod
    def from_config(cls, config: S3Config, **kwargs) -> 'S3Manager':
        """
        Создать менеджер из конфигурации
        
        Args:
            config: Объект S3Config с параметрами подключения
            **kwargs: Дополнительные параметры для конструктора
        """
        return cls(
            endpoint_url=config.endpoint_url,
            bucket=config.bucket,
            access_key=config.access_key,
            secret_key=config.secret_key,
            region=config.region,
            **kwargs
        )
    
    def _get_client(self):
        """Создает S3 клиент с настройками"""
        return self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            verify=self.verify_ssl,
            config=botocore.config.Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                retries={'max_attempts': 3, 'mode': 'adaptive'}
            )
        )
    
    async def exists(self, s3_key: str) -> bool:
        """
        Проверить существование файла в S3
        
        Args:
            s3_key: Ключ файла в S3
            
        Returns:
            True если файл существует, False иначе
        """
        try:
            async with self._get_client() as s3:
                await s3.head_object(Bucket=self.bucket, Key=s3_key)
                return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    async def get_file_info(self, s3_key: str) -> FileInfo:
        """
        Получить информацию о файле
        
        Args:
            s3_key: Ключ файла в S3
            
        Returns:
            Объект FileInfo с информацией о файле
        """
        async with self._get_client() as s3:
            response = await s3.head_object(Bucket=self.bucket, Key=s3_key)
            
            return FileInfo(
                key=s3_key,
                size=response['ContentLength'],
                last_modified=response['LastModified'].isoformat(),
                etag=response['ETag'].strip('"'),
                storage_class=response.get('StorageClass')
            )
    
    async def purge(self) -> int:
        """
        Полная очистка S3 хранилища
        Удаляет все файлы и незавершенные загрузки
        
        Returns:
            Количество удаленных объектов
        """
        logger.warning(f"Начинается полная очистка bucket: {self.bucket}")
        deleted_count = 0
        
        async with self._get_client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=""):
                if "Contents" in page:
                    objects_to_delete = [{"Key": obj["Key"]} for obj in page["Contents"]]
                    if objects_to_delete:
                        await s3.delete_objects(
                            Bucket=self.bucket,
                            Delete={"Objects": objects_to_delete}
                        )
                        deleted_count += len(objects_to_delete)
        
        incomplete_count = await self.clear_incomplete_uploads()
        deleted_count += incomplete_count
        
        logger.info(f"Очистка завершена. Удалено объектов: {deleted_count}")
        return deleted_count
    
    async def clear_incomplete_uploads(self) -> int:
        """
        Удаление незавершенных многочастичных загрузок
        
        Returns:
            Количество удаленных незавершенных загрузок
        """
        deleted_count = 0
        
        async with self._get_client() as s3:
            paginator = s3.get_paginator("list_multipart_uploads")
            async for page in paginator.paginate(Bucket=self.bucket):
                if "Uploads" in page:
                    for upload in page["Uploads"]:
                        await s3.abort_multipart_upload(
                            Bucket=self.bucket,
                            Key=upload["Key"],
                            UploadId=upload["UploadId"]
                        )
                        deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"Удалено незавершенных загрузок: {deleted_count}")
        
        return deleted_count
    
    async def get_usage_gb(self) -> float:
        """
        Получить общий размер занятого пространства
        
        Returns:
            Размер в гигабайтах
        """
        total_size = 0
        
        async with self._get_client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket):
                if "Contents" in page:
                    total_size += sum(obj["Size"] for obj in page["Contents"])
        
        return total_size / (1024**3)
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        """
        Получить подробную статистику использования
        
        Returns:
            Словарь со статистикой: total_files, total_size_gb, avg_file_size_mb
        """
        total_size = 0
        file_count = 0
        
        async with self._get_client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket):
                if "Contents" in page:
                    for obj in page["Contents"]:
                        total_size += obj["Size"]
                        file_count += 1
        
        return {
            "total_files": file_count,
            "total_size_gb": total_size / (1024**3),
            "total_size_mb": total_size / (1024**2),
            "avg_file_size_mb": (total_size / (1024**2) / file_count) if file_count > 0 else 0
        }
    
    async def move(self, source_key: str, destination_key: str) -> None:
        """
        Переместить файл (копировать и удалить оригинал)
        
        Args:
            source_key: Исходный путь к файлу в S3
            destination_key: Новый путь к файлу в S3
        """
        logger.debug(f"Перемещение: {source_key} -> {destination_key}")
        
        async with self._get_client() as s3:
            await s3.copy_object(
                Bucket=self.bucket,
                CopySource={'Bucket': self.bucket, 'Key': source_key},
                Key=destination_key
            )
            await s3.delete_object(Bucket=self.bucket, Key=source_key)
        
        logger.info(f"Файл перемещен: {source_key} -> {destination_key}")
    
    async def copy(self, source_key: str, destination_key: str) -> None:
        """
        Скопировать файл
        
        Args:
            source_key: Исходный путь к файлу в S3
            destination_key: Новый путь к файлу в S3
        """
        logger.debug(f"Копирование: {source_key} -> {destination_key}")
        
        async with self._get_client() as s3:
            await s3.copy_object(
                Bucket=self.bucket,
                CopySource={'Bucket': self.bucket, 'Key': source_key},
                Key=destination_key
            )
        
        logger.info(f"Файл скопирован: {source_key} -> {destination_key}")
    
    async def upload(
        self,
        local_filepath: str,
        s3_directory: str = "",
        s3_filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Загрузить файл в S3 с многочастичной загрузкой
        
        Args:
            local_filepath: Путь к локальному файлу
            s3_directory: Директория в S3 (без начального и конечного слеша)
            s3_filename: Имя файла в S3 (если не указано, используется имя локального файла)
            content_type: MIME тип файла (если не указан, определяется автоматически)
            metadata: Дополнительные метаданные для файла
        
        Returns:
            Полный ключ загруженного файла в S3
            
        Raises:
            S3UploadError: При ошибке загрузки
            FileNotFoundError: Если локальный файл не найден
        """
        if not os.path.exists(local_filepath):
            raise FileNotFoundError(f"Файл не найден: {local_filepath}")
        
        filename = s3_filename or os.path.basename(local_filepath)
        filename = filename.replace(" ", "_")
        
        if s3_directory:
            s3_key = f"{s3_directory.strip('/')}/{filename}"
        else:
            s3_key = filename
        
        if content_type is None:
            content_type, _ = mimetypes.guess_type(filename)
            if content_type is None:
                content_type = self.DEFAULT_CONTENT_TYPE
        
        file_size = os.path.getsize(local_filepath)
        logger.info(f"Начало загрузки: {local_filepath} ({file_size / (1024**2):.2f} MB) -> {s3_key}")
        
        async with self._get_client() as s3:
            async with aiofiles.open(local_filepath, "rb") as file:
                upload_id = None
                parts = []
                part_number = 1
                
                try:
                    create_params = {
                        "Bucket": self.bucket,
                        "Key": s3_key,
                        "ContentType": content_type
                    }
                    if metadata:
                        create_params["Metadata"] = metadata
                    
                    response = await s3.create_multipart_upload(**create_params)
                    upload_id = response["UploadId"]
                    
                    while True:
                        chunk = await file.read(self.CHUNK_SIZE)
                        if not chunk:
                            break
                        
                        response = await s3.upload_part(
                            Bucket=self.bucket,
                            Key=s3_key,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=chunk
                        )
                        
                        parts.append({
                            "PartNumber": part_number,
                            "ETag": response["ETag"]
                        })
                        part_number += 1
                        
                        logger.debug(f"Загружена часть {part_number - 1}/{(file_size // self.CHUNK_SIZE) + 1}")
                    
                    await s3.complete_multipart_upload(
                        Bucket=self.bucket,
                        Key=s3_key,
                        UploadId=upload_id,
                        MultipartUpload={"Parts": parts},
                    )
                    
                    logger.info(f"Загрузка завершена: {s3_key}")
                    return s3_key
                    
                except Exception as e:
                    if upload_id:
                        try:
                            await s3.abort_multipart_upload(
                                Bucket=self.bucket,
                                Key=s3_key,
                                UploadId=upload_id,
                            )
                            logger.warning(f"Загрузка отменена: {s3_key}")
                        except Exception as abort_error:
                            logger.error(f"Ошибка при отмене загрузки: {abort_error}")
                    
                    logger.error(f"Ошибка загрузки {local_filepath}: {e}")
                    raise S3UploadError(f"Не удалось загрузить файл {local_filepath}: {e}") from e
    
    async def download(
        self,
        s3_key: str,
        local_directory: str,
        local_filename: Optional[str] = None
    ) -> str:
        """
        Скачать файл из S3
        
        Args:
            s3_key: Ключ файла в S3
            local_directory: Локальная директория для сохранения
            local_filename: Имя файла для сохранения (если не указано, используется имя из S3)
        
        Returns:
            Путь к скачанному файлу
            
        Raises:
            S3DownloadError: При ошибке скачивания
        """
        filename = local_filename or s3_key.split('/')[-1]
        local_filepath = os.path.join(local_directory, filename)
        
        os.makedirs(local_directory, exist_ok=True)
        
        logger.info(f"Начало скачивания: {s3_key} -> {local_filepath}")
        
        try:
            async with self._get_client() as s3:
                await s3.download_file(self.bucket, s3_key, local_filepath)
            
            logger.info(f"Скачивание завершено: {local_filepath}")
            return local_filepath
            
        except Exception as e:
            logger.error(f"Ошибка скачивания {s3_key}: {e}")
            raise S3DownloadError(f"Не удалось скачать файл {s3_key}: {e}") from e
    
    async def delete(self, s3_key: str) -> None:
        """
        Удалить файл из S3
        
        Args:
            s3_key: Ключ файла в S3
        """
        logger.info(f"Удаление файла: {s3_key}")
        
        async with self._get_client() as s3:
            await s3.delete_object(Bucket=self.bucket, Key=s3_key)
        
        logger.debug(f"Файл удален: {s3_key}")
    
    async def delete_multiple(self, s3_keys: List[str]) -> int:
        """
        Удалить несколько файлов за один запрос
        
        Args:
            s3_keys: Список ключей файлов для удаления
            
        Returns:
            Количество удаленных файлов
        """
        if not s3_keys:
            return 0
        
        logger.info(f"Удаление {len(s3_keys)} файлов")
        
        async with self._get_client() as s3:
            objects_to_delete = [{"Key": key} for key in s3_keys]
            
            deleted_count = 0
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i:i+1000]
                await s3.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": batch}
                )
                deleted_count += len(batch)
        
        logger.info(f"Удалено файлов: {deleted_count}")
        return deleted_count
    
    async def list_files(
        self,
        prefix: str = "",
        max_files: Optional[int] = None,
        detailed: bool = False
    ) -> List[str] | List[FileInfo]:
        """
        Получить список файлов в директории
        
        Args:
            prefix: Префикс (директория) для поиска файлов
            max_files: Максимальное количество файлов (None = все)
            detailed: Вернуть подробную информацию (FileInfo объекты)
        
        Returns:
            Список ключей файлов или список FileInfo объектов
        """
        files = []
        count = 0
        
        async with self._get_client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                if "Contents" in page:
                    for obj in page["Contents"]:
                        if detailed:
                            files.append(FileInfo(
                                key=obj["Key"],
                                size=obj["Size"],
                                last_modified=obj["LastModified"].isoformat(),
                                etag=obj["ETag"].strip('"'),
                                storage_class=obj.get("StorageClass")
                            ))
                        else:
                            files.append(obj["Key"])
                        
                        count += 1
                        if max_files and count >= max_files:
                            return files
        
        logger.debug(f"Найдено файлов: {len(files)} (префикс: '{prefix}')")
        return files
    
    async def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
        method: str = "get_object"
    ) -> str:
        """
        Создать временную ссылку на файл
        
        Args:
            s3_key: Ключ файла в S3
            expiration: Время жизни ссылки в секундах (по умолчанию 1 час)
            method: Метод доступа ('get_object' для скачивания, 'put_object' для загрузки)
        
        Returns:
            Presigned URL
        """
        async with self._get_client() as s3:
            url = await s3.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )
        
        logger.debug(f"Создана временная ссылка для {s3_key} (срок: {expiration}с)")
        return url
    
    def __repr__(self) -> str:
        return f"S3Manager(bucket='{self.bucket}', endpoint='{self.endpoint_url}')"
