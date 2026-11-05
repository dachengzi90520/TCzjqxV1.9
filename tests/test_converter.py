import sys
sys.path.insert(0, '.')
import os
import tempfile
import pandas as pd
from core.converter import (
    csv_to_xlsx, final_output, _format_amount_df,
    format_amount_columns, clean_account_card_numbers
)
from openpyxl import load_workbook
from utils.csv_utils import read_csv_auto

MAX_XLSX_ROWS = 1_048_576


def test_csv_to_xlsx_basic():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "test.csv")
        pd.DataFrame({"姓名": ["张三"], "卡号": ["6222021234567890"]}).to_csv(
            csv_path, index=False, encoding="utf-8-sig"
        )

        xlsx_path = os.path.join(tmp, "test.xlsx")
        csv_to_xlsx(csv_path, xlsx_path)

        assert os.path.exists(xlsx_path)
        wb = load_workbook(xlsx_path)
        ws = wb.active
        assert ws.cell(2, 2).value == "6222021234567890"


def test_csv_to_xlsx_strips_whitespace():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "test.csv")
        pd.DataFrame({"姓名": [" 张三  "], "金额": [" 100 "]}).to_csv(
            csv_path, index=False, encoding="utf-8-sig"
        )

        xlsx_path = os.path.join(tmp, "test.xlsx")
        csv_to_xlsx(csv_path, xlsx_path)

        wb = load_workbook(xlsx_path)
        ws = wb.active
        assert ws.cell(2, 1).value == "张三"


def test_csv_to_xlsx_removes_illegal_chars():
    """V1.5: 含 \\x1c 控制字符的数据写入 XLSX 不再报 IllegalCharacterError"""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "test.csv")
        pd.DataFrame({"交易对手名称": ["7C04\x1cJSV91"], "备注": ["正常"]}).to_csv(
            csv_path, index=False, encoding="utf-8-sig"
        )

        xlsx_path = os.path.join(tmp, "test.xlsx")
        csv_to_xlsx(csv_path, xlsx_path)

        wb = load_workbook(xlsx_path)
        ws = wb.active
        assert ws.cell(2, 1).value == "7C04JSV91"


def test_format_amount_df():
    """_format_amount_df 将金额列转为 float"""
    df = pd.DataFrame({
        "交易卡号": ["C001", "C002"],
        "交易金额": ["100.50", "200"],
        "交易余额": ["50.123", ""],
        "其他": ["x", "y"],
    })
    result = _format_amount_df(df)
    assert isinstance(result.iloc[0]["交易金额"], float)
    assert result.iloc[0]["交易金额"] == 100.50
    assert result.iloc[1]["交易金额"] == 200.0
    assert isinstance(result.iloc[0]["交易余额"], float)
    assert result.iloc[0]["交易余额"] == 50.12


def test_format_amount_columns():
    """format_amount_columns 流式处理 XLSX"""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "交易明细_test.csv")
        pd.DataFrame({
            "交易卡号": ["C001", "C002"],
            "交易金额": ["100.50", "200"],
            "交易余额": ["50.123", ""],
        }).to_csv(csv_path, index=False, encoding="utf-8-sig")

        xlsx_path = os.path.join(tmp, "交易明细_test.xlsx")
        csv_to_xlsx(csv_path, xlsx_path)

        format_amount_columns(xlsx_path)

        wb2 = load_workbook(xlsx_path)
        ws2 = wb2.active
        assert isinstance(ws2.cell(2, 2).value, float)
        assert ws2.cell(2, 2).value == 100.50
        assert ws2.cell(2, 3).value == 50.12
        assert ws2.cell(3, 3).value is None or ws2.cell(3, 3).value == ""


