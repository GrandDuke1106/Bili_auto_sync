# utils/logger.py — 日志系统初始化
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"


def setup_logger():
    """初始化日志系统。

    - 日志文件按天轮转，保留 30 天。
    - 通过 PrintInterceptor 接管 stdout/stderr，使所有 print() 输出
      自动进入日志（同时保留控制台回显）。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "sync.log"

    logger = logging.getLogger("BiliSync")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    class PrintInterceptor:
        """将 print 调用重定向到 logger.info，实现 stdout/stderr 统一管理。"""
        def write(self, message):
            msg = message.strip()
            if msg:
                logger.info(msg)

        def flush(self):
            pass

    sys.stdout = PrintInterceptor()
    sys.stderr = PrintInterceptor()
