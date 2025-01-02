import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Set

from bs4 import BeautifulSoup

from app.common.download_client import DownloadClient
from app.common.logger import logger
from app.common.proxy_manager import ProxyManager
from app.settings import settings

from .schema import PackageVersion


class PyPIIndexManager:
    """PyPI 包索引管理器"""

    def __init__(self):
        """
        初始化索引管理器
        """
        self.settings = settings.pypi
        self.index_file = Path(self.settings.index_path) / "package_index.json"
        self._local_index: Set[str] = set()  # 本地包索引
        self._remote_index: Set[str] = set()  # 远程包索引
        self.cache_ttl = timedelta(
            seconds=self.settings.index_cache_ttl
        )  # 缓存过期时间
        self.last_index_update: Optional[datetime] = None  # 最后更新时间
        self.download_client = DownloadClient(ProxyManager())
        self.sources = self.settings.sources

    async def init_index(self):
        """初始化包索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    data = json.load(f)
                    self._local_index = set(data.get("local_packages", []))
                    self._remote_index = set(data.get("remote_packages", []))
                    self.last_index_update = (
                        datetime.fromisoformat(data["last_update"])
                        if data["last_update"]
                        else None
                    )
                    logger.info(
                        "package.index.loaded",
                        local_count=len(self._local_index),
                        remote_count=len(self._remote_index),
                    )
            except Exception as e:
                logger.error("package.index.load.failed", error=str(e))

    def is_index_expired(self) -> bool:
        """检查索引是否过期"""
        return (
            self.last_index_update is None
            or datetime.now() - self.last_index_update > self.cache_ttl
        )

    def update_remote_index(self, packages: Set[str]):
        """更新远程包索引"""
        self._remote_index = packages
        self.last_index_update = datetime.now()
        self._save_index()

    def update_local_index(self, package_name: str):
        """更新本地索引"""
        self._local_index.add(package_name)
        self._save_index()

    def remove_from_local_index(self, package_name: str):
        """从本地索引中移除包"""
        self._local_index.discard(package_name)
        self._save_index()

    def get_all_packages(self) -> Set[str]:
        """获取所有包名称"""
        return self._local_index | self._remote_index

    def _save_index(self):
        """保存索引到文件"""
        try:
            cache_data = {
                "last_update": self.last_index_update.isoformat()
                if self.last_index_update
                else None,
                "local_packages": list(self._local_index),
                "remote_packages": list(self._remote_index),
            }
            with open(self.index_file, "w") as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.error("package.index.save.failed", error=str(e))

    def get_index_status(self) -> dict:
        """获取索引状态"""
        return {
            "last_update": self.last_index_update.isoformat()
            if self.last_index_update
            else None,
            "local_packages_count": len(self._local_index),
            "remote_packages_count": len(self._remote_index),
            "is_expired": self.is_index_expired(),
        }

    def clear_index(self):
        """清除索引缓存"""
        self._local_index.clear()
        self._remote_index.clear()
        self.last_index_update = None
        if self.index_file.exists():
            self.index_file.unlink()

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

    async def update_index(self):
        """更新包索引"""
        try:
            packages = await self.list_upstream_packages()
            if packages:
                self.update_remote_index(set(packages))
                logger.info(
                    "package.index.updated",
                    local_count=len(self._local_index),
                    remote_count=len(self._remote_index),
                )
        except Exception as e:
            logger.error("package.index.update.failed", error=str(e))

    async def list_versions(self, package_name: str) -> List[PackageVersion]:
        """获取包版本列表"""
        versions = []
        package_name = package_name.lower()

        # 遍历所有源
        for source_url in self.sources:
            try:
                # 修改这里的URL构造逻辑
                source_url = source_url.rstrip("/")
                index_url = (
                    f"{source_url}/simple/{package_name}/"
                    if "/simple" not in source_url
                    else f"{source_url}/{package_name}/"
                )
                content = await self.download_client.download(index_url)

                if content:
                    soup = BeautifulSoup(content, "html.parser")
                    for link in soup.find_all("a"):
                        if not link.string:
                            continue

                        filename = link.string
                        url = link.get("href", "")
                        requires_python = link.get("data-requires-python")

                        version = PackageVersion(
                            version=filename.split("-")[1],
                            filename=filename,
                            url=url,
                            requires_python=requires_python,
                        )
                        versions.append(version)

                    logger.info(
                        "package.versions.list.success",
                        package=package_name,
                        source=source_url,
                        count=len(versions),
                    )
                    break

            except Exception as e:
                logger.error(
                    "package.versions.list.failed",
                    package=package_name,
                    source=source_url,
                    error=str(e),
                )

        return sorted(versions, key=lambda v: v.version, reverse=True)

    async def list_packages(self) -> List[str]:
        """获取所有包名称"""
        return sorted(self.get_all_packages())
