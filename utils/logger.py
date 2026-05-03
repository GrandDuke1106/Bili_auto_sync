# utils/logger.py
import sys
import os
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"

class DualLogger(object):
    def __init__(self, filename="sync_log.txt"):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        # 生成带时间戳的日志文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.terminal = sys.stdout
        self.log_file = open(LOG_DIR / f"run_{timestamp}_{filename}", "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

def setup_logger():
    """将标准输出重定向到 DualLogger"""
    sys.stdout = DualLogger()
    # 也可以重定向 stderr
    sys.stderr = sys.stdout
