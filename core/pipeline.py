"""流程编排：串联所有处理步骤，提供统一的进度和错误回调"""
import os
import shutil
import tempfile
import time
from datetime import datetime
from core.extractor import extract_all
from core.merger import merge_csvs
from core.converter import final_output, clean_account_card_numbers
from core.deduper import deduplicate_all
from core.cleaner import clean_all, normalize_all
from core.completer import complete_all
from core.format_adapter import is_new_format, adapt_new_format
from utils.config import DEDUP_COLS_DETAIL
from utils.logger import ErrorLogger


class Pipeline:
    def __init__(
        self,
        input_zips: list[str],
        output_dir: str,
        keep_temp: bool = False,
        stop_on_error: bool = True
    ):
        self.input_zips = input_zips
        self.output_dir = output_dir
        self.keep_temp = keep_temp
        self.stop_on_error = stop_on_error
        self.temp_dir = None
        self.logger = None
        self._progress = None
        self._cancel_requested = False

    @property
    def progress(self) -> tuple[str, float, str]:
        return self._progress or ("就绪", 0.0, "")

    def request_cancel(self):
        self._cancel_requested = True

    def _report(self, detail: str, percentage: float, step_name: str = ""):
        self._progress = (step_name, percentage, detail)

    def run(self) -> bool:
        """执行完整流程，返回 True 表示成功"""
        start_time = time.time()

        try:
            os.makedirs(self.output_dir, exist_ok=True)

            log_path = os.path.join(self.output_dir, "error.log")
            self.logger = ErrorLogger(log_path)
            self.logger.info(f"=== 开始处理 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
            self.logger.info(f"输入文件: {len(self.input_zips)} 个")
            self.logger.info(f"输出目录: {self.output_dir}")

            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp(prefix="fund_clean_")

            # 检测新版（逐卡）反馈包格式（V1.7 新增适配，不改动 V1.6 原有处理）
            self.is_new_pkg = is_new_format(self.input_zips)
            if self.is_new_pkg:
                self.logger.info("检测到新版逐卡反馈包：交易明细按卡拆分，启用新增适配层")

            # === 步骤1: 解压 ===
            self._report("解压ZIP文件中...", 0.0, "步骤 1/7: 解压ZIP文件")
            extract_result = extract_all(
                self.input_zips,
                self.temp_dir,
                progress_callback=lambda msg, pct: self._report(msg, pct * 0.10, "步骤 1/7: 解压ZIP文件"),
                error_logger=self.logger
            )
            total_csvs = sum(len(v) for v in extract_result.values())
            self.logger.info(f"解压完成: {total_csvs} 个CSV文件, 分属 {len(extract_result)} 个类别")

            # === 步骤1.5: 新版逐卡格式适配（仅新版生效，旧版为无操作）===
            if self.is_new_pkg:
                self._report("适配新版逐卡格式...", 5.0, "步骤 1.5/7: 新版格式适配")
                adapt_new_format(
                    extract_result,
                    progress_callback=lambda msg, pct: self._report(msg, 5.0 + pct * 0.05, "步骤 1.5/7: 新版格式适配"),
                    error_logger=self.logger,
                )

            if self._cancel_requested:
                return False

            # === 步骤2: 合并 CSV ===
            self._report("合并CSV文件中...", 10.0, "步骤 2/7: 合并同类CSV")
            total_csvs = sum(len(v) for v in extract_result.values())
            self.logger.info(f"收集到 {total_csvs} 个CSV文件, 分属 {len(extract_result)} 个类别")

            merged_csv_dir = os.path.join(self.temp_dir, "merged_csv")
            os.makedirs(merged_csv_dir, exist_ok=True)
            merged_csvs = merge_csvs(
                extract_result,
                merged_csv_dir,
                progress_callback=lambda msg, pct: self._report(msg, 10.0 + pct * 0.10, "步骤 2/7: 合并同类CSV"),
                error_logger=self.logger
            )
            self.logger.info(f"合并完成: {len(merged_csvs)} 个合并CSV")

            if self._cancel_requested:
                return False

            # === V1.9 资金流水步骤 1-2: 清理前后空白 + 全字段去重 ===
            # 其他类型表仍按原有逻辑全字段去重，账户信息表处理不变。
            deduplicate_all(
                merged_csvs,
                dedup_cols=DEDUP_COLS_DETAIL,
                progress_callback=lambda msg, pct: self._report(
                    msg, 20.0 + pct * 0.10,
                    "资金流水 1-2/8: 清理空白并全字段去重"
                ),
                error_logger=self.logger,
                full_detail_fields=True,
            )

            if self._cancel_requested:
                return False

            # === V1.9 资金流水步骤 3: 交易时间、交易金额同时为空才删除 ===
            clean_all(
                merged_csvs,
                progress_callback=lambda msg, pct: self._report(
                    msg, 30.0 + pct * 0.06,
                    "资金流水 3/8: 删除交易时间和金额同时为空的行"
                ),
                error_logger=self.logger
            )

            if self._cancel_requested:
                return False

            # === V1.9 资金流水步骤 4-5: 先补卡号/账号，再补户名/证件号码 ===
            complete_all(
                merged_csvs,
                progress_callback=lambda msg, pct: self._report(
                    msg, 36.0 + pct * 0.12,
                    "资金流水 4-5/8: 补全账户键、户名和证件号码"
                ),
                error_logger=self.logger
            )

            if self._cancel_requested:
                return False

            # === V1.9 资金流水步骤 6-7: 金额数值化、收付标志标准化 ===
            normalize_all(
                merged_csvs,
                progress_callback=lambda msg, pct: self._report(
                    msg, 48.0 + pct * 0.12,
                    "资金流水 6-7/8: 金额数值化和收付标志标准化"
                ),
                error_logger=self.logger,
            )

            if self._cancel_requested:
                return False

            # === 账户信息表原有卡号清理规则保持不变 ===
            # 账户信息表：'-' 是银行代号前缀 → dash_mode="prefix"
            # 交易明细表：'-' 是调证序号后缀 → dash_mode="suffix"
            for csv_path in merged_csvs:
                basename = os.path.basename(csv_path)
                if "关联" in basename or "子账户" in basename:
                    continue
                if "账户信息" in basename:
                    self._report("清理账户信息表卡号", 60.0, "账户信息表原有清洗")
                    clean_account_card_numbers(csv_path, dash_mode="prefix")
                elif "交易明细" in basename:
                    self._report("清理交易明细表卡号/账号", 60.0, "资金流水附加字段清理")
                    clean_account_card_numbers(csv_path, dash_mode="suffix")

            if self._cancel_requested:
                return False

            # === V1.9 资金流水步骤 8: 标准化后按 6 列最终去重 ===
            deduplicate_all(
                merged_csvs,
                dedup_cols=DEDUP_COLS_DETAIL,
                progress_callback=lambda msg, pct: self._report(
                    msg, 62.0 + pct * 0.10,
                    "资金流水 8/8: 六字段最终去重"
                ),
                error_logger=self.logger,
            )

            if self._cancel_requested:
                return False

            # === 最终输出（汇总 XLSX + 分表）===
            self._report("生成最终 XLSX 输出...", 72.0, "最终输出")
            final_output(
                merged_csvs,
                self.output_dir,
                progress_callback=lambda msg, pct: self._report(
                    msg, 72.0 + pct * 0.28, "最终输出"
                ),
                error_logger=self.logger
            )

            elapsed = time.time() - start_time
            self.logger.info(f"=== 处理完成 === 耗时: {elapsed:.1f}秒")
            self._report("处理完成!", 100.0, "完成")

            return True

        except Exception as e:
            self.logger.error(f"处理异常: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._report(f"错误: {e}", -1, "处理失败")
            if self.stop_on_error:
                raise
            return False

        finally:
            if self.temp_dir and os.path.exists(self.temp_dir) and not self.keep_temp:
                try:
                    shutil.rmtree(self.temp_dir)
                except Exception:
                    pass

            if self.logger:
                self.logger.close()
