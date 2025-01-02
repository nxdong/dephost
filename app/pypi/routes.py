from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.common.logger import logger

from . import schema
from .instance import pypi_service

# 初始化路由和模板
api_router = APIRouter(prefix="/pypi")
web_router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

# 初始化调度器
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Loading package index...")
    await pypi_service.init_index()

    @scheduler.scheduled_job("interval", hours=1)
    async def refresh_index():
        logger.info("Refreshing package index...")
        await pypi_service.update_index()

    scheduler.start()
    yield
    scheduler.shutdown()


# API 路由
@api_router.get("/stats", response_model=schema.Statistics)
async def get_statistics():
    """获取统计信息"""
    return await pypi_service.get_statistics()


@api_router.get(
    "/simple",
    response_model=List[str],
    responses={404: {"description": "Package index not found"}},
)
async def get_simple_index():
    """获取包索引列表"""
    packages = await pypi_service.index_manager.list_packages()
    return packages


@api_router.get("/simple/{package_name}/")
async def get_package_versions(package_name: str):
    """获取包版本列表"""
    versions = await pypi_service.index_manager.list_versions(package_name)
    if not versions:
        raise HTTPException(status_code=404, detail="Package not found")

    return _build_version_html(package_name, versions)


@api_router.get("/packages/{package_name}/{version}/{filename}")
async def get_package_file(package_name: str, version: str, filename: str):
    """获取包文件"""
    content = await pypi_service.package_manager.get_package(
        package_name, version, filename
    )
    if not content:
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


# Web 路由
@web_router.get("/")
async def index(request: Request):
    """首页"""
    popular_packages = await pypi_service.get_popular_packages(limit=6)
    stats = await pypi_service.get_statistics()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "popular_packages": popular_packages,
            "stats": stats,
        },
    )


@web_router.get("/search")
async def search(request: Request, q: str):
    """搜索页面"""
    packages = await pypi_service.search_packages(q)
    return templates.TemplateResponse(
        "search.html", {"request": request, "query": q, "packages": packages}
    )


@web_router.get("/help")
async def help_page(request: Request):
    """帮助页面"""
    return templates.TemplateResponse("help.html", {"request": request})


@web_router.get("/package/{package_name}")
async def package_detail(request: Request, package_name: str):
    """包详情页面"""
    package = await pypi_service.get_package_info(package_name)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return templates.TemplateResponse(
        "package_detail.html", {"request": request, "package": package}
    )


def _build_version_html(
    package_name: str, versions: List[schema.PackageVersion]
) -> HTMLResponse:
    """构建版本列表HTML"""
    version_items = []
    for version in versions:
        version_str = str(version.version)
        filename = version.filename
        requires_python = version.requires_python
        requires_python_attr = (
            f'data-requires-python="{requires_python}"' if requires_python else ""
        )
        version_items.append(
            f'<a href="/pypi/packages/{package_name}/{version_str}/{filename}" '
            f"{requires_python_attr}>{filename}</a><br/>"
        )

    html_content = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta name="pypi:repository-version" content="1.0">
            <meta name="viewport" content="width=device-width, initial-scale=1">
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
            "Cache-Control": "max-age=3600",
        },
    )
