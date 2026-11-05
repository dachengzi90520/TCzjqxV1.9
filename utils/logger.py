"""错误日志记录器，支持 INFO/WARN/ERROR 三级日志"""
import os
from datetime import datetime


class ErrorLogger:
    def __init__(self, log_path: str):
        self.log_path = log_path
        self._file = open(log_path, "w", encoding="utf-8")
        self._closed = False

    def _write(self, level: str, msg: str):
        if self._closed:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {msg}\n"
        self._file.write(line)
        self._file.flush()

    def info(self, msg: str):
        self._write("INFO", msg)

    def warning(self, msg: str):
        self._write("WARN", msg)

    def error(self, msg: str):
        self._write("ERROR", msg)

    def close(self):
        if not self._closed:
            self._file.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
