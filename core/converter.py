"""CSV → XLSX 转换 + 最终输出：长数字列文本格式，汇总超限自动分片"""
import os
import shutil
import pandas as pd
from openpyxl import Workbook
from openpyxl import load_workbook
from openpyxl.cell import WriteOnlyCell
from typing import Callable
from utils.csv_utils import read_csv_auto, sanitize_excel_string
from core.cleaner import normalize_transaction_amounts

MAX_XLSX_ROWS = 1_048_576


# ============================================================
# 工具：预计算列类型，避免逐行检查
# ============================================================

def _classify_columns(df_columns) -> tuple[list[int], list[int]]:
    """
    将列索引分为「金额列」和「文本列」，避免写 XLSX 时对每个单元格做字符串匹配。
    返回 (amount_indices, text_indices)
    """
    amount_idx = []
    text_idx = []
    for i, col in enumerate(df_columns):
        col_name = str(col)
        if "交易金额" in col_name or "交易余额" in col_name:
            amount_idx.append(i)
        else:
            text_idx.append(i)
    return amount_idx, text_idx


def _build_row_writer(columns, amount_idx, text_idx):
    """
    返回一个快速行构建函数 (row_tuple) → list。
    金额列转 float，文本列转 str.strip()。
    """
    def fast_row(row_tuple) -> list:
        row_data = [None] * len(columns)
        for i in amount_idx:
            val = row_tuple[i]
            if val is not None:
                str_val = str(val).strip()
                if str_val and str_val != "nan":
                    try:
                        row_data[i] = round(float(str_val), 2)
                    except ValueError:
                        row_data[i] = sanitize_excel_string(str_val)
        for i in text_idx:
            val = row_tuple[i]
            if val is None:
                row_data[i] = ""
            else:
                s = str(val)
                row_data[i] = sanitize_excel_string(s).strip() if s != "nan" else ""
        return row_data
    return fast_row


def _append_xlsx_row(ws, row_data, amount_idx) -> None:
    """追加一行，并给有效金额数值设置两位小数格式。"""
    amount_indices = set(amount_idx)
    cells = []
    for idx, value in enumerate(row_data):
        cell = WriteOnlyCell(ws, value=value)
        if idx in amount_indices and isinstance(value, (int, float)):
            cell.number_format = "0.00"
        cells.append(cell)
    ws.append(cells)


# ============================================================
# 基础：CSV → XLSX（流式写入）
# ============================================================

def csv_to_xlsx(csv_path: str, xlsx_path: str) -> None:
    """单个 CSV 转 XLSX（流式写入，预计算列类型加速）"""
    df = read_csv_auto(csv_path)

    columns = list(df.columns)
    amount_idx, text_idx = _classify_columns(columns)
    build_row = _build_row_writer(columns, amount_idx, text_idx)

    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append([sanitize_excel_string(col).strip() for col in columns])

    # 用 itertuples 替代 iterrows（~10x 更快）
    for row_tuple in df.itertuples(index=False, name=None):
        _append_xlsx_row(ws, build_row(row_tuple), amount_idx)

    wb.save(xlsx_path)


# ============================================================
# 金额格式化
# ============================================================

def _format_amount_df(df):
    """
    将 DataFrame 中的交易金额/交易余额列转为 float（保留2位小数）。
    无法转换的非空内容保持原值，避免最终输出时丢失数据。
    """
    return normalize_transaction_amounts(df)


