import sys
sys.path.insert(0, '.')
import os
import tempfile
from utils.encoding import detect_encoding

def test_detect_utf8():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", encoding="utf-8", delete=False) as f:
        f.write("姓名,年龄\n张三,30\n")
        path = f.name
    try:
        enc = detect_encoding(path)
        assert "utf" in enc.lower() or enc.lower() == "ascii"
    finally:
        os.unlink(path)

def test_detect_gbk():
    content = "姓名,年龄\n张三,30\n"
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
        f.write(content.encode("gbk"))
        path = f.name
    try:
        enc = detect_encoding(path)
        assert "gb" in enc.lower() or "gbk" in enc.lower() or "gb2312" in enc.lower()
    finally:
        os.unlink(path)

def test_detect_empty_file_fallback():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", encoding="utf-8", delete=False) as f:
        f.write("")
        path = f.name
    try:
        enc = detect_encoding(path)
        assert enc == "gbk"
    finally:
        os.unlink(path)
