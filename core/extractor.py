"""ZIP 解压模块：解析银行ZIP文件名获取银行名和CSV类型，按类型收集CSV"""
import os
import zipfile
import shutil
from typing import Callable
from utils.config import parse_bank_zip_name, get_output_category


def _extract_zip_safe(zip_path: str, dest_dir: str) -> list[str]:
    """安全解压一个 ZIP 到目标目录，返回解压出的文件路径列表"""
    extracted = []
    os.makedirs(dest_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                member_path = os.path.normpath(member)
                if member_path.startswith("..") or os.path.isabs(member_path):
                    continue
                if member.endswith("/") or member.endswith("\\"):
                    continue
                zf.extract(member, dest_dir)
                extracted.append(os.path.join(dest_dir, member))
    except Exception as e:
        raise RuntimeError(f"解压失败 {zip_path}: {e}")
    return extracted


def extract_all(
    user_zips: list[str],
    output_dir: str,
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None
) -> dict:
    """
    解压所有用户选择的 ZIP 文件，按 CSV 类型归类收集。

    返回结构（与 merger.collect_all_csvs 兼容）:
    {
        "交易明细信息": [("莱商银行股份有限公司", "/path/to/交易明细信息.csv"), ...],
        "人员信息": [("莱商银行股份有限公司", "/path/to/人员信息.csv"), ...],
        "账户信息": [...],
        "关联子账户信息": [...],
        "强制措施信息": [...],
        "任务信息(成功)": [("全局", "/path/to/任务信息(成功).csv"), ...],
        "任务信息(失败)": [...],
    }
    """
    collected: dict[str, list[tuple[str, str]]] = {}
    total_cases = len(user_zips)

    for case_idx, zip_path in enumerate(user_zips):
        case_name = os.path.splitext(os.path.basename(zip_path))[0]
        case_dir = os.path.join(output_dir, case_name)
        os.makedirs(case_dir, exist_ok=True)

        if progress_callback:
            progress_callback(f"解压案件: {case_name}", (case_idx / total_cases) * 100)

        # 第一层：解压用户 ZIP
        first_level_files = _extract_zip_safe(zip_path, case_dir)

        for file_path in first_level_files:
            basename = os.path.basename(file_path)

            if basename.lower().endswith(".zip"):
                # === 银行 ZIP：文件名 = 银行名 + CSV类型 ===
                parsed = parse_bank_zip_name(basename)
                if parsed is None:
                    if error_logger:
                        error_logger.warning(f"无法识别银行ZIP类型: {basename}")
                    continue

                bank_name, csv_type = parsed

                # 解压银行 ZIP，取到唯一的 CSV
                bank_extract_dir = os.path.join(case_dir, f"_bank_{bank_name}_{csv_type}")
                csv_files = _extract_zip_safe(file_path, bank_extract_dir)

                # 收集此银行 ZIP 中的所有 CSV（通常只有1个）
                for csv_path in csv_files:
                    if csv_path.lower().endswith(".csv"):
                        if csv_type not in collected:
                            collected[csv_type] = []
                        collected[csv_type].append((bank_name, csv_path))

            elif basename.lower().endswith(".csv"):
                # === 顶层 CSV（任务信息）===
                category = get_output_category(basename)
                if category:
                    if category not in collected:
                        collected[category] = []
                    collected[category].append(("全局", file_path))
                elif error_logger:
                    error_logger.warning(f"无法识别顶层CSV类型: {basename}")

    if progress_callback:
        progress_callback("解压完成", 100.0)

    return collected