def format_amount_columns(xlsx_path: str) -> None:
    """
    将 XLSX 中的 交易金额/交易余额 列转为数值格式（流式处理）。
    用于分表文件的金额格式化。
    """
    wb_read = load_workbook(xlsx_path, read_only=True)
    ws_read = wb_read.active

    header = []
    amount_col_idxs = []

    for row in ws_read.iter_rows(min_row=1, max_row=1, values_only=True):
        for col_idx, cell_val in enumerate(row):
            col_name = str(cell_val or "")
            header.append(col_name)
            if "交易金额" in col_name or "交易余额" in col_name:
                amount_col_idxs.append(col_idx)

    if not amount_col_idxs:
        wb_read.close()
        return

    wb_write = Workbook(write_only=True)
    ws_write = wb_write.create_sheet()
    ws_write.append(header)

    for row in ws_read.iter_rows(min_row=2, values_only=True):
        new_row = []
        for col_idx, val in enumerate(row):
            if col_idx in amount_col_idxs:
                str_val = str(val or "").strip()
                if str_val and str_val != "nan":
                    try:
                        new_row.append(round(float(str_val), 2))
                    except ValueError:
                        new_row.append(sanitize_excel_string(str_val))
                else:
                    new_row.append(None)
            else:
                new_row.append(val)
        _append_xlsx_row(ws_write, new_row, amount_col_idxs)

    wb_read.close()

    tmp_path = xlsx_path + ".tmp"
    wb_write.save(tmp_path)
    wb_write.close()
    shutil.move(tmp_path, xlsx_path)


# ============================================================
# 卡号/账号清理（账户信息表）
# ============================================================

def clean_account_card_numbers(csv_path: str, dash_mode: str = "prefix") -> None:
    """
    清理 CSV 中 交易卡号/交易账号 列的附加字符。

    dash_mode:
      - "prefix": "-" 是前缀分隔符（银行代号），删 "-" 及之前 → 用于账户信息表
      - "suffix": "-" 是后缀分隔符（调证序号），删 "-" 及之后 → 用于交易明细表

    "_" 后缀（批次号）：两侧统一删除 "_" 及之后。
    """
    df = read_csv_auto(csv_path)

    for col in df.columns:
        col_name = str(col)
        if "交易卡号" in col_name or "交易账号" in col_name:
            if dash_mode == "suffix":
                def _clean(val):
                    s = str(val).strip() if val is not None else ""
                    if not s or s == "nan":
                        return val
                    # "-" 作后缀分隔符，删除 "-" 及之后
                    dash_pos = s.find("-")
                    if dash_pos >= 0:
                        s = s[:dash_pos]
                    # "_" 作后缀分隔符
                    underscore_pos = s.find("_")
                    if underscore_pos > 0:
                        s = s[:underscore_pos]
                    return s
            else:
                def _clean(val):
                    s = str(val).strip() if val is not None else ""
                    if not s or s == "nan":
                        return val
                    # "-" 作前缀分隔符，删除 "-" 及之前
                    dash_pos = s.find("-")
                    if dash_pos >= 0:
                        s = s[dash_pos + 1:]
                    # "_" 作后缀分隔符
                    underscore_pos = s.find("_")
                    if underscore_pos > 0:
                        s = s[:underscore_pos]
                    return s
            df[col] = df[col].apply(_clean)

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")


# ============================================================
# 最终输出
# ============================================================

def _write_single_xlsx(df, xlsx_path: str) -> None:
    """将 DataFrame 写入 XLSX：金额列格式化为数值，其余列转为字符串（itertuples 加速）"""
    columns = list(df.columns)
    amount_idx, text_idx = _classify_columns(columns)
    build_row = _build_row_writer(columns, amount_idx, text_idx)

    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append([sanitize_excel_string(col).strip() for col in columns])

    for row_tuple in df.itertuples(index=False, name=None):
        _append_xlsx_row(ws, build_row(row_tuple), amount_idx)

    wb.save(xlsx_path)


