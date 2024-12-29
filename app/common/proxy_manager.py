from typing import Dict, Optional
from urllib.parse import urlparse

from app.settings import ProxySettings


class ProxyManager:
    def __init__(self):
        self.proxies: Dict[str, ProxySettings] = {}

    def add_proxy(self, source_url: str, proxy_url: str):
        """为源添加代理"""
        domain = urlparse(source_url).netloc
        self.proxies[domain] = ProxySettings(
            http_proxy=proxy_url, https_proxy=proxy_url
        )

    def get_proxy(self, url: str) -> Optional[ProxySettings]:
        """获取URL对应的代理配置"""
        domain = urlparse(url).netloc
        return self.proxies.get(domain)
