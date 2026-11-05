"""去重模块：资金流水执行全字段去重和最终 6 列去重，其他表按全列去重。"""
import os
import pandas as pd
from typing import Callable, Sequence
from utils.config import DEDUP_COLS_DETAIL, find_columns
from utils.csv_utils import read_csv_auto
from core.cleaner import strip_transaction_detail


def deduplicate_detail(
    df: pd.DataFrame,
    dedup_cols: Sequence[str] | None = None
) -> pd.DataFrame:
    """
    对交易明细表按指定去重键去重（模糊匹配列名）。
    默认使用 DEDUP_COLS_DETAIL（V1.9 六列）。
    如果某列不存在则跳过该列；全部列都不存在时退化为全列去重。
    """
    keywords = list(dedup_cols) if dedup_cols is not None else list(DEDUP_COLS_DETAIL)
    existing_cols = find_columns(list(df.columns), keywords)
    if existing_cols:
        return df.drop_duplicates(subset=existing_cols, keep="first").reset_index(drop=True)
    else:
        return df.drop_duplicates(keep="first").reset_index(drop=True)


def deduplicate_detail_full(df: pd.DataFrame) -> pd.DataFrame:
    """V1.9 第 1、2 步：清理前后空白后，以全部字段相同判定重复。"""
    cleaned = strip_transaction_detail(df)
    return cleaned.drop_duplicates(keep="first").reset_index(drop=True)


def deduplicate_csv(
    file_path: str,
    dedup_cols: Sequence[str] | None = None,
    full_detail_fields: bool = False,
) -> int:
    """
    对 CSV 文件去重，自动判断是交易明细还是其他表。
    dedup_cols 为交易明细最终去重键（默认 V1.9 六列）。
    full_detail_fields=True 时，交易明细先清理前后空白并按全字段去重。
    返回去掉的行数。
    """
    df = read_csv_auto(file_path)
    before = len(df)

    basename = os.path.basename(file_path)
    if "交易明细" in basename:
        if full_detail_fields:
            df = deduplicate_detail_full(df)
        else:
            df = deduplicate_detail(df, dedup_cols)
    else:
        df = df.drop_duplicates(keep="first").reset_index(drop=True)

    after = len(df)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return before - after


def deduplicate_all(
    csv_files: list[str],
    dedup_cols: Sequence[str] | None = None,
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None,
    full_detail_fields: bool = False,
) -> dict[str, int]:
    """
    对所有 CSV 文件执行去重，返回每个文件去掉的行数。
    交易明细默认使用 dedup_cols（V1.9 六列）；first pass 可传
    full_detail_fields=True 执行全字段去重。其他表始终按全列去重。
    """
    results = {}
    total = len(csv_files)
    for idx, path in enumerate(csv_files):
        basename = os.path.basename(path)
        if progress_callback:
            progress_callback(f"去重: {basename}", (idx / total) * 100)
        try:
            removed = deduplicate_csv(path, dedup_cols, full_detail_fields)
            results[basename] = removed
            if error_logger:
                error_logger.info(f"去重完成: {basename}, 移除 {removed} 行")
        except Exception as e:
            if error_logger:
                error_logger.error(f"去重失败: {basename}, {e}")
            results[basename] = -1
    return results
