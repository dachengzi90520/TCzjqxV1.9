"""CSV 合并：按类别合并同类 CSV 文件（流式写入，避免大数据量内存溢出）"""
import os
import pandas as pd
from typing import Callable
from utils.csv_utils import read_csv_auto


def merge_csvs(
    collected: dict,
    output_dir: str,
    progress_callback: Callable[[str, float], None] | None = None,
    error_logger=None
) -> list[str]:
    """
    将已按类别收集的 CSV 流式合并，逐文件追加写入，不在内存中构建完整 DataFrame。

    collected 格式（由 extractor.extract_all 直接产生）:
    {
        "交易明细信息": [("银行A", "/path/to/file.csv"), ...],
        "人员信息": [...],
        ...
    }

    返回合并后的 CSV 文件路径列表。
    """
    output_files = []
    categories = list(collected.keys())
    total = len(categories)

    for idx, (category, file_list) in enumerate(collected.items()):
        if progress_callback:
            progress_callback(f"合并: {category}", (idx / total) * 100)

        if not file_list:
            continue

        safe_name = category.replace("(", "（").replace(")", "）")
        output_path = os.path.join(output_dir, f"{safe_name}_合并.csv")

        # 第一遍：扫描所有文件表头，取列并集（保证不丢失任何列）
        header_cols = ["银行来源"]
        for bank_name, csv_path in file_list:
            try:
                # 只读表头，不加载全部数据
                df_head = read_csv_auto(csv_path, nrows=0)
                for col in df_head.columns:
                    if col not in header_cols:
                        header_cols.append(col)
            except Exception:
                continue
        # 确保 "银行来源" 在最前面
        if "银行来源" in header_cols:
            header_cols.remove("银行来源")
        header_cols.insert(0, "银行来源")

        # 第二遍：流式写入
        written = False
        for bank_name, csv_path in file_list:
            try:
                df = read_csv_auto(csv_path)
            except Exception as e:
                if error_logger:
                    error_logger.error(f"读取CSV失败: {csv_path}, {e}")
                continue

            if df.empty:
                continue

            df["银行来源"] = bank_name
            # 对齐到完整列集合，缺失列填空
            df = df.reindex(columns=header_cols)

            if not written:
                df.to_csv(output_path, index=False, encoding="utf-8-sig")
                written = True
            else:
                df.to_csv(output_path, mode="a", header=False, index=False, encoding="utf-8-sig")

        if written:
            output_files.append(output_path)

    if progress_callback:
        progress_callback("合并完成", 100.0)

    return output_files
