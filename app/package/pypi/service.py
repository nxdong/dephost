import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

from fastapi import HTTPException, UploadFile

from app.common.logger import logger
from app.download.client import DownloadClient
from app.proxy.manager import ProxyManager
from app.settings import settings

from .schema import (
    PackageCreate,
    PackageInfo,
    PackageSearch,
    PackageVersion,
    Statistics,
)


def normalize_package_name(package_name: str) -> str:
    """
    标准化包名:
    1. 转换为小写
    2. 将连字符和下划线替换为连字符
    3. 移除多余的空格
    """
    return package_name.lower().replace("_", "-").replace(" ", "-")


def normalize_package_path(package_name: str) -> str:
    """
    标准化包名用于URL路径:
    1. 标准化包名
    2. URL编码特殊字符
    """
    normalized = normalize_package_name(package_name)
    return quote(normalized)


def normalize_filename(filename: str) -> str:
    """
    标准化文件名:
    1. 将包名部的下划线替换为连字符
    2. URL编码特殊字符
    """
    # 分离文件名和扩展名
    name_parts = filename.rsplit(".", 2)  # 处理类似 name.tar.gz 的情况
    if len(name_parts) > 1:
        # 如果有扩展名
        base_name = name_parts[0]
        extensions = ".".join(name_parts[1:])
        # 标准化基础名称（将下划线替换为连字符）
        normalized_base = base_name.replace("_", "-")
        # 重新组合文件名
        normalized = f"{normalized_base}.{extensions}"
    else:
        # 如果没有扩展名
        normalized = filename.replace("_", "-")

    return quote(normalized)


