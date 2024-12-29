from contextlib import asynccontextmanager
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, Response

from app.common.logger import logger

from . import schema
from .cache import PyPICache
from .instance import pypi_service

router = APIRouter(prefix="/pypi")

# 初始化缓存
pypi_cache = PyPICache()
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化索引
    logger.info("Loading package index...")
    await pypi_service.init_index()

    # 设置定时刷新任务
    scheduler = AsyncIOScheduler()

    @scheduler.scheduled_job("interval", hours=1)
    async def refresh_index():
        logger.info("Refreshing package index...")
        await pypi_service.update_index()

    scheduler.start()
    yield
    scheduler.shutdown()


@router.get("/stats", response_model=schema.Statistics)
async def get_statistics():
    """获取统计信息"""
    return await pypi_service.get_statistics()


@router.get(
    "/simple",
    response_model=List[str],
    responses={404: {"description": "Package index not found"}},
)
async def get_simple_index():
    """获取包索引列表"""
    packages = await pypi_service.list_packages()
    return packages


@router.get("/simple/{package_name}/")
async def get_package_versions(package_name: str):
    # 首先检查缓存
    cached_versions = pypi_cache.get_package_versions(package_name)
    logger.info(f"cached_versions: {cached_versions}")
    if cached_versions is None:
        # 缓存未命中，从远程获取
        versions = await pypi_service.list_versions(package_name)
        # 更新缓存
        pypi_cache.update_package_versions(package_name, versions)
    else:
        versions = cached_versions

    logger.debug(f"package {package_name} versions: {versions}")
    # 构建版本列表
    version_items = []
    for version in versions:
        version_str = str(version.version)
        filename = version.filename
        requires_python = version.requires_python
        requires_python_attr = (
            f'data-requires-python="{requires_python}"' if requires_python else ""
        )

        version_item = f"""
            <a href="/pypi/packages/{package_name}/{version_str}/{filename}"
               {requires_python_attr}>
                {filename}
            </a><br/>
        """
        version_items.append(version_item)

    # 构建完整的HTML
    html_content = f"""
<!DOCTYPE html>
<html>
    <head>
        <meta name="pypi:repository-version" content="1.0">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="generator" content="private-pypi-server">
        <title>Links for {package_name}</title>
    </head>
    <body>
        <h1>Links for {package_name}</h1>
        {''.join(version_items)}
    </body>
</html>
    """.strip()

    return HTMLResponse(
        content=html_content,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "X-PyPI-Last-Serial": str(pypi_cache.get_serial(package_name)),
            "Cache-Control": "max-age=3600",
        },
    )


@router.get("/packages/{package_name}/{version}/{filename}")
async def get_package_file(package_name: str, version: str, filename: str):
    """获取包文件"""
    content = await pypi_service.get_package(package_name, version, filename)

    if content is None:
        # 如果本地没有，尝试从上游获取
        content = await pypi_service.fetch_package_from_upstream(
            package_name, version, filename
        )
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Package file not found: {package_name}-{version}",
            )

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/x-gzip",
        },
    )
