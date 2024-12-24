from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # 基础配置
    BASE_DIR: Path = Path(__file__).parent
    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    PACKAGES_DIR: Path = BASE_DIR / "packages"
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # 数据库配置（如果需要）
    DATABASE_URL: str = "sqlite:///./pypi.db"
    
    class Config:
        env_file = ".env"

settings = Settings() 