from typing import Any, Dict
from urllib.parse import quote

from .index_manager import PyPIIndexManager
from .package_manager import PackageManager


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
        self.index_manager = PyPIIndexManager()
        self.package_manager = PackageManager()

    async def init_index(self):
        """初始化包索引"""
        await self.index_manager.init_index()
        if (
            not self.index_manager.get_all_packages()
            or self.index_manager.is_index_expired()
        ):
            await self.index_manager.update_index()

    def get_index_status(self) -> Dict[str, Any]:
        """获取索引状态"""
        return self.index_manager.get_index_status()

    def clear_index(self):
        """清除索引缓存"""
        self.index_manager.clear_index()