def test_v19_amount_cells_numeric_and_display_two_decimals():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "交易明细信息_合并.csv")
        xlsx_path = os.path.join(tmp, "交易明细信息_合并.xlsx")
        pd.DataFrame({
            "交易卡号": ["C001"],
            "交易金额": ["100"],
            "交易余额": ["50.5"],
        }).to_csv(csv_path, index=False, encoding="utf-8-sig")

        csv_to_xlsx(csv_path, xlsx_path)
        ws = load_workbook(xlsx_path).active

        assert ws.cell(2, 2).value == 100.0
        assert ws.cell(2, 2).number_format == "0.00"
        assert ws.cell(2, 3).value == 50.5
        assert ws.cell(2, 3).number_format == "0.00"


def test_clean_account_card_numbers():
    """clean_account_card_numbers 改为操作 CSV"""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "账户信息_合并.csv")
        df = pd.DataFrame({
            "交易卡号": ["6217002210035674693_156_1", "6217009999999999999"],
            "交易账号": ["3200012345678_001_2", ""],
            "交易户名": ["张三", "李四"],
        })
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        clean_account_card_numbers(csv_path)

        result = read_csv_auto(csv_path)
        assert result.iloc[0]["交易卡号"] == "6217002210035674693"
        assert result.iloc[0]["交易账号"] == "3200012345678"
        assert result.iloc[1]["交易卡号"] == "6217009999999999999"


def test_clean_account_card_numbers_dash_prefix():
    """V1.3: clean_account_card_numbers 去除 - 前缀"""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "账户信息_合并.csv")
        df = pd.DataFrame({
            "交易卡号": ["123456-7890123456789"],
            "交易账号": ["001-3200012345678_1_2"],
        })
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        clean_account_card_numbers(csv_path)

        result = read_csv_auto(csv_path)
        assert result.iloc[0]["交易卡号"] == "7890123456789"
        assert result.iloc[0]["交易账号"] == "3200012345678"


def test_final_output_small():
    """final_output: 数据量小，输出单文件 + 分表"""
    with tempfile.TemporaryDirectory() as tmp:
        detail_csv = os.path.join(tmp, "交易明细信息_合并.csv")
        pd.DataFrame({
            "银行来源": ["工商银行", "建设银行"],
            "交易户名": ["张三", "李四"],
            "交易卡号": ["C001", "C002"],
            "交易金额": ["100", "200"],
            "交易余额": ["50", "100"],
        }).to_csv(detail_csv, index=False, encoding="utf-8-sig")

        personnel_csv = os.path.join(tmp, "人员信息_合并.csv")
        pd.DataFrame({"姓名": ["张三"]}).to_csv(personnel_csv, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "output")
        csv_files = [detail_csv, personnel_csv]

        final_output(csv_files, output_dir)

        # 验证汇总 XLSX
        detail_xlsx = os.path.join(output_dir, "交易明细信息_合并.xlsx")
        assert os.path.exists(detail_xlsx)
        result = pd.read_excel(detail_xlsx, dtype=str)
        assert len(result) == 2

        personnel_xlsx = os.path.join(output_dir, "人员信息_合并.xlsx")
        assert os.path.exists(personnel_xlsx)

        # 验证分表
        split_dir = os.path.join(output_dir, "分表")
        assert os.path.exists(split_dir)
        assert len(os.listdir(split_dir)) == 2


