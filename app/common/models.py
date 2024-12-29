from typing import Optional

from pydantic import BaseModel


class ProxyConfig(BaseModel):
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
