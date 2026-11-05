import sys
sys.path.insert(0, '.')
import os
import tempfile
import pandas as pd
from core.merger import merge_csvs


def create_test_csv(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_merge_csvs_basic():
    with tempfile.TemporaryDirectory() as tmp:
        csv1 = os.path.join(tmp, "交易明细_银行A.csv")
        csv2 = os.path.join(tmp, "交易明细_银行B.csv")
        create_test_csv(csv1, "卡号,金额\n001,100\n")
        create_test_csv(csv2, "卡号,金额\n002,200\n")

        collected = {
            "交易明细信息": [
                ("银行A", csv1),
                ("银行B", csv2),
            ]
        }

        output_dir = os.path.join(tmp, "merged")
        os.makedirs(output_dir)
        merge_csvs(collected, output_dir)

        merged_path = os.path.join(output_dir, "交易明细信息_合并.csv")
        assert os.path.exists(merged_path)

        df = pd.read_csv(merged_path, dtype=str)
        assert len(df) == 2
        assert "银行来源" in df.columns
        assert df.iloc[0]["银行来源"] == "银行A"


def test_merge_csvs_different_columns():
    with tempfile.TemporaryDirectory() as tmp:
        csv1 = os.path.join(tmp, "交易明细_A.csv")
        csv2 = os.path.join(tmp, "交易明细_B.csv")
        create_test_csv(csv1, "卡号,金额\n001,100\n")
        create_test_csv(csv2, "卡号,金额,备注\n002,200,test\n")

        collected = {
            "交易明细信息": [
                ("银行A", csv1),
                ("银行B", csv2),
            ]
        }

        output_dir = os.path.join(tmp, "merged")
        os.makedirs(output_dir)
        merge_csvs(collected, output_dir)

        df = pd.read_csv(os.path.join(output_dir, "交易明细信息_合并.csv"), dtype=str)
        assert "备注" in df.columns
