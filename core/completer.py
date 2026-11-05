"""信息补全：从账户信息表补充交易明细中的户名和证件号码（向量化实现）"""
import os
import pandas as pd
from typing import Callable
from utils.config import find_column


def _clean_key(value: str) -> str:
    """
    清理账户信息表侧的卡号/账号附加字符（用于构建匹配索引）。

    处理规则（按顺序）：
    1. "-" 前缀：删除 "-" 及其之前的所有字符（银行系统代号前缀）
       例如 "123456-7890123456789" → "7890123456789"
    2. "_" 后缀：删除第一个 "_" 及其之后的所有字符（批次号_序号）
       例如 "6217002210035674693_156_1" → "6217002210035674693"

    两种规则可组合生效：
       例如 "123456-7890123456789_156_1" → "7890123456789_156_1" → "7890123456789"
    """
    if not value:
        return ""
    # 第一步：删除 "-" 及其之前的所有字符（银行系统前缀）
    dash_pos = value.find("-")
    if dash_pos >= 0:
        value = value[dash_pos + 1:]
    # 第二步：删除第一个 "_" 及其之后的所有字符（批次号_序号）
    underscore_pos = value.find("_")
    if underscore_pos > 0:
        return value[:underscore_pos]
    return value


def _clean_detail_key(value: str) -> str:
    """
    清理交易明细侧的卡号/账号附加字符（用于匹配查询）。

    处理规则（按顺序）：
    1. "-" 后缀：删除 "-" 及其之后的所有字符（调证序号后缀）
       例如 "6222021234567890-001" → "6222021234567890"
    2. "_" 后缀：删除第一个 "_" 及其之后的所有字符（批次号_序号）
       例如 "6217002210035674693_156_1" → "6217002210035674693"

    两种规则可组合生效：
       例如 "6222021234567890-001_156" → "6222021234567890-001" → "6222021234567890"
    """
    if not value:
        return ""
    # 第一步：删除第一个 "-" 及其之后的所有字符（调证序号后缀）
    dash_pos = value.find("-")
    if dash_pos >= 0:
        value = value[:dash_pos]
    # 第二步：删除第一个 "_" 及其之后的所有字符（批次号_序号）
    underscore_pos = value.find("_")
    if underscore_pos > 0:
        return value[:underscore_pos]
    return value


def _find_any_column(columns: list[str], keywords: list[str]) -> str | None:
    """从列名列表中查找第一个匹配任意关键词的列名"""
    for kw in keywords:
        col = find_column(columns, kw)
        if col:
            return col
    return None


def _first_value_map(keys: pd.Series, values: pd.Series) -> dict[str, str]:
    """按 VLOOKUP 的“首个匹配”语义构建映射，忽略空键。"""
    result: dict[str, str] = {}
    for key, value in zip(keys, values):
        key = _clean_key(str(key).strip())
        if not key or key == "nan" or key in result:
            continue
        result[key] = "" if value is None else str(value).strip()
    return result


def _account_lookups(account_df: pd.DataFrame) -> dict:
    """构建账户信息表的卡号/账号、户名、证件号码查询表。"""
    columns = list(account_df.columns)
    card_col = _find_any_column(columns, ["交易卡号", "卡号"])
    account_col = _find_any_column(columns, ["交易账号", "账号"])
    name_col = _find_any_column(columns, [
        "交易户名", "账户开户名称", "客户名称", "户名", "开户名称", "姓名"
    ])
    id_col = _find_any_column(columns, [
        "交易证件号码", "开户人证件号码", "证件号码", "身份证号", "身份证"
    ])

    lookups = {
        "card_col": card_col,
        "account_col": account_col,
        "name_col": name_col,
        "id_col": id_col,
        "card_to_account": {},
        "account_to_card": {},
        "card_to_name": {},
        "card_to_id": {},
        "account_to_name": {},
        "account_to_id": {},
    }
    if not card_col or not account_col:
        return lookups

    cards = account_df[card_col]
    accounts = account_df[account_col]
    clean_cards = cards.astype(str).str.strip().map(_clean_key)
    clean_accounts = accounts.astype(str).str.strip().map(_clean_key)
    lookups["card_to_account"] = _first_value_map(clean_cards, accounts.map(_clean_key))
    lookups["account_to_card"] = _first_value_map(clean_accounts, cards.map(_clean_key))

    if name_col:
        names = account_df[name_col]
        lookups["card_to_name"] = _first_value_map(clean_cards, names)
        lookups["account_to_name"] = _first_value_map(clean_accounts, names)
    if id_col:
        ids = account_df[id_col]
        lookups["card_to_id"] = _first_value_map(clean_cards, ids)
        lookups["account_to_id"] = _first_value_map(clean_accounts, ids)
    return lookups


