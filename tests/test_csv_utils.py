import sys
sys.path.insert(0, '.')
import os
import tempfile
import pandas as pd
from utils.csv_utils import (
    detect_delimiter, read_csv_auto, normalize_column_names, sanitize_excel_string
)

def test_detect_delimiter_comma():
    content = "姓名,年龄,城市\n张三,30,北京\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        assert detect_delimiter(path) == ","
    finally:
        os.unlink(path)

def test_detect_delimiter_tab():
    content = "姓名\t年龄\t城市\n张三\t30\t北京\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        assert detect_delimiter(path) == "\t"
    finally:
        os.unlink(path)

def test_read_csv_auto_basic():
    content = " 姓名 , 年龄 , 城市 \n 张三 , 30 , 北京 \n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        df = read_csv_auto(path)
        assert list(df.columns) == ["姓名", "年龄", "城市"]
        assert len(df) == 1
        assert df.iloc[0]["姓名"] == "张三"
    finally:
        os.unlink(path)

def test_read_csv_auto_strips_whitespace():
    content = "姓名,年龄\n  张三  ,  30  \n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        df = read_csv_auto(path)
        assert df.iloc[0]["姓名"] == "张三"
        assert df.iloc[0]["年龄"] == "30"
    finally:
        os.unlink(path)

def test_read_csv_auto_removes_illegal_xml_chars():
    """V1.5: 数据含 \\x1c 等 Excel 非法控制字符时自动移除"""
    content = "交易对手账号\x1c户名,备注\n7C04\x1cJSV91,正常\x0b值\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        df = read_csv_auto(path)
        assert list(df.columns) == ["交易对手账号户名", "备注"]
        assert df.iloc[0]["交易对手账号户名"] == "7C04JSV91"
        assert df.iloc[0]["备注"] == "正常值"
    finally:
        os.unlink(path)


def test_sanitize_excel_string_removes_control_chars():
    """V1.6: 20260817 光大银行反馈数据中的 \\x10 控制字符必须被清除"""
    # 生产真实场景：交易对手户名 = base64串 + 16个 \x10 + 中文
    raw = "AW8BAGYFokXSyvkpZwrs-GMi0z7Vvmy8" + "\x10" * 16 + "司"
    cleaned = sanitize_excel_string(raw)
    assert cleaned == "AW8BAGYFokXSyvkpZwrs-GMi0z7Vvmy8司"
    assert "\x10" not in cleaned

    # 覆盖 openpyxl 全部非法范围：\x00-\x08 \x0b \x0c \x0e-\x1f
    for ch in ["\x00", "\x08", "\x0b", "\x0c", "\x0e", "\x1f", "\x1c"]:
        assert sanitize_excel_string(f"a{ch}b") == "ab"

    # 合法字符（tab/LF/CR）保留
    assert sanitize_excel_string("a\tb\nc\rd") == "a\tb\nc\rd"


def test_normalize_column_names():
    df = pd.DataFrame({" 姓名 ": [1], "年龄\n": [2]})
    result = normalize_column_names(df)
    assert "姓名" in result.columns
    assert "年龄" in result.columns
