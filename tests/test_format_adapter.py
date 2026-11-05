"""V1.7 新版逐卡格式适配层测试"""
import sys
import os
import tempfile
sys.path.insert(0, '.')
import pandas as pd
from core.format_adapter import (
    is_new_format, normalize_detail_card_cols, adapt_new_format
)


def _make_zip(path, member_names):
    """构造一个仅含指定成员名的 zip（成员内容可为空）。"""
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        for name in member_names:
            z.writestr(name, "")
    return path


def test_is_new_format_true():
    """含新版逐卡明细 zip → True"""
    with tempfile.TemporaryDirectory() as d:
        zp = _make_zip(
            os.path.join(d, "案件.zip"),
            ["中国农业银行交易明细信息(6228411333029998167).zip", "北京银行账户信息.zip"],
        )
        assert is_new_format([zp]) is True


def test_is_new_format_false():
    """纯旧版文件名 → False"""
    with tempfile.TemporaryDirectory() as d:
        zp = _make_zip(
            os.path.join(d, "案件.zip"),
            ["莱商银行股份有限公司交易明细信息.zip", "北京银行账户信息.zip"],
        )
        assert is_new_format([zp]) is False


def test_is_new_format_dash_card_is_false():
    """括号内为 '-' 视为无卡号 → 不判定为新版"""
    with tempfile.TemporaryDirectory() as d:
        zp = _make_zip(
            os.path.join(d, "案件.zip"),
            ["中国光大银行股份有限公司交易明细信息(-).zip"],
        )
        assert is_new_format([zp]) is False


def test_normalize_detail_card_cols_fills_empty():
    """文件名卡号补全为空的 交易卡号/交易账号"""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "中国农业银行交易明细信息(6228411333029998167).csv")
        df = pd.DataFrame({
            "交易卡号": ["", "6228411333029998167"],
            "交易账号": ["", ""],
            "交易金额": ["1", "2"],
        })
        df.to_csv(p, index=False, encoding="utf-8-sig")
        filled = normalize_detail_card_cols(p, "6228411333029998167")
        # 只补为空的"交易卡号"（第1行），"交易账号"不属于卡号，不补
        assert filled == 1
        out = pd.read_csv(p, dtype=str, keep_default_na=False)
        assert out.loc[0, "交易卡号"] == "6228411333029998167"
        assert out.loc[1, "交易卡号"] == "6228411333029998167"
        assert out.loc[0, "交易账号"] == ""


def test_adapt_new_format_noop_without_card():
    """无卡号（补全卡号空）→ 不影响数据"""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "莱商银行股份有限公司交易明细信息.csv")
        df = pd.DataFrame({"交易卡号": ["1"], "交易账号": ["2"]})
        df.to_csv(p, index=False, encoding="utf-8-sig")
        filled = adapt_new_format({"交易明细信息": [("莱商银行", p)]})
        assert filled == 0


def test_adapt_new_format_fills():
    """逐卡明细用文件名卡号补全空单元格"""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "中国农业银行交易明细信息(6228411333029998167).csv")
        df = pd.DataFrame({"交易卡号": [""], "交易账号": ["111"], "交易金额": ["1"]})
        df.to_csv(p, index=False, encoding="utf-8-sig")
        filled = adapt_new_format({"交易明细信息": [("中国农业银行", p)]})
        assert filled == 1
        out = pd.read_csv(p, dtype=str, keep_default_na=False)
        assert out.loc[0, "交易卡号"] == "6228411333029998167"