def _clean_detail_series(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """返回交易流水键的后缀模式、前缀模式清理结果。"""
    source = series.astype(str).str.strip()
    return source.map(_clean_detail_key), source.map(_clean_key)


def _map_with_prefix_fallback(
    suffix_keys: pd.Series,
    prefix_keys: pd.Series,
    mapping: dict[str, str],
) -> pd.Series:
    """后缀匹配优先；未命中时回退到前缀匹配。"""
    suffix_values = suffix_keys.map(mapping)
    prefix_values = prefix_keys.map(mapping)
    return suffix_values.where(suffix_values.notna(), prefix_values)


def fill_missing_account_keys(
    detail_df: pd.DataFrame,
    account_df: pd.DataFrame,
) -> pd.DataFrame:
    """V1.9 第 4 步：按账户表的卡号/账号对应关系补齐空白键。"""
    detail_cols = list(detail_df.columns)
    detail_card_col = _find_any_column(detail_cols, ["交易卡号", "卡号"])
    detail_account_col = _find_any_column(detail_cols, ["交易账号", "账号"])
    lookups = _account_lookups(account_df)
    if not all([
        detail_card_col,
        detail_account_col,
        lookups["card_col"],
        lookups["account_col"],
    ]):
        return detail_df

    card_suffix, card_prefix = _clean_detail_series(detail_df[detail_card_col])
    acct_suffix, acct_prefix = _clean_detail_series(detail_df[detail_account_col])

    account_empty = _blank_series(detail_df[detail_account_col])
    account_fill = _map_with_prefix_fallback(
        card_suffix, card_prefix, lookups["card_to_account"]
    )
    fill_account = account_empty & account_fill.notna() & (account_fill != "")
    detail_df.loc[fill_account, detail_account_col] = account_fill[fill_account]

    card_empty = _blank_series(detail_df[detail_card_col])
    card_fill = _map_with_prefix_fallback(
        acct_suffix, acct_prefix, lookups["account_to_card"]
    )
    fill_card = card_empty & card_fill.notna() & (card_fill != "")
    detail_df.loc[fill_card, detail_card_col] = card_fill[fill_card]
    return detail_df


def _blank_series(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip()
    return series.isna() | values.isin(["", "nan", "None"])


def fill_missing_identity(
    detail_df: pd.DataFrame,
    account_df: pd.DataFrame,
) -> pd.DataFrame:
    """V1.9 第 5 步：用已补全的卡号/账号填入空白户名和证件号码。"""
    detail_cols = list(detail_df.columns)
    detail_card_col = _find_any_column(detail_cols, ["交易卡号", "卡号"])
    detail_account_col = _find_any_column(detail_cols, ["交易账号", "账号"])
    detail_name_col = _find_any_column(detail_cols, [
        "交易户名", "账户开户名称", "客户名称", "户名"
    ])
    detail_id_col = _find_any_column(detail_cols, [
        "交易证件号码", "开户人证件号码", "证件号码", "身份证号", "身份证"
    ])
    lookups = _account_lookups(account_df)

    if not all([
        detail_card_col,
        detail_account_col,
        detail_name_col,
        detail_id_col,
        lookups["name_col"],
        lookups["id_col"],
    ]):
        return detail_df

    card_suffix, card_prefix = _clean_detail_series(detail_df[detail_card_col])
    acct_suffix, acct_prefix = _clean_detail_series(detail_df[detail_account_col])

    card_name = _map_with_prefix_fallback(
        card_suffix, card_prefix, lookups["card_to_name"]
    )
    card_id = _map_with_prefix_fallback(
        card_suffix, card_prefix, lookups["card_to_id"]
    )
    acct_name = _map_with_prefix_fallback(
        acct_suffix, acct_prefix, lookups["account_to_name"]
    )
    acct_id = _map_with_prefix_fallback(
        acct_suffix, acct_prefix, lookups["account_to_id"]
    )

    poor_name = card_name.isna() | card_name.isin(["", "nan", "None"])
    poor_id = card_id.isna() | card_id.isin(["", "nan", "None"])
    acct_has_name = acct_name.notna() & ~acct_name.isin(["", "nan", "None"])
    use_account = poor_name & poor_id & acct_has_name

    final_name = card_name.where(~use_account, acct_name)
    final_id = card_id.where(~use_account, acct_id)

    fill_name = _blank_series(detail_df[detail_name_col]) & final_name.notna()
    fill_name &= ~final_name.isin(["", "nan", "None"])
    detail_df.loc[fill_name, detail_name_col] = final_name[fill_name]

    fill_id = _blank_series(detail_df[detail_id_col]) & final_id.notna()
    fill_id &= ~final_id.isin(["", "nan", "None"])
    detail_df.loc[fill_id, detail_id_col] = final_id[fill_id]
    return detail_df


def complete_transaction_detail(
    detail_df: pd.DataFrame,
    account_df: pd.DataFrame
) -> pd.DataFrame:
    """
    V1.9 第 4、5 步：先补齐空白卡号/账号，再补户名和证件号码。
    """
    detail_df = fill_missing_account_keys(detail_df, account_df)
    return fill_missing_identity(detail_df, account_df)


def complete_all(
    csv_files: list[str],
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None
) -> int:
    """
    从 csv_files 中找到交易明细和账户信息 CSV，执行补全。
    返回补全的行数。
    """
    from utils.csv_utils import read_csv_auto

    detail_path = None
    account_path = None

    for path in csv_files:
        basename = os.path.basename(path)
        if "交易明细" in basename:
            detail_path = path
        elif "账户信息" in basename and "关联" not in basename and "子账户" not in basename:
            account_path = path

    if not detail_path or not account_path:
        if error_logger:
            error_logger.warning("补全跳过: 找不到交易明细或账户信息表")
        return 0

    if progress_callback:
        progress_callback("补全: 交易户名和证件号码", 50.0)

    detail_df = read_csv_auto(detail_path)
    account_df = read_csv_auto(account_path)

    # 统计补全前空值
    name_col = _find_any_column(list(detail_df.columns), [
        "交易户名", "账户开户名称", "客户名称", "户名"
    ])
    before_empty = 0
    if name_col:
        before_empty = (detail_df[name_col] == "").sum()

    detail_df = complete_transaction_detail(detail_df, account_df)

    after_empty = 0
    if name_col:
        after_empty = (detail_df[name_col] == "").sum()

    filled = before_empty - after_empty
    detail_df.to_csv(detail_path, index=False, encoding="utf-8-sig")

    if error_logger:
        error_logger.info(f"补全完成: 填充了 {filled} 行")

    return filled
