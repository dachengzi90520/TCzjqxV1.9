"""资金交易流水清洗与字段标准化（V1.9）。"""
import os
import pandas as pd
from typing import Callable
from utils.config import (
    CLEAN_REQUIRED_AMOUNT_COLS,
    PAYMENT_FLAG_MAPPING,
    find_column,
)
from utils.csv_utils import read_csv_auto


def _blank_mask(series: pd.Series) -> pd.Series:
    """判断空白值；兼容空字符串、None、NaN 和旧版读取产生的 "nan"。"""
    value = series.astype(str).str.strip()
    return series.isna() | value.isin(["", "nan", "None"])


def strip_transaction_detail(df: pd.DataFrame) -> pd.DataFrame:
    """去除资金流水所有字段的前后空白，不改变空白单元格本身。"""
    result = df.copy()
    for col in result.columns:
        s = result[col].astype(str)
        empty = _blank_mask(result[col])
        result[col] = s.str.strip().where(~empty, "")
    return result.reset_index(drop=True)


def clean_transaction_detail(df: pd.DataFrame) -> pd.DataFrame:
    """
    V1.9 第 3 步：删除"交易时间"和"交易金额"同时为空的行。

    注意：仅交易时间为空、但交易金额有值时，该行必须保留。
    """
    time_col = find_column(list(df.columns), "交易时间")
    amount_col = find_column(list(df.columns), CLEAN_REQUIRED_AMOUNT_COLS[0])
    if not time_col or not amount_col:
        return df.reset_index(drop=True)

    both_empty = _blank_mask(df[time_col]) & _blank_mask(df[amount_col])
    return df.loc[~both_empty].reset_index(drop=True)


def normalize_transaction_amounts(df: pd.DataFrame) -> pd.DataFrame:
    """V1.9 第 6 步：交易金额、交易余额转为数值并保留两位小数。"""
    result = df.copy()
    for keyword in CLEAN_REQUIRED_AMOUNT_COLS:
        col = find_column(list(result.columns), keyword)
        if not col:
            continue

        source = result[col].astype(str).str.strip()
        numeric = pd.to_numeric(
            source.where(~source.isin(["", "nan", "None"]), None),
            errors="coerce",
        )
        valid = numeric.notna()
        values = source.astype(object).copy()
        values.loc[valid] = numeric.loc[valid].round(2)
        result[col] = values
    return result


def normalize_payment_flags(df: pd.DataFrame) -> pd.DataFrame:
    """V1.9 第 7 步：精确替换标准收付标志，未匹配内容保持原样。"""
    result = df.copy()
    flag_col = find_column(list(result.columns), "收付标志")
    if not flag_col:
        flag_col = find_column(list(result.columns), "收费标志")
    if not flag_col:
        return result

    source = result[flag_col].astype(str).str.strip()
    matched = source.isin(PAYMENT_FLAG_MAPPING)
    mapped = source.map(PAYMENT_FLAG_MAPPING)
    result[flag_col] = source.where(~matched, mapped)
    return result


def normalize_transaction_fields(df: pd.DataFrame) -> pd.DataFrame:
    """按 V1.9 顺序执行金额数值化与收付标志标准化。"""
    return normalize_payment_flags(normalize_transaction_amounts(df))


def clean_csv(file_path: str) -> int:
    """
    清洗 CSV 文件（仅交易明细表）。
    返回删除的行数。
    """
    basename = os.path.basename(file_path)
    if "交易明细" not in basename:
        return 0

    df = read_csv_auto(file_path)
    before = len(df)
    df = clean_transaction_detail(df)
    after = len(df)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return before - after


def clean_all(
    csv_files: list[str],
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None
) -> dict[str, int]:
    """批量清洗，返回每个文件删除的行数"""
    results = {}
    total = len(csv_files)
    for idx, path in enumerate(csv_files):
        basename = os.path.basename(path)
        if progress_callback:
            progress_callback(f"清洗: {basename}", (idx / total) * 100)
        try:
            removed = clean_csv(path)
            results[basename] = removed
            if error_logger:
                error_logger.info(f"清洗完成: {basename}, 删除 {removed} 行")
        except Exception as e:
            if error_logger:
                error_logger.error(f"清洗失败: {basename}, {e}")
            results[basename] = -1
    return results


def normalize_transaction_csv(file_path: str) -> None:
    """对一个资金交易流水 CSV 执行第 6、7 步并写回。"""
    if "交易明细" not in os.path.basename(file_path):
        return
    df = read_csv_auto(file_path)
    df = normalize_transaction_fields(df)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")


def normalize_all(
    csv_files: list[str],
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None,
) -> dict[str, bool]:
    """批量执行交易金额数值化与收付标志标准化。"""
    results: dict[str, bool] = {}
    total = len(csv_files)
    for idx, path in enumerate(csv_files):
        basename = os.path.basename(path)
        if progress_callback:
            progress_callback(f"金额与收付标志标准化: {basename}", (idx / max(total, 1)) * 100)
        try:
            normalize_transaction_csv(path)
            results[basename] = True
            if error_logger:
                error_logger.info(f"金额/收付标志标准化完成: {basename}")
        except Exception as exc:
            if error_logger:
                error_logger.error(f"金额/收付标志标准化失败: {basename}, {exc}")
            results[basename] = False
    return results
