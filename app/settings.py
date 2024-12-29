import os
from typing import Dict, List

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProxySettings(BaseModel):
    """代理服务器配置"""

    http_proxy: str | None = None
    https_proxy: str | None = None
    socks5_proxy: str | None = None


class CacheSettings(BaseModel):
    """缓存配置"""

    max_size_gb: float = Field(default=10.0, ge=0)  # 最大缓存大小（GB）
    min_free_space_gb: float = Field(default=5.0, ge=0)  # 最小剩余空间（GB）
    cleanup_interval_hours: int = Field(default=24, ge=1)  # 清理间隔（小时）
    file_ttl_days: int = Field(default=30, ge=1)  # 文件保存时间（天）


class PyPISettings(BaseModel):
    """PyPI 源配置"""

    sources: List[str] = [
        "https://pypi.org/simple/",
        # "https://mirrors.aliyun.com/pypi/simple/",
        # "https://pypi.tuna.tsinghua.edu.cn/simple/",
    ]
    timeout_seconds: int = 30
    max_retries: int = 3
    index_update_interval: int = 3600  # 索引更新间隔（秒）
    index_cache_ttl: int = 3600  # 索引缓存过期时间（秒）


class UbuntuSettings(BaseModel):
    """Ubuntu 源配置"""

    sources: List[str] = [
        "http://archive.ubuntu.com/ubuntu/",
        "https://mirrors.aliyun.com/ubuntu/",
        "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/",
    ]
    timeout_seconds: int = 30
    max_retries: int = 3


class Settings(BaseSettings):
    """应用程序配置"""

    # 基本设置
    name: str = "PyPI Server"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    # 存储路径
    storage_path: str = "./storage"

    # 缓存目录
    cache_dir: str = "./cache"

    # 各模块配置
    cache: CacheSettings = CacheSettings()
    pypi: PyPISettings = PyPISettings()
    ubuntu: UbuntuSettings = UbuntuSettings()

    # 代理配置
    # 格式: {"domain": ProxySettings}
    proxies: Dict[str, ProxySettings] = {}

    class Config:
        env_prefix = "DEPHOST_"  # 环境变量前缀
        env_file = ".env"  # 环境变量文件

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保必要的目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.storage_path, exist_ok=True)

        # 创建各个包类型的缓存目录
        os.makedirs(os.path.join(self.cache_dir, "pypi"), exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, "ubuntu"), exist_ok=True)


# 创建全局设置实例
settings = Settings()
