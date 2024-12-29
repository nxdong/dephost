from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from pydantic import BaseModel

from .schema import PackageVersion


class PackageCache(BaseModel):
    versions: List[PackageVersion]
    last_updated: datetime


class PyPICache:
    def __init__(self):
        self.packages: Dict[str, PackageCache] = {}
        self.cache_ttl = timedelta(hours=1)
        self.serial_counter = 0
        # 新增：包索引缓存
        self._local_index: Set[str] = set()
        self._remote_index: Set[str] = set()
        self._index_last_updated: Optional[datetime] = None
    
    def update_local_index(self, packages: List[str]) -> None:
        """更新本地包索引"""
        self._local_index = set(packages)
        self._index_last_updated = datetime.now()
    
    def update_remote_index(self, packages: List[str]) -> None:
        """更新远程包索引"""
        self._remote_index = set(packages)
        self._index_last_updated = datetime.now()
    
    def get_merged_index(self) -> List[str]:
        """获取合并后的包索引列表"""
        return sorted(self._local_index | self._remote_index)
    
    def get_index_last_updated(self) -> Optional[datetime]:
        """获取索引最后更新时间"""
        return self._index_last_updated
    
    def is_index_expired(self) -> bool:
        """检查索引是否过期"""
        if not self._index_last_updated:
            return True
        return datetime.now() - self._index_last_updated > self.cache_ttl

    def get_package_versions(self, package_name: str) -> Optional[List[PackageVersion]]:
        if package_name not in self.packages:
            return None

        cache_entry = self.packages[package_name]
        if datetime.now() - cache_entry.last_updated > self.cache_ttl:
            return None

        return cache_entry.versions

    def update_package_versions(
        self, package_name: str, versions: List[PackageVersion]
    ):
        self.packages[package_name] = PackageCache(
            versions=versions, last_updated=datetime.now()
        )

    def get_last_updated(self, package_name: str) -> Optional[datetime]:
        """获取包的最后更新时间"""
        if package_name in self.packages:
            return self.packages[package_name].last_updated
        return None

    def get_serial(self, package_name: str) -> int:
        """获取包的序列号"""
        if package_name in self.packages:
            self.serial_counter += 1
            return self.serial_counter
        return 0
