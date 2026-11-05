import sys
sys.path.insert(0, '.')
import os
import tempfile
from utils.logger import ErrorLogger

def test_logger_writes_info():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "error.log")
        logger = ErrorLogger(log_path)
        logger.info("测试信息")
        logger.close()
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[INFO]" in content
        assert "测试信息" in content

def test_logger_writes_warn():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "error.log")
        logger = ErrorLogger(log_path)
        logger.warning("警告信息")
        logger.close()
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[WARN]" in content

def test_logger_writes_error():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "error.log")
        logger = ErrorLogger(log_path)
        logger.error("错误信息")
        logger.close()
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[ERROR]" in content

def test_logger_multiple_lines():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "error.log")
        logger = ErrorLogger(log_path)
        logger.info("第一行")
        logger.info("第二行")
        logger.close()
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) >= 2