class PyPIService:
    def __init__(self, storage_path: str = "packages"):
        self.storage_path = storage_path
        self.download_client = DownloadClient(ProxyManager())
        self.sources = settings.pypi.sources
        self.index_file = Path(storage_path) / "package_index.json"

        # 合并 PyPICache 的属性
        self._local_index: Set[str] = set()
        self._remote_index: Set[str] = set()
        self.cache_ttl = timedelta(hours=1)
        self.last_index_update: Optional[datetime] = None

        os.makedirs(storage_path, exist_ok=True)

    async def init_index(self):
        """初始化包索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    data = json.load(f)
                    # 更新本地和远程索引
                    self._local_index = set(data.get("local_packages", []))
                    self._remote_index = set(data.get("remote_packages", []))
                    self.last_index_update = datetime.fromisoformat(data["last_update"])
                    logger.info(
                        "package.index.loaded",
                        local_count=len(self._local_index),
                        remote_count=len(self._remote_index),
                    )
            except Exception as e:
                logger.error("package.index.load.failed", error=str(e))

        # 如果没有索引或索引过期,从上游更新
        if not self._remote_index or self._is_index_expired():
            await self.update_index()

    def _is_index_expired(self) -> bool:
        """检查索引是否过期"""
        return (
            not self.last_index_update
            or datetime.now() - self.last_index_update > self.cache_ttl
        )

    async def update_index(self):
        """从上游更新索引"""
        try:
            packages = await self.list_upstream_packages()
            if packages:
                self._remote_index = set(packages)
                self.last_index_update = datetime.now()

                # 保存到本地文件
                cache_data = {
                    "last_update": self.last_index_update.isoformat(),
                    "local_packages": list(self._local_index),
                    "remote_packages": list(self._remote_index),
                }
                with open(self.index_file, "w") as f:
                    json.dump(cache_data, f)

                logger.info(
                    "package.index.updated",
                    local_count=len(self._local_index),
                    remote_count=len(self._remote_index),
                )
        except Exception as e:
            logger.error("package.index.update.failed", error=str(e))

    def update_local_index(self, package_name: str):
        """更新本地索引"""
        self._local_index.add(package_name)
        self._save_index()

    def remove_from_local_index(self, package_name: str):
        """从本地索引中移除包"""
        self._local_index.discard(package_name)
        self._save_index()

    def _save_index(self):
        """保存索引到文件"""
        try:
            cache_data = {
                "last_update": self.last_index_update.isoformat(),
                "local_packages": list(self._local_index),
                "remote_packages": list(self._remote_index),
            }
            with open(self.index_file, "w") as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.error("package.index.save.failed", error=str(e))

    async def get_package(
        self, package_name: str, version: str, filename: str
    ) -> bytes:
        """获取包文件"""
        normalized_name = normalize_package_name(package_name)
        normalized_filename = normalize_filename(filename)
        logger.info(
            f"filename: {filename} normalized_name: {normalized_name} normalized_filename: {normalized_filename}"
        )
        package_path = os.path.join(
            self.storage_path, normalized_name, version, normalized_filename
        )

        if os.path.exists(package_path):
            # 如果本地存在，直接返回文件内容
            with open(package_path, "rb") as f:
                return f.read()

        # 如果本地不存在，从远程源下载
        for source_url in self.sources:
            try:
                source_url = source_url.rstrip("/")
                normalized_path = normalize_package_path(package_name)
                logger.info(f"normalized_path: {normalized_path}")
                logger.info(f"source_url: {source_url}")

                if "/simple" in source_url:
                    # 首先获取simple API页面
                    index_url = f"{source_url}/{normalized_path}/"
                    logger.debug(f"downloading index from {index_url}")
                    index_content = await self.download_client.download(index_url)

                    # 解析HTML找到正确的下载链接
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(index_content, "html.parser")

                    # 查找匹配的文件链接
                    file_url = None
                    # logger.info(f"soup: {soup}")
                    for link in soup.find_all("a"):
                        link_text = link.string if link.string else ""
                        # 标准化链接文本中的包名部分
                        normalized_link = link_text.replace("_", "-")
                        logger.info(
                            f"normalized_filename: {normalized_filename} normalized_link: {normalized_link} filename: {filename}"
                        )
                        if normalized_link and normalized_filename in normalized_link:
                            file_url = link.get("href")
                            break
                    logger.info(f"file_url=====: {file_url}")
                    if not file_url:
                        continue
                else:
                    # 标准PyPI API 的文件URL格式，使用标准化的件名
                    file_url = f"{source_url}/packages/{normalized_path}/{version}/{normalized_filename}"

                logger.info(
                    "package.download.start",
                    package=package_name,
                    version=version,
                    source=source_url,
                )
                logger.info(f"downloading file from {file_url}")
                content = await self.download_client.download(file_url)
                if content:
                    # 确保目录存在
                    os.makedirs(os.path.dirname(package_path), exist_ok=True)
                    # 保存到本地
                    with open(package_path, "wb") as f:
                        f.write(content)

                    logger.info(
                        "package.download.success",
                        package=package_name,
                        version=version,
                        source=source_url,
                    )
                    return content

            except Exception as e:
                logger.error(
                    "package.download.failed",
                    package=package_name,
                    version=version,
                    source=source_url,
                    error=str(e),
                )
                continue

        # 如果所有源都下载失败��抛出异常
        raise HTTPException(
            status_code=404,
            detail=f"Package {package_name} version {version} not found",
        )

    async def get_package_info(
        self, package_name: str, version: Optional[str] = None
    ) -> Optional[PackageInfo]:
        """获取包信息"""
        package_dir = os.path.join(self.storage_path, package_name)
        if not os.path.exists(package_dir):
            return None

        # 这里应该从数据库或文件系统获取真实数据
        versions = [
            PackageVersion(
                version="1.0.0",
                size=1024,
                filename=f"{package_name}-1.0.0.tar.gz",
                upload_time=datetime.now(),
                downloads=100,
                url=f"{package_name}-1.0.0.tar.gz",
            )
        ]

        return PackageInfo(
            name=package_name,
            version=versions[-1].version,
            description=f"Description for {package_name}",
            versions=versions,
            total_downloads=sum(v.downloads for v in versions),
        )

    async def upload_package(
        self, package_data: PackageCreate, package_file: UploadFile
    ) -> PackageInfo:
        """上传包"""
        package_dir = os.path.join(self.storage_path, package_data.name)
        os.makedirs(package_dir, exist_ok=True)

        # 保存文件
        file_path = os.path.join(package_dir, f"{package_data.version}.tar.gz")
        content = await package_file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # 更新本地索引
        self.update_local_index(package_data.name)

        # 返回更新后的包信息
        return await self.get_package_info(package_data.name)

    async def delete_package(self, package_name: str, version: str) -> bool:
        """删除包文件"""
        file_path = os.path.join(self.storage_path, package_name, version)
        if not os.path.exists(file_path):
            return False

        os.remove(file_path)

        # 如果这是包的最后一个版本,从本地索引中移除
        if not os.listdir(os.path.dirname(file_path)):
            self.remove_from_local_index(package_name)

        return True

    async def list_versions(self, package_name: str) -> List[PackageVersion]:
        """获取包的所有版本"""
        # 首先尝试���本地获取
        package_dir = os.path.join(self.storage_path, package_name)
        if os.path.exists(package_dir):
            versions = []
            for version_dir in os.listdir(package_dir):
                if os.path.isdir(os.path.join(package_dir, version_dir)):
                    versions.append(
                        PackageVersion(
                            version=version_dir,
                            filename=f"{package_name}-{version_dir}.tar.gz",
                            url=f"{package_name}-{version_dir}.tar.gz",
                        )
                    )
            return versions

        # 如果本地没有，从远程源获取
        for source_url in self.sources:
            try:
                source_url = source_url.rstrip("/")
                if "/simple" not in source_url:
                    package_url = f"{source_url}/simple/{package_name}/"
                else:
                    package_url = f"{source_url}/{package_name}/"

                content = await self.download_client.download(package_url)
                if content:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(content, "html.parser")
                    versions = []

                    for link in soup.find_all("a"):
                        filename = link.string or link.get("href", "").split("/")[-1]
                        if filename:
                            # 从文件名中提取版本号
                            version_match = re.search(
                                rf"{package_name}-([^-]+)(?:\.tar\.gz|\.whl)$",
                                filename,
                                re.IGNORECASE,
                            )
                            if version_match:
                                version = version_match.group(1)
                                versions.append(
                                    PackageVersion(
                                        version=version,
                                        filename=filename,
                                        url=link.get("href", ""),
                                        requires_python=link.get(
                                            "data-requires-python"
                                        ),
                                        dist_info_metadata=link.get(
                                            "data-dist-info-metadata"
                                        ),
                                        core_metadata=link.get("data-core-metadata"),
                                    )
                                )

                    return versions

            except Exception as e:
                logger.error(f"Error getting versions from {source_url}: {e}")
                continue

        return []

    async def register_package(self, package_name: str, info: PackageInfo):
        """注册新包"""
        package_dir = os.path.join(self.storage_path, package_name)
        os.makedirs(package_dir, exist_ok=True)

        info_path = os.path.join(package_dir, "info.json")
        # 实现保存包信息的逻辑
        pass

    async def get_popular_packages(self, limit: int = 10) -> List[Dict]:
        """获取热门包列表"""
        # 临时返回一些示例数据
        return [
            {
                "name": "requests",
                "description": "Python HTTP for Humans",
                "downloads": 1000000,
                "latest_version": "2.31.0",
            },
            {
                "name": "flask",
                "description": "A lightweight WSGI web application framework",
                "downloads": 500000,
                "latest_version": "3.0.0",
            },
            {
                "name": "django",
                "description": "A high-level Python web framework",
                "downloads": 800000,
                "latest_version": "5.0.1",
            },
        ][:limit]

    async def get_statistics(self) -> Statistics:
        """获取统计信息"""
        # 这里应该从数据库获取真实数据
        return Statistics(
            total_packages=len(os.listdir(self.storage_path)),
            total_downloads=1000000,
            total_versions=2000,
            cache_hit_rate=85.5,
            storage_usage="1.2 GB",
        )

    async def search_packages(
        self, query: str, page: int = 1, page_size: int = 10
    ) -> PackageSearch:
        """搜索包"""
        # 这里应该实现真实的搜索逻辑
        results = []
        total = 0

        return PackageSearch(
            query=query, results=results, total=total, page=page, page_size=page_size
        )

    async def list_packages(self) -> List[str]:
        """列出所有可用的包名"""
        # 确保索引已初始化
        if not self._remote_index:
            await self.init_index()

        # 如果索引过期,异步更新
        if self._is_index_expired():
            logger.info("package.index.updating")
            await self.update_index()

        # 返回合并后的索引
        return sorted(self._local_index | self._remote_index)

    def get_python_requires(self, package_name: str, version: str) -> Optional[str]:
        """获取包的 Python 版本要求"""
        try:
            version_str = str(version)
            package_dir = os.path.join(self.storage_path, package_name, version_str)
            metadata_file = os.path.join(package_dir, "METADATA")
            if os.path.exists(metadata_file):
                with open(metadata_file, "r") as f:
                    for line in f:
                        if line.startswith("Requires-Python:"):
                            return line.split(":", 1)[1].strip()
            return None
        except Exception as e:
            logger.error(f"Error getting python requires: {e}")
            return None

    def get_upload_time(self, package_name: str, version: str) -> Optional[datetime]:
        """获取包的上传时间"""
        try:
            version_str = str(version)
            package_path = os.path.join(self.storage_path, package_name, version_str)
            if os.path.exists(package_path):
                timestamp = os.path.getmtime(package_path)
                return datetime.fromtimestamp(timestamp)
            return None
        except Exception as e:
            logger.error(f"Error getting upload time: {e}")
            return None

    def get_package_metadata(self, package_name: str, version: str) -> Dict[str, str]:
        """获取包的元数据"""
        try:
            # 确保 version 是字符串
            version_str = str(version)
            package_dir = os.path.join(self.storage_path, package_name, version_str)
            metadata_file = os.path.join(package_dir, "METADATA")
            metadata = {}

            if os.path.exists(metadata_file):
                with open(metadata_file, "r") as f:
                    current_key = None
                    current_value = []

                    for line in f:
                        if line.startswith(" ") and current_key:  # 继续多行值
                            current_value.append(line.strip())
                        elif ":" in line:  # 新的键值对
                            if current_key:  # 保存之前的键值对
                                metadata[current_key] = "\n".join(current_value)

                            key, value = line.split(":", 1)
                            current_key = key.strip()
                            current_value = [value.strip()]

                    if current_key:  # 保存最后一个键值对
                        metadata[current_key] = "\n".join(current_value)

            return metadata
        except Exception as e:
            logger.error(f"Error getting package metadata: {e}")
            return {}

    async def fetch_package_from_upstream(
        self, package_name: str, version: str, filename: str
    ) -> Optional[bytes]:
        """从上游源获取包"""
        for source_url in self.sources:
            try:
                source_url = source_url.rstrip("/")
                if "/simple" not in source_url:
                    package_url = (
                        f"{source_url}/simple/{package_name}/{version}/{filename}"
                    )
                else:
                    package_url = f"{source_url}/{package_name}/{version}/{filename}"

                content = await self.download_client.download(package_url)
                if content:
                    # 保存到本地存储
                    package_dir = os.path.join(self.storage_path, package_name, version)
                    os.makedirs(package_dir, exist_ok=True)

                    file_path = os.path.join(package_dir, filename)
                    with open(file_path, "wb") as f:
                        f.write(content)

                    return content

            except Exception as e:
                logger.error(f"Error fetching package from {source_url}: {e}")
                continue

        return None

    async def list_upstream_packages(self) -> List[str]:
        """从上游源获取包索引列表"""
        max_retries = 3
        retry_delay = 1  # 秒

        for source_url in self.sources:
            retries = 0
            while retries < max_retries:
                try:
                    source_url = source_url.rstrip("/")
                    if "/simple" not in source_url:
                        index_url = f"{source_url}/simple/"
                    else:
                        index_url = source_url

                    logger.info("packages.upstream.list.start", source=source_url)

                    content = await self.download_client.download(index_url)
                    if content:
                        from bs4 import BeautifulSoup

                        soup = BeautifulSoup(content, "html.parser")
                        packages = [
                            link.string for link in soup.find_all("a") if link.string
                        ]

                        logger.info(
                            "packages.upstream.list.success",
                            source=source_url,
                            count=len(packages),
                        )
                        return sorted(packages)
                except Exception as e:
                    retries += 1
                    if retries < max_retries:
                        logger.warning(
                            "packages.upstream.list.retry",
                            source=source_url,
                            attempt=retries,
                            error=str(e),
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(
                            "packages.upstream.list.failed",
                            source=source_url,
                            error=str(e),
                        )

        return []

    def get_index_status(self) -> Dict[str, Any]:
        """获取索引状态信息"""
        return {
            "last_update": self.last_index_update.isoformat()
            if self.last_index_update
            else None,
            "local_packages_count": len(self._local_index),
            "remote_packages_count": len(self._remote_index),
            "is_expired": self._is_index_expired(),
        }

    def clear_index(self):
        """清除索引缓存"""
        self._local_index.clear()
        self._remote_index.clear()
        self.last_index_update = None
        if self.index_file.exists():
            self.index_file.unlink()
