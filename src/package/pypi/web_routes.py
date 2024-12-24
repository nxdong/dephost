from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from .instance import pypi_service

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")


@router.get("/")
async def index(request: Request):
    # 获取热门包和统计信息
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


@router.get("/search")
async def search(request: Request, q: str):
    packages = await pypi_service.search_packages(q)
    return templates.TemplateResponse(
        "search.html", {"request": request, "query": q, "packages": packages}
    )


@router.get("/help")
async def help_page(request: Request):
    return templates.TemplateResponse("help.html", {"request": request})


@router.get("/package/{package_name}")
async def package_detail(request: Request, package_name: str):
    package = await pypi_service.get_package_info(package_name)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return templates.TemplateResponse(
        "package_detail.html", {"request": request, "package": package}
    )


@router.get("/upload")
async def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})
