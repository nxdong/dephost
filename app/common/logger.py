import logging
import sys
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory
from structlog.types import Processor


def add_service_name() -> Processor:
    """添加服务名称到日志"""

    def processor(logger: Any, name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        event_dict["service"] = "dephost"
        return event_dict

    return processor


def setup_logger():
    """配置结构化日志

    根据是否是TTY终端决定日志格式：
    - 当是TTY终端时（如命令行），输出易读的控制台格式
    - 当不是TTY终端时（如容器或重定向），输出JSON格式
    """
    # 配置标准库 logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        force=True,  # 强制重新配置
    )

    # 获取根记录器并设置级别
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 获取基础处理器
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_service_name(),
    ]

    # 根据是否是TTY终端选择渲染器
    if sys.stdout.isatty():
        # 终端环境：使用彩色格式化输出
        processors.extend(
            [
                structlog.dev.ConsoleRenderer(
                    colors=True,
                    exception_formatter=structlog.dev.default_exception_formatter,
                )
            ]
        )
    else:
        # 非终端环境：使用JSON格式
        processors.extend(
            [
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(indent=None),
            ]
        )

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


# 创建全局logger实例
logger = setup_logger()
