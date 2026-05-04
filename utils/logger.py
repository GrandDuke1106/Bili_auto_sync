# utils/logger.py
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"

def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # 核心日志文件，旧日志会自动被重命名为 sync.log.YYYY-MM-DD
    log_file = LOG_DIR / "sync.log"  

    logger = logging.getLogger("BiliSync")
    logger.setLevel(logging.INFO)

    # 定义包含时间戳的格式: [2026-05-04 13:00:44] 你的输出内容
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # 每天午夜切分，保留最近 30 天
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # 控制台输出
    original_stdout = sys.stdout
    console_handler = logging.StreamHandler(original_stdout)
    console_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    # 接管 print 函数，让所有常规输出都进入规范日志
    class PrintInterceptor:
        def write(self, message):
            msg = message.strip()
            if msg:
                logger.info(msg)
        def flush(self):
            pass

    sys.stdout = PrintInterceptor()
    sys.stderr = PrintInterceptor()
