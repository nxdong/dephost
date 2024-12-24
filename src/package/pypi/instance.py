from src.settings import settings

from .service import PyPIService

pypi_service = PyPIService(storage_path=settings.storage_path)
