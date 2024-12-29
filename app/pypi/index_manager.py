import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set

from app.common.logger import logger


class PyPIIndexManager:
    """PyPI 包索引管理器"""

    def __init__(self, index_path: str):
        """
        初始化索引管理器

        Args:
            index_path: 索引文件路径
        """
        self.index_file = Path(index_path) / "package_index.json"
        self._local_index: Set[str] = set()  # 本地包索引
        self._remote_index: Set[str] = set()  # 远程包索引
        self.cache_ttl = timedelta(hours=1)  # 缓存过期时间
        self.last_index_update: Optional[datetime] = None  # 最后更新时间

    async def init_index(self):
        """初始化包索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    data = json.load(f)
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
                "last_update": self.last_index_update.isoformat(),
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
