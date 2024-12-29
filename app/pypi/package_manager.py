from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from app.common.download.client import DownloadClient
from app.common.logger import logger
from app.common.proxy.manager import ProxyManager
from app.settings import settings


class PackageManager:
    """包文件管理器"""

    def __init__(self):
        """初始化包管理器"""
        self.settings = settings.pypi
        self.storage_path = Path(self.settings.packages_path)
        self.download_client = DownloadClient(ProxyManager())

        # 确保存储目录存在
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def normalize_package_name(self, package_name: str) -> str:
        """标准化包名"""
        return package_name.lower().replace("_", "-").replace(" ", "-")

    def normalize_filename(self, filename: str) -> str:
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

    def get_package_path(self, package_name: str, version: str, filename: str) -> Path:
        """获取包文件的本地存储路径"""
        normalized_name = self.normalize_package_name(package_name)
        normalized_filename = self.normalize_filename(filename)
        return self.storage_path / normalized_name / version / normalized_filename

    async def download_package(self, url: str, save_path: Path) -> Optional[bytes]:
        """下载包文件并保存到本地"""
        try:
            content = await self.download_client.download(url)
            if content:
                # 确保目录存在
                save_path.parent.mkdir(parents=True, exist_ok=True)
                # 保存文件
                save_path.write_bytes(content)
                logger.info("package.download.success", url=url, path=str(save_path))
                return content
        except Exception as e:
            logger.error("package.download.failed", url=url, error=str(e))
        return None

    def get_package_file(
        self, package_name: str, version: str, filename: str
    ) -> Optional[bytes]:
        """获取本地包文件内容"""
        file_path = self.get_package_path(package_name, version, filename)
        if file_path.exists():
            return file_path.read_bytes()
        return None

    def save_package_file(
        self, package_name: str, version: str, filename: str, content: bytes
    ):
        """保存包文件到本地"""
        file_path = self.get_package_path(package_name, version, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

    def delete_package(self, package_name: str, version: str) -> bool:
        """删除包文件"""
        package_dir = (
            self.storage_path / self.normalize_package_name(package_name) / version
        )
        if package_dir.exists():
            try:
                for file in package_dir.iterdir():
                    file.unlink()
                package_dir.rmdir()
                # 如果版本目录是空的,删除包目录
                version_dir = package_dir.parent
                if not any(version_dir.iterdir()):
                    version_dir.rmdir()
                return True
            except Exception as e:
                logger.error(
                    "package.delete.failed",
                    package=package_name,
                    version=version,
                    error=str(e),
                )
        return False

    def get_package_info(self, package_name: str, version: str) -> dict:
        """获取包文件信息"""
        file_path = self.get_package_path(
            package_name, version, f"{package_name}-{version}.tar.gz"
        )
        if file_path.exists():
            return {
                "size": file_path.stat().st_size,
                "created_time": datetime.fromtimestamp(file_path.stat().st_ctime),
                "modified_time": datetime.fromtimestamp(file_path.stat().st_mtime),
            }
        return {}

    def list_versions(self, package_name: str) -> list[str]:
        """列出包的所有版本"""
        package_dir = self.storage_path / self.normalize_package_name(package_name)
        if package_dir.exists():
            return [d.name for d in package_dir.iterdir() if d.is_dir()]
        return []

    def cleanup_old_files(self, max_age_days: int = 30):
        """清理过期的包文件"""
        now = datetime.now()
        for package_dir in self.storage_path.iterdir():
            if not package_dir.is_dir():
                continue

            for version_dir in package_dir.iterdir():
                if not version_dir.is_dir():
                    continue

                for file_path in version_dir.iterdir():
                    if not file_path.is_file():
                        continue

                    file_age = now - datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_age.days > max_age_days:
                        try:
                            file_path.unlink()
                            logger.info("package.cleanup.deleted", path=str(file_path))
                        except Exception as e:
                            logger.error(
                                "package.cleanup.failed",
                                path=str(file_path),
                                error=str(e),
                            )
