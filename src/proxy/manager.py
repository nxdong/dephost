from typing import Dict
from typing import Optional
from urllib.parse import urlparse

from src.common.models import ProxyConfig


class ProxyManager:
    def __init__(self):
        self.proxies: Dict[str, ProxyConfig] = {}

    def add_proxy(self, source_url: str, proxy_url: str):
        """为源添加代理"""
        domain = urlparse(source_url).netloc
        self.proxies[domain] = ProxyConfig(http_proxy=proxy_url, https_proxy=proxy_url)

    def get_proxy(self, url: str) -> Optional[ProxyConfig]:
        """获取URL对应的代理配置"""
        domain = urlparse(url).netloc
        return self.proxies.get(domain)
