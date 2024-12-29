from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.pypi.routes import lifespan
from app.pypi.routes import router as api_router  # API路由，如果有的话
from app.pypi.web_routes import router as web_router
from app.settings import settings

app = FastAPI(title=settings.name, lifespan=lifespan)

# CORS设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "home" / "static"),
    name="static",
)

# 注册路由
app.include_router(web_router, tags=["web"])
app.include_router(api_router, tags=["pypi"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
