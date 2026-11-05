import sys
sys.path.insert(0, '.')
import os
import tempfile
import pandas as pd
from core.cleaner import clean_transaction_detail, clean_csv
from core.cleaner import (
    normalize_payment_flags,
    normalize_transaction_amounts,
    strip_transaction_detail,
)


def test_v19_keeps_row_when_time_empty_but_amount_present():
    df = pd.DataFrame({
        "交易时间": ["", "2024-01-01", None],
        "交易金额": ["100", "200", "300"],
        "交易余额": ["50", "60", "70"],
    })
    result = clean_transaction_detail(df)
    assert len(result) == 3


def test_v19_removes_row_when_time_and_amount_both_empty():
    df = pd.DataFrame({
        "交易时间": ["", None, "2024-01-03"],
        "交易金额": ["", "", "300"],
        "交易余额": ["", "200", ""],
    })
    result = clean_transaction_detail(df)
    assert len(result) == 1
    assert result.iloc[0]["交易时间"] == "2024-01-03"


def test_clean_keep_when_one_amount_exists():
    df = pd.DataFrame({
        "交易时间": ["2024-01-01", "2024-01-02"],
        "交易金额": ["100", ""],
        "交易余额": ["", "200"],
    })
    result = clean_transaction_detail(df)
    assert len(result) == 2


def test_clean_csv_file():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "交易明细信息_合并.csv")
        df = pd.DataFrame({
            "交易时间": ["2024-01-01", "", "", "2024-01-03"],
            "交易金额": ["100", "x", "", ""],
            "交易余额": ["50", "x", "", ""],
        })
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        removed = clean_csv(csv_path)
        assert removed == 1

        result = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        assert len(result) == 3


def test_clean_skips_non_detail_files():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "人员信息_合并.csv")
        df = pd.DataFrame({"姓名": ["张三"], "年龄": ["30"]})
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        removed = clean_csv(csv_path)
        assert removed == 0


def test_v19_strip_all_fields():
    df = pd.DataFrame({
        "交易卡号": [" C001 ", "   "],
        "交易时间": [" 2024-01-01 ", None],
    })
    result = strip_transaction_detail(df)
    assert result.iloc[0]["交易卡号"] == "C001"
    assert result.iloc[1]["交易卡号"] == ""


def test_v19_amounts_numeric_and_two_decimals():
    df = pd.DataFrame({
        "交易金额": ["100.126", "200", "非数字", ""],
        "交易余额": ["50.555", "", "30.2", "x"],
    })
    result = normalize_transaction_amounts(df)
    assert result.iloc[0]["交易金额"] == 100.13
    assert result.iloc[1]["交易金额"] == 200.0
    assert result.iloc[0]["交易余额"] == 50.56
    assert result.iloc[2]["交易金额"] == "非数字"
    assert result.iloc[2]["交易余额"] == 30.2


def test_v19_payment_flag_exact_mapping_and_unknown_preserved():
    df = pd.DataFrame({
        "收付标志": ["借", "1", "D", "d", "转出", "贷", "2", "C", "c", "入", "转入", " 借 ", "借入", ""],
    })
    result = normalize_payment_flags(df)
    assert result["收付标志"].tolist() == [
        "出", "出", "出", "出", "出",
        "进", "进", "进", "进", "进", "进",
        "出", "借入", "",
    ]
