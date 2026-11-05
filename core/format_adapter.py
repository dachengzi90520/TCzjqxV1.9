"""V1.7 新版反馈包适配层。

旧版（V1.6）反馈包：每个银行一个明细 ZIP，文件名为 "{银行名}{类型}.zip"。
新版（V1.7）反馈包：交易明细升级为"逐卡"模式，文件名为 "{银行名}交易明细信息({卡号}).zip"，
一个 ZIP 对应一张卡，卡号写在文件名括号内，可能带批量后缀 _001 / _000000。

本模块只做"新增适配"，不改动 V1.6 原有处理逻辑：
- is_new_format(): 判断输入包是否为新版逐卡格式。
- adapt_new_format(): 用文件名里的卡号，把逐卡明细 CSV 中为空的"交易卡号"补全，
  使下游去重/补全/分表能正确按键处理。非空单元格不做任何改动。
"""
import os
import zipfile
from typing import Callable

from utils.config import parse_bank_zip_name_v2, find_column
from utils.csv_utils import read_csv_auto


def is_new_format(input_zips) -> bool:
    """判断输入包是否为"新版逐卡"格式。

    规则：顶层 ZIP 内存在任意一个 {银行名}交易明细信息({卡号}).zip 且括号内为有效卡号。
    """
    for zp in input_zips:
        if not isinstance(zp, str) or not os.path.isfile(zp):
            continue
        try:
            with zipfile.ZipFile(zp) as z:
                for n in z.namelist():
                    base = os.path.basename(n)
                    if not base.lower().endswith(".zip"):
                        continue
                    parsed = parse_bank_zip_name_v2(base)
                    if parsed and parsed[1] == "交易明细信息" and parsed[2]:
                        return True
        except Exception:
            continue
    return False


def _card_of_csv(csv_path: str) -> str:
    """从逐卡明细 CSV 的文件名中解析卡号（CSV 名与来源 ZIP 名一致）。"""
    parsed = parse_bank_zip_name_v2(os.path.basename(csv_path))
    return parsed[2] if parsed else ""


def normalize_detail_card_cols(csv_path: str, card: str, target_cols=("交易卡号",)) -> int:
    """把逐卡明细 CSV 中为空的"交易卡号"用文件名的卡号补全。

    文件名的卡号即"交易卡号"，因此只补 交易卡号（避免用卡号误填不同的"交易账号"）。
    仅补空单元格，非空单元格不动；返回补全的单元格数。
    """
    if not card:
        return 0
    df = read_csv_auto(csv_path)
    filled = 0
    for kw in tuple(target_cols):
        col = find_column(list(df.columns), kw)
        if col is None:
            continue
        s = df[col].astype(str).str.strip()
        empty = s.isna() | (s == "") | (s == "nan")
        if empty.any():
            df.loc[empty, col] = card
            filled += int(empty.sum())
    if filled:
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return filled


def adapt_new_format(
    collected: dict,
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None,
) -> int:
    """对已归类收集的结果（extract_all 的返回）执行新版适配。

    遍历"交易明细信息"分类下的每个逐卡 CSV，用文件名卡号补全为空的"交易卡号"。
    返回补全的单元格总数。非新版（无卡号）时不做任何改动。
    """
    detail_files = collected.get("交易明细信息", []) or []
    total = len(detail_files)
    filled_total = 0
    for idx, (bank, csv_path) in enumerate(detail_files):
        base = os.path.basename(csv_path)
        card = _card_of_csv(csv_path)
        if progress_callback:
            progress_callback(f"新版适配: {base}", (idx / max(total, 1)) * 100)
        try:
            filled = normalize_detail_card_cols(csv_path, card)
        except Exception as e:
            if error_logger:
                error_logger.error(f"新版适配失败: {base}, {e}")
            continue
        filled_total += filled
        if error_logger and filled:
            error_logger.info(f"新版适配: {base} 用文件名卡号补全 {filled} 个单元格")
    if error_logger:
        error_logger.info(f"新版格式适配完成: 用文件名卡号补全 {filled_total} 个单元格")
    return filled_total
