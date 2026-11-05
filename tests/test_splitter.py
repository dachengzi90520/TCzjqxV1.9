import sys
sys.path.insert(0, '.')
import os
import tempfile
import pandas as pd
from core.splitter import split_by_account


def test_split_creates_files():
    with tempfile.TemporaryDirectory() as tmp:
        detail_path = os.path.join(tmp, "交易明细信息_合并.csv")
        df = pd.DataFrame({
            "银行来源": ["工商银行", "工商银行", "建设银行"],
            "交易户名": ["张三", "李四", ""],
            "交易卡号": ["C001", "C002", "C003"],
            "交易金额": ["100", "200", "300"],
        })
        df.to_csv(detail_path, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "分表")
        files = split_by_account(detail_path, output_dir)

        assert len(files) == 3
        assert os.path.exists(os.path.join(output_dir, "张三_工商银行_C001.xlsx"))
        assert os.path.exists(os.path.join(output_dir, "李四_工商银行_C002.xlsx"))
        assert os.path.exists(os.path.join(output_dir, "C003_建设银行_C003.xlsx"))


def test_split_single_person():
    with tempfile.TemporaryDirectory() as tmp:
        detail_path = os.path.join(tmp, "交易明细信息_合并.csv")
        df = pd.DataFrame({
            "银行来源": ["招商银行"],
            "交易户名": ["王五"],
            "交易卡号": ["C001"],
            "交易金额": ["500"],
        })
        df.to_csv(detail_path, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "分表")
        files = split_by_account(detail_path, output_dir)

        assert len(files) == 1
        result = pd.read_excel(files[0], dtype=str)
        assert len(result) == 1
        assert result.iloc[0]["交易金额"] == "500"


def test_split_filename_strips_underscore_suffix():
    """V1.2: 分表文件名中卡号去除 _后缀"""
    with tempfile.TemporaryDirectory() as tmp:
        detail_path = os.path.join(tmp, "交易明细信息_合并.csv")
        df = pd.DataFrame({
            "银行来源": ["工商银行"],
            "交易户名": ["张三"],
            "交易卡号": ["6217002210035674693_156_1"],
            "交易金额": ["100"],
        })
        df.to_csv(detail_path, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "分表")
        files = split_by_account(detail_path, output_dir)

        assert len(files) == 1
        assert os.path.exists(os.path.join(
            output_dir, "张三_工商银行_6217002210035674693.xlsx"
        ))


def test_split_same_account_diff_cards_merged():
    """V1.3: 同一户名同一银行同一交易账号的不同卡号合并为一张分表"""
    with tempfile.TemporaryDirectory() as tmp:
        detail_path = os.path.join(tmp, "交易明细信息_合并.csv")
        df = pd.DataFrame({
            "银行来源": ["工商银行", "工商银行"],
            "交易户名": ["张三", "张三"],
            "交易卡号": ["C001", "C002"],
            "交易账号": ["A001", "A001"],
            "交易金额": ["100", "200"],
        })
        df.to_csv(detail_path, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "分表")
        files = split_by_account(detail_path, output_dir)

        assert len(files) == 1
        result = pd.read_excel(files[0], dtype=str)
        assert len(result) == 2
        assert result.iloc[0]["交易卡号"] == "C001"
        assert result.iloc[1]["交易卡号"] == "C002"


def test_split_diff_accounts_separated():
    """V1.3: 同一户名同一银行但不同交易账号应拆分为不同分表"""
    with tempfile.TemporaryDirectory() as tmp:
        detail_path = os.path.join(tmp, "交易明细信息_合并.csv")
        df = pd.DataFrame({
            "银行来源": ["工商银行", "工商银行"],
            "交易户名": ["张三", "张三"],
            "交易卡号": ["C001", "C002"],
            "交易账号": ["A001", "A002"],
            "交易金额": ["100", "200"],
        })
        df.to_csv(detail_path, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "分表")
        files = split_by_account(detail_path, output_dir)

        assert len(files) == 2


def test_split_sorted_by_card_and_time():
    """V1.3: 交易明细合并表按卡号升序→交易时间升序排序"""
    with tempfile.TemporaryDirectory() as tmp:
        detail_path = os.path.join(tmp, "交易明细信息_合并.csv")
        df = pd.DataFrame({
            "银行来源": ["工商银行", "工商银行", "工商银行"],
            "交易户名": ["张三", "张三", "张三"],
            "交易卡号": ["C003", "C001", "C001"],
            "交易账号": ["A001", "A001", "A001"],
            "交易时间": ["2024-03-01", "2024-02-01", "2024-01-01"],
            "交易金额": ["300", "200", "100"],
        })
        df.to_csv(detail_path, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "分表")
        files = split_by_account(detail_path, output_dir)

        assert len(files) == 1
        result = pd.read_excel(files[0], dtype=str)
        assert result.iloc[0]["交易卡号"] == "C001"
        assert result.iloc[0]["交易时间"] == "2024-01-01"
        assert result.iloc[1]["交易卡号"] == "C001"
        assert result.iloc[1]["交易时间"] == "2024-02-01"
        assert result.iloc[2]["交易卡号"] == "C003"


def test_split_removes_illegal_control_chars():
    """V1.6 回归: 分表写入 XLSX 前清理 \x10 控制字符，不再报 IllegalCharacterError"""
    with tempfile.TemporaryDirectory() as tmp:
        detail_path = os.path.join(tmp, "交易明细信息_合并.csv")
        bad_name = "AW8BAGYFokXSyvkpZwrs-GMi0z7Vvmy8" + "\x10" * 16 + "司"
        df = pd.DataFrame({
            "银行来源": ["中国光大银行"],
            "交易户名": ["张三"],
            "交易卡号": ["C001"],
            "交易对手名称": [bad_name],
            "交易金额": ["100"],
        })
        df.to_csv(detail_path, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "分表")
        files = split_by_account(detail_path, output_dir)

        assert len(files) == 1
        result = pd.read_excel(files[0], dtype=str)
        assert result.iloc[0]["交易对手名称"] == "AW8BAGYFokXSyvkpZwrs-GMi0z7Vvmy8司"
        assert "\x10" not in result.to_string()
