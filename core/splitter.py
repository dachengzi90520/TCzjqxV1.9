"""按户名分表：将交易明细按 银行+户名（或卡号）拆分为多个 XLSX（流式分块处理，防内存溢出）"""
import os
import re
import pandas as pd
from typing import Callable
from utils.config import find_column
from core.completer import _clean_detail_key
from utils.csv_utils import ILLEGAL_XML_CHARS_RE


def _safe_filename(name: str) -> str:
    """移除文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def _format_amount_inline(df: pd.DataFrame) -> None:
    """将交易金额/交易余额列转为数值 float，避免二次读取 XLSX"""
    for col in df.columns:
        col_name = str(col)
        if "交易金额" in col_name or "交易余额" in col_name:
            s = df[col].astype(str).str.strip()
            s = s.where(~s.isin(["", "nan"]), None)
            df[col] = pd.to_numeric(s, errors="coerce").round(2)


def _clean_series(s: pd.Series) -> pd.Series:
    """向量化清理交易明细侧卡号/账号：'-' 和 '_' 都作后缀分隔符"""
    # 第一步：删除 "-" 及其之后（调证序号后缀）
    s = s.str.replace(r'-.*$', '', regex=True)
    # 第二步：删除第一个 "_" 及其之后（批次号_序号）
    s = s.str.replace(r'_.*$', '', regex=True)
    return s


def _add_group_keys_vectorized(df: pd.DataFrame, name_col, card_col, account_col):
    """向量化计算分组键列（含 _clean_key 清理，确保 -/_ 不影响分组）"""
    # 预处理：清理卡号和账号列（统一去掉 "-"前缀 和 "_"后缀）
    clean_card = _clean_series(df[card_col].astype(str).str.strip()) if card_col else None
    clean_acct = _clean_series(df[account_col].astype(str).str.strip()) if account_col else None

    # 分组键1：户名为空用（清理后的）卡号
    if name_col:
        name_series = df[name_col].str.strip()
        has_name = name_series.notna() & (name_series != "") & (name_series != "nan")
        group_name = name_series.where(has_name, other=None)
        if clean_card is not None:
            group_name = group_name.fillna(clean_card)
        group_name = group_name.fillna("未知")
    elif clean_card is not None:
        group_name = clean_card.fillna("未知")
    else:
        group_name = pd.Series("未知", index=df.index)

    # 分组键2：交易账号为空回退到（清理后的）卡号
    if clean_acct is not None:
        acct_series = clean_acct
        has_acct = acct_series.notna() & (acct_series != "") & (acct_series != "nan")
        group_acct = acct_series.where(has_acct, other=None)
        if clean_card is not None:
            group_acct = group_acct.fillna(clean_card)
        group_acct = group_acct.fillna("")
    elif clean_card is not None:
        group_acct = clean_card.fillna("")
    else:
        group_acct = pd.Series("", index=df.index)

    df["_分组键"] = group_name
    df["_分组账号"] = group_acct
    return df


def split_by_account(
    detail_csv_path: str,
    output_dir: str,
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None
) -> list[str]:
    """
    将交易明细表按 银行来源 + 户名 + 交易账号 分组输出。

    分组规则：
    - 同一户名、同一银行、同一交易账号 → 一张分表（即使有多个卡号）
    - 同一户名、同一银行、不同交易账号 → 不同分表
    - 户名为空时用交易卡号代替

    排序规则：
    - 每张分表内：按交易卡号（升序）→ 交易时间（升序）

    使用流式分块处理：每次加载 10 万行，分块计算分组键后追加到各组临时 CSV，
    最后将各组 CSV 转 XLSX。避免大数据量（300 万+行）时内存溢出。

    返回生成的文件路径列表。
    """
    os.makedirs(output_dir, exist_ok=True)

    # 先读表头确定列位置
    df_head = pd.read_csv(detail_csv_path, nrows=0)
    columns = list(df_head.columns)

    bank_col = find_column(columns, "银行来源")
    name_col = find_column(columns, "交易户名")
    card_col = find_column(columns, "交易卡号")
    account_col = find_column(columns, "交易账号")
    time_col = find_column(columns, "交易时间")

    if bank_col is None:
        if error_logger:
            error_logger.error("分表失败: 找不到'银行来源'列")
        return []

    # === 流式分块处理 ===
    CHUNK_SIZE = 100000
    group_info = {}    # key → {"path": temp_csv, "card_num": str}
    group_order = []   # 保持分组发现顺序

    for chunk_idx, chunk in enumerate(
        pd.read_csv(detail_csv_path, dtype=str, keep_default_na=False, chunksize=CHUNK_SIZE)
    ):
        # 向量化计算分组键（关键优化：替代 apply(axis=1)）
        chunk = _add_group_keys_vectorized(chunk, name_col, card_col, account_col)

        # 按 银行 + 户名 + 账号 分组
        for (bank, name, acct), group in chunk.groupby([bank_col, "_分组键", "_分组账号"]):
            key = (str(bank), str(name), str(acct))

            # 去掉辅助列
            group = group.drop(columns=["_分组键", "_分组账号"])

            if key not in group_info:
                # 获取代表性卡号（去 _ 后缀和 - 前缀）
                card_num = "无卡号"
                if card_col:
                    card_vals = group[card_col].replace("nan", "").replace("", pd.NA).dropna()
                    if len(card_vals) > 0:
                        card_num = _clean_detail_key(str(card_vals.iloc[0]))

                tmp_path = os.path.join(output_dir, f"_tmp_group_{len(group_info)}.csv")
                group_info[key] = {"path": tmp_path, "card_num": card_num}
                group_order.append(key)
                group.to_csv(tmp_path, index=False, encoding="utf-8-sig")
            else:
                group.to_csv(
                    group_info[key]["path"], mode="a", header=False,
                    index=False, encoding="utf-8-sig"
                )

        if progress_callback and chunk_idx % 5 == 0:
            progress_callback(f"分块处理中...", 50.0)

    if progress_callback:
        progress_callback("分块处理完成，正在生成分表...", 80.0)

    # === 各组临时 CSV → XLSX ===
    output_files = []
    total_groups = len(group_order)

    for idx, key in enumerate(group_order):
        info = group_info[key]
        bank, name, acct = key

        safe_bank = _safe_filename(bank)
        safe_name = _safe_filename(name)
        safe_card = _safe_filename(info["card_num"])

        filename = f"{safe_name}_{safe_bank}_{safe_card}.xlsx"
        filepath = os.path.join(output_dir, filename)

        if progress_callback:
            progress_callback(f"输出分表: {filename}", 80 + (idx / max(total_groups, 1)) * 20)

        # 读取该组临时 CSV，排序后写出 XLSX
        try:
            group_df = pd.read_csv(info["path"], dtype=str, keep_default_na=False)
        except Exception:
            continue

        # 分表内排序：卡号升序 → 交易时间升序
        sort_cols = []
        if card_col:
            sort_cols.append(card_col)
        if time_col:
            sort_cols.append(time_col)
        if sort_cols:
            group_df = group_df.sort_values(by=sort_cols, ascending=True)

        # 内联金额格式化（避免 converter.format_amount_columns 二次读取）
        _format_amount_inline(group_df)

        # 清理 Excel 非法控制字符（如 \x1c / \x10），防止 openpyxl 写入分表时报错
        # 兼容 pandas>=3.0：dtype=str 返回 string 类型而非 object，用 is_string_dtype 判断
        for col in group_df.columns:
            if pd.api.types.is_string_dtype(group_df[col]):
                group_df[col] = group_df[col].astype(str).str.replace(
                    ILLEGAL_XML_CHARS_RE, "", regex=True
                )

        # 共用最终 XLSX 写入器，确保金额为数值且显示两位小数。
        from core.converter import _write_single_xlsx
        _write_single_xlsx(group_df, filepath)
        output_files.append(filepath)

        # 清理临时 CSV
        try:
            os.remove(info["path"])
        except Exception:
            pass

    if error_logger:
        error_logger.info(f"分表完成: 生成 {len(output_files)} 个文件")

    if progress_callback:
        progress_callback("分表完成", 100.0)

    return output_files