def _write_summary_xlsx(df, output_dir: str, base_name: str) -> list[str]:
    """写入汇总 XLSX，超 MAX_XLSX_ROWS 行自动分片。返回生成的文件路径列表。"""
    output_files = []
    total = len(df)

    if total <= MAX_XLSX_ROWS:
        xlsx_path = os.path.join(output_dir, f"{base_name}.xlsx")
        _write_single_xlsx(df, xlsx_path)
        output_files.append(xlsx_path)
    else:
        num_chunks = (total + MAX_XLSX_ROWS - 1) // MAX_XLSX_ROWS
        for i in range(num_chunks):
            start = i * MAX_XLSX_ROWS
            end = min(start + MAX_XLSX_ROWS, total)
            chunk = df.iloc[start:end].reset_index(drop=True)

            if i == 0:
                filename = f"{base_name}.xlsx"
            else:
                filename = f"{base_name}_{i + 1}.xlsx"

            xlsx_path = os.path.join(output_dir, filename)
            _write_single_xlsx(chunk, xlsx_path)
            output_files.append(xlsx_path)

    return output_files


def final_output(
    csv_files: list[str],
    output_dir: str,
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None
) -> None:
    """
    最终输出步骤：
    - 非交易明细表：直接 CSV → XLSX
    - 交易明细表：格式化金额 → 汇总 XLSX（超限分片）+ 分表
    """
    from core.splitter import split_by_account

    os.makedirs(output_dir, exist_ok=True)

    detail_csv = None

    # 先找出交易明细 CSV，其他直接转 XLSX
    for csv_path in csv_files:
        basename = os.path.basename(csv_path)
        if "交易明细" in basename:
            detail_csv = csv_path
        else:
            safe_name = os.path.splitext(basename)[0]
            safe_name = safe_name.replace("（", "(").replace("）", ")")
            xlsx_name = safe_name + ".xlsx"
            xlsx_path = os.path.join(output_dir, xlsx_name)
            if progress_callback:
                progress_callback(f"输出: {xlsx_name}", 0)
            csv_to_xlsx(csv_path, xlsx_path)

    # 处理交易明细
    if detail_csv and os.path.exists(detail_csv):
        if progress_callback:
            progress_callback("读取交易明细...", 20.0)

        df = read_csv_auto(detail_csv)

        # 格式化金额列（全向量化）
        df = _format_amount_df(df)

        # 输出汇总 XLSX（自动分片）
        if progress_callback:
            progress_callback("输出汇总 XLSX...", 40.0)

        base_name = os.path.splitext(os.path.basename(detail_csv))[0]
        summary_files = _write_summary_xlsx(df, output_dir, base_name)

        if error_logger:
            error_logger.info(f"汇总输出: {len(summary_files)} 个文件, 共 {len(df)} 行")

        # 分表（splitter 内部已做金额格式化）
        if progress_callback:
            progress_callback("分表...", 70.0)

        split_dir = os.path.join(output_dir, "分表")
        try:
            split_files = split_by_account(
                detail_csv,
                split_dir,
                progress_callback=lambda msg, pct: None,
                error_logger=error_logger
            )

            if error_logger:
                error_logger.info(f"分表完成: {len(split_files)} 个文件")
        except Exception as e:
            if error_logger:
                error_logger.error(f"分表失败: {e}")
            import traceback
            if error_logger:
                error_logger.error(traceback.format_exc())


def convert_all(
    csv_files: list[str],
    output_dir: str,
    progress_callback: Callable[[str, float], None] | None = None
) -> list[str]:
    """
    批量转换所有 CSV 为 XLSX。
    保留此函数以兼容可能的旧调用，推荐使用 final_output 替代。
    """
    xlsx_files = []
    total = len(csv_files)

    for idx, csv_path in enumerate(csv_files):
        basename = os.path.splitext(os.path.basename(csv_path))[0]
        safe_name = basename.replace("（", "(").replace("）", ")")
        xlsx_path = os.path.join(output_dir, f"{safe_name}.xlsx")

        if progress_callback:
            progress_callback(f"转换: {basename}", (idx / total) * 100)

        csv_to_xlsx(csv_path, xlsx_path)
        xlsx_files.append(xlsx_path)

    if progress_callback:
        progress_callback("转换完成", 100.0)

    return xlsx_files
