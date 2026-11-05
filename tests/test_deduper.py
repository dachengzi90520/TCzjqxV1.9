import sys
sys.path.insert(0, '.')
import os
import tempfile
import pandas as pd
from core.deduper import deduplicate_csv, deduplicate_detail, deduplicate_detail_full
from utils.config import DEDUP_COLS_DETAIL


def test_deduplicate_detail_finds_cols():
    df = pd.DataFrame({
        "交易卡号": ["A", "A", "B"],
        "交易时间": ["2024-01-01", "2024-01-01", "2024-01-02"],
        "交易金额": ["100", "100", "200"],
        "收付标志": ["1", "1", "2"],
        "交易对手账卡号": ["X", "X", "Y"],
        "其他列": ["x1", "x2", "y1"],
    })
    result = deduplicate_detail(df)
    assert len(result) == 2


def test_deduplicate_full():
    df = pd.DataFrame({"a": ["1", "1", "2"], "b": ["2", "2", "3"]})
    result = df.drop_duplicates()
    assert len(result) == 2


def test_deduplicate_csv_detail():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "交易明细信息_合并.csv")
        df = pd.DataFrame({
            "交易卡号": ["A", "A", "B"],
            "交易时间": ["2024-01-01", "2024-01-01", "2024-01-02"],
            "交易金额": ["100", "100", "200"],
            "收付标志": ["1", "1", "2"],
            "交易对手账卡号": ["X", "X", "Y"],
        })
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        deduplicate_csv(csv_path)
        result = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        assert len(result) == 2


def test_deduplicate_csv_other_table():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "人员信息_合并.csv")
        df = pd.DataFrame({
            "姓名": ["张三", "张三", "李四"],
            "身份证": ["123", "123", "456"],
        })
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        deduplicate_csv(csv_path)
        result = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        assert len(result) == 2


# ==================== V1.8：去重键加入"交易余额" ====================

def _detail_df_with_balance():
    """同一卡、同一秒、同金额、同对手，但交易余额不同的两笔真实交易。"""
    return pd.DataFrame({
        "交易卡号": ["A", "A", "B"],
        "交易时间": ["2024-01-01 10:00:00", "2024-01-01 10:00:00", "2024-01-02 10:00:00"],
        "交易金额": ["100", "100", "200"],
        "交易余额": ["900", "800", "700"],
        "收付标志": ["1", "1", "2"],
        "交易对手账卡号": ["X", "X", "Y"],
        "其他列": ["x1", "x2", "y1"],
    })


def test_v18_keeps_rows_with_different_balance():
    """V1.8：6 列去重 —— 余额不同视为不同笔交易，必须全部保留。"""
    result = deduplicate_detail(_detail_df_with_balance())
    assert len(result) == 3, f"余额不同的 3 笔交易都应保留, 实际: {len(result)}"


def test_v18_removes_true_duplicate():
    """V1.8：6 列完全相同的行仍应被去掉。"""
    df = _detail_df_with_balance()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    result = deduplicate_detail(df)
    assert len(result) == 3, f"完全重复的 1 行应被去掉, 实际: {len(result)}"


def test_v17_five_cols_would_merge_balance_rows():
    """对照：显式传 V1.7 的 5 列键时，余额不同的行会被合并（说明扩键确有必要）。"""
    v17_cols = ["交易卡号", "交易时间", "交易金额", "收付标志", "交易对手账卡号"]
    result = deduplicate_detail(_detail_df_with_balance(), v17_cols)
    assert len(result) == 2, f"5 列去重后应为 2 行, 实际: {len(result)}"


def test_v18_csv_detail_default_uses_balance():
    """deduplicate_csv 默认按 6 列（含余额）去重，不同余额的行全部保留。"""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "交易明细信息_合并.csv")
        _detail_df_with_balance().to_csv(csv_path, index=False, encoding="utf-8-sig")

        removed = deduplicate_csv(csv_path)
        result = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        assert removed == 0
        assert len(result) == 3


def test_v18_other_table_still_full_column():
    """6 列键只作用于交易明细，其他表仍为全列去重。"""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "账户信息_合并.csv")
        df = pd.DataFrame({
            "交易卡号": ["A", "A", "B"],
            "交易时间": ["t", "t", "t2"],
            "交易金额": ["1", "1", "2"],
            "交易余额": ["1", "2", "3"],
        })
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        deduplicate_csv(csv_path)
        result = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        assert len(result) == 3, "账户信息表按全列去重，4 列有差异的行不该合并"


def test_v18_missing_balance_col_falls_back_to_5_cols():
    """数据中无"交易余额"列时，6 列键自动退化为实际存在的 5 列，不报错。"""
    df = pd.DataFrame({
        "交易卡号": ["A", "A"],
        "交易时间": ["2024-01-01", "2024-01-01"],
        "交易金额": ["100", "100"],
        "收付标志": ["1", "1"],
        "交易对手账卡号": ["X", "X"],
    })
    result = deduplicate_detail(df)
    assert len(result) == 1


def test_v19_first_pass_is_full_field_after_strip():
    df = pd.DataFrame({
        "交易卡号": [" C001 ", "C001"],
        "交易时间": ["2024-01-01", "2024-01-01"],
        "交易金额": ["100", "100"],
        "其他列": [" A ", "A"],
    })
    result = deduplicate_detail_full(df)
    assert len(result) == 1
    assert result.iloc[0]["交易卡号"] == "C001"
    assert result.iloc[0]["其他列"] == "A"
