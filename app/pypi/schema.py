from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class PackageBase(BaseModel):
    """包的基础信息"""

    name: str = Field(..., description="包名称")
    version: str = Field(..., description="包版本")
    description: Optional[str] = Field(None, description="包描述")


class PackageCreate(PackageBase):
    """创建包时的输入模型"""

    author: Optional[str] = Field(None, description="作者")
    author_email: Optional[EmailStr] = Field(None, description="作者邮箱")
    homepage: Optional[HttpUrl] = Field(None, description="项目主页")
    license: Optional[str] = Field(None, description="许可证")
    requires_python: Optional[str] = Field(None, description="Python版本要求")
    keywords: Optional[List[str]] = Field(default=[], description="关键词")


class PackageVersion(BaseModel):
    """包版本信息"""

    version: str = Field(..., description="版本号")
    upload_time: datetime = Field(default_factory=datetime.now, description="上传时间")
    size: Optional[int] = 0
    downloads: int = Field(default=0, description="下载次数")
    filename: str = Field(..., description="文件名")
    sha256_digest: Optional[str] = None
    version: str
    filename: str
    url: str
    requires_python: Optional[str] = None
    sha256: Optional[str] = None
    dist_info_metadata: Optional[str] = None
    core_metadata: Optional[str] = None


class PackageInfo(PackageBase):
    """包的完整信息"""

    author: Optional[str] = None
    author_email: Optional[EmailStr] = None
    homepage: Optional[HttpUrl] = None
    license: Optional[str] = None
    requires_python: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    versions: List[PackageVersion] = Field(default_factory=list)
    total_downloads: int = Field(default=0, description="总下载次数")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PackageList(BaseModel):
    """包列表响应"""

    packages: List[PackageInfo]
    total: int
    page: int = 1
    page_size: int = 10


class PackageSearch(BaseModel):
    """搜索结果"""

    query: str
    results: List[PackageInfo]
    total: int
    page: int = 1
    page_size: int = 10


class Statistics(BaseModel):
    """统计信息"""

    total_packages: int = Field(..., description="包总数")
    total_downloads: int = Field(..., description="总下载次数")
    total_versions: int = Field(..., description="版本总数")
    cache_hit_rate: float = Field(..., description="缓存命中率")
    storage_usage: str = Field(..., description="存储使用量")


class Message(BaseModel):
    """消息提示"""

    type: str = Field(..., description="消息类型: success, info, warning, error")
    text: str = Field(..., description="消息内容")


class UploadResponse(BaseModel):
    """上传响应"""

    success: bool
    message: str
    package_info: Optional[PackageInfo] = None