def test_final_output_over_limit(monkeypatch):
    """final_output: 超过限制行数时自动分片（用 monkeypatch 模拟小阈值）"""
    # 用 monkeypatch 设置很小的分片阈值来快速验证分片逻辑
    monkeypatch.setattr("core.converter.MAX_XLSX_ROWS", 50)

    with tempfile.TemporaryDirectory() as tmp:
        detail_csv = os.path.join(tmp, "交易明细信息_合并.csv")
        n_rows = 120  # 超过 50 行阈值，应分 3 片
        df = pd.DataFrame({
            "银行来源": ["测试银行"] * n_rows,
            "交易户名": ["测试人"] * n_rows,
            "交易卡号": [f"C{i:03d}" for i in range(n_rows)],
            "交易金额": ["100"] * n_rows,
            "交易余额": ["50"] * n_rows,
        })
        df.to_csv(detail_csv, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "output")
        from core.converter import final_output
        final_output([detail_csv], output_dir)

        # 应生成 3 个汇总分片（50 + 50 + 20）
        f1 = os.path.join(output_dir, "交易明细信息_合并.xlsx")
        f2 = os.path.join(output_dir, "交易明细信息_合并_2.xlsx")
        f3 = os.path.join(output_dir, "交易明细信息_合并_3.xlsx")
        assert os.path.exists(f1)
        assert os.path.exists(f2)
        assert os.path.exists(f3)

        r1 = pd.read_excel(f1, dtype=str)
        r2 = pd.read_excel(f2, dtype=str)
        r3 = pd.read_excel(f3, dtype=str)
        assert len(r1) == 50
        assert len(r2) == 50
        assert len(r3) == 20


def test_final_output_with_illegal_chars():
    """V1.5: 交易明细含非法控制字符时，汇总 XLSX 与分表均能正常生成"""
    with tempfile.TemporaryDirectory() as tmp:
        detail_csv = os.path.join(tmp, "交易明细信息_合并.csv")
        pd.DataFrame({
            "银行来源": ["工商银行"],
            "交易户名": ["张三"],
            "交易卡号": ["C001"],
            "交易对手名称": ["223HOTEL LOTTE CO\x1cLTD(LOTTE          KOR"],
            "交易金额": ["100"],
            "交易余额": ["50"],
        }).to_csv(detail_csv, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "output")
        final_output([detail_csv], output_dir)

        # 汇总 XLSX
        detail_xlsx = os.path.join(output_dir, "交易明细信息_合并.xlsx")
        assert os.path.exists(detail_xlsx)
        result = pd.read_excel(detail_xlsx, dtype=str)
        assert "223HOTEL LOTTE COLTD(LOTTE          KOR" in result.iloc[0]["交易对手名称"]

        # 分表 XLSX 同样正常生成且不含非法字符
        split_dir = os.path.join(output_dir, "分表")
        assert os.path.exists(split_dir)
        split_files = os.listdir(split_dir)
        assert len(split_files) == 1
        split_df = pd.read_excel(os.path.join(split_dir, split_files[0]), dtype=str)
        assert "\x1c" not in split_df.to_string()


def test_final_output_with_control_chars_20260817():
    """V1.6 回归: 20260817 光大银行反馈包中 \x10 控制字符不再导致 IllegalCharacterError"""
    with tempfile.TemporaryDirectory() as tmp:
        detail_csv = os.path.join(tmp, "交易明细信息_合并.csv")
        bad_name = "AW8BAGYFokXSyvkpZwrs-GMi0z7Vvmy8" + "\x10" * 16 + "司"
        pd.DataFrame({
            "银行来源": ["中国光大银行"],
            "交易户名": ["张三"],
            "交易卡号": ["6231560203436887"],
            "交易对手名称": [bad_name],
            "交易金额": ["100"],
            "交易余额": ["2528.97"],
        }).to_csv(detail_csv, index=False, encoding="utf-8-sig")

        output_dir = os.path.join(tmp, "output")
        final_output([detail_csv], output_dir)

        detail_xlsx = os.path.join(output_dir, "交易明细信息_合并.xlsx")
        assert os.path.exists(detail_xlsx)
        result = pd.read_excel(detail_xlsx, dtype=str)
        assert result.iloc[0]["交易对手名称"] == "AW8BAGYFokXSyvkpZwrs-GMi0z7Vvmy8司"
        assert "\x10" not in result.to_string()

        split_dir = os.path.join(output_dir, "分表")
        split_files = os.listdir(split_dir)
        assert len(split_files) == 1
        split_df = pd.read_excel(os.path.join(split_dir, split_files[0]), dtype=str)
        assert "\x10" not in split_df.to_string()
