from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup
from fastapi import HTTPException

from app.common.logger import logger
from app.settings import settings

from .download_client import DownloadClient
from .index_manager import PyPIIndexManager
from .proxy_manager import ProxyManager


def normalize_package_name(package_name: str) -> str:
    """标准化包名"""
    return package_name.lower().replace("_", "-").replace(" ", "-")


def normalize_package_path(package_name: str) -> str:
    """标准化包路径"""
    normalized = normalize_package_name(package_name)
    return quote(normalized)


def normalize_filename(filename: str) -> str:
    """标准化文件名"""
    name_parts = filename.rsplit(".", 2)
    if len(name_parts) > 1:
        base_name = name_parts[0]
        extensions = ".".join(name_parts[1:])
        normalized_base = base_name.replace("_", "-")
        normalized = f"{normalized_base}.{extensions}"
    else:
        normalized = filename.replace("_", "-")
    return quote(normalized)


class PyPIService:
    def __init__(self):
        """初始化 PyPI 服务"""
        self.settings = settings.pypi
        self.storage_path = Path(self.settings.packages_path)
        self.download_client = DownloadClient(ProxyManager())
        self.sources = settings.pypi.sources
        self.index_manager = PyPIIndexManager(settings.pypi.index_path)
        self.cache_ttl = timedelta(seconds=settings.pypi.index_cache_ttl)

        # 确保存储目录存在
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def init_index(self):
        """初始化包索引"""
        await self.index_manager.init_index()
        if (
            not self.index_manager.get_all_packages()
            or self.index_manager.is_index_expired()
        ):
            await self.update_index()

    async def update_index(self):
        """更新包索引"""
        try:
            packages = await self.list_upstream_packages()
            if packages:
                self.index_manager.update_remote_index(set(packages))
                logger.info(
                    "package.index.updated",
                    local_count=len(self.index_manager._local_index),
                    remote_count=len(self.index_manager._remote_index),
                )
        except Exception as e:
            logger.error("package.index.update.failed", error=str(e))

    async def get_package(
        self, package_name: str, version: str, filename: str
    ) -> bytes:
        """获取包文件内容"""
        normalized_name = normalize_package_name(package_name)
        normalized_filename = normalize_filename(filename)
        package_path = (
            self.storage_path / normalized_name / version / normalized_filename
        )

        # 检查本地缓存
        if package_path.exists():
            return package_path.read_bytes()

        # 从远程源下载
        content = await self._download_from_sources(package_name, version, filename)
        if content:
            # 保存到本地缓存
            package_path.parent.mkdir(parents=True, exist_ok=True)
            package_path.write_bytes(content)
            return content

        raise HTTPException(
            status_code=404,
            detail=f"Package {package_name} version {version} not found",
        )

    async def _download_from_sources(
        self, package_name: str, version: str, filename: str
    ) -> Optional[bytes]:
        """从源站下载包文件"""
        normalized_path = normalize_package_path(package_name)

        for source_url in self.sources:
            try:
                source_url = source_url.rstrip("/")
                if "/simple" in source_url:
                    # 处理 simple API
                    index_url = f"{source_url}/{normalized_path}/"
                    index_content = await self.download_client.download(index_url)
                    if not index_content:
                        continue

                    soup = BeautifulSoup(index_content, "html.parser")
                    file_url = None
                    for link in soup.find_all("a"):
                        link_text = link.string if link.string else ""
                        normalized_link = link_text.replace("_", "-")
                        if (
                            normalized_link
                            and normalize_filename(filename) in normalized_link
                        ):
                            file_url = link.get("href")
                            break

                    if not file_url:
                        continue
                else:
                    # 标准 PyPI API
                    file_url = (
                        f"{source_url}/packages/{normalized_path}/{version}/{filename}"
                    )

                logger.info(
                    "package.download.start",
                    package=package_name,
                    version=version,
                    source=source_url,
                )

                content = await self.download_client.download(file_url)
                if content:
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

        return None

    async def list_upstream_packages(self) -> List[str]:
        """获取上游源的包列表"""
        max_retries = 3
        retry_delay = 1

        for source_url in self.sources:
            retries = 0
            while retries < max_retries:
                try:
                    source_url = source_url.rstrip("/")
                    index_url = (
                        f"{source_url}/simple/"
                        if "/simple" not in source_url
                        else source_url
                    )

                    logger.info("packages.upstream.list.start", source=source_url)
                    content = await self.download_client.download(index_url)

                    if content:
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

    async def list_packages(self) -> List[str]:
        """获取所有可用的包列表"""
        if not self.index_manager.get_all_packages():
            await self.init_index()

        if self.index_manager.is_index_expired():
            logger.info("package.index.updating")
            await self.update_index()

        return sorted(self.index_manager.get_all_packages())

    def get_index_status(self) -> Dict[str, Any]:
        """获取索引状态"""
        return self.index_manager.get_index_status()

    def clear_index(self):
        """清除索引缓存"""
        self.index_manager.clear_index()
