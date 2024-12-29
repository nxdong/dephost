from typing import Optional

import aiohttp

from app.common.logger import logger
from app.proxy.manager import ProxyManager


class DownloadClient:
    def __init__(self, proxy_manager: ProxyManager):
        self.proxy_manager = proxy_manager

    async def download(self, url: str) -> Optional[bytes]:
        """下载文件"""
        proxy = self.proxy_manager.get_proxy(url)
        proxy_url = proxy.http_proxy if proxy else None

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, proxy=proxy_url) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.error(f"Download failed: {url}, status: {response.status}")
                    return None
            except Exception as e:
                logger.error(f"Download error: {url}, error: {e!s}")
                return None
