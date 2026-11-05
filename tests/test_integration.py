"""端到端集成测试：模拟完整的处理流程（CSV 中间格式 + 最终 XLSX 输出）"""
import sys
sys.path.insert(0, '.')
import os
import tempfile
import zipfile
import pandas as pd
from core.pipeline import Pipeline


def create_test_csv(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def create_zip(zip_path, files_dict):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, src in files_dict.items():
            zf.write(src, arcname)


def test_full_pipeline():
    """端到端：银行ZIP=银行名+类型.zip，每ZIP仅含一个CSV"""
    with tempfile.TemporaryDirectory() as tmp:
        # === 工商银行 数据 ===
        detail_a = os.path.join(tmp, "工行_交易明细.csv")
        create_test_csv(detail_a, (
            "交易卡号,交易时间,交易金额,交易余额,收付标志,交易对手账卡号,交易户名,交易证件号码,交易账号\n"
            "C001,2024-01-01,100,50,出,X001,,,A001\n"
            "C002,2024-01-02,200,100,出,X002,李四,ID002,A002\n"
            "C001,,100,50,出,X001,张三,ID001,A001\n"
        ))
        personnel_a = os.path.join(tmp, "工行_人员.csv")
        create_test_csv(personnel_a, "姓名,身份证号\n张三,3200001\n")
        account_a = os.path.join(tmp, "工行_账户.csv")
        create_test_csv(account_a, "交易卡号,交易账号,交易户名,交易证件号码\nC001,A001,张三,ID001\nC002,A002,李四,ID002\n")
        sub_a = os.path.join(tmp, "工行_关联子账户.csv")
        create_test_csv(sub_a, "主子账户,关联状态\n主1-子1,激活\n")

        bank_a_detail_zip = os.path.join(tmp, "工商银行交易明细信息.zip")
        create_zip(bank_a_detail_zip, {"工商银行交易明细信息.csv": detail_a})
        bank_a_personnel_zip = os.path.join(tmp, "工商银行人员信息.zip")
        create_zip(bank_a_personnel_zip, {"工商银行人员信息.csv": personnel_a})
        bank_a_account_zip = os.path.join(tmp, "工商银行账户信息.zip")
        create_zip(bank_a_account_zip, {"工商银行账户信息.csv": account_a})
        bank_a_sub_zip = os.path.join(tmp, "工商银行关联子账户信息.zip")
        create_zip(bank_a_sub_zip, {"工商银行关联子账户信息.csv": sub_a})

        # === 建设银行 数据 ===
        detail_b = os.path.join(tmp, "建行_交易明细.csv")
        create_test_csv(detail_b, (
            "交易卡号,交易时间,交易金额,交易余额,收付标志,交易对手账卡号,交易户名,交易证件号码,交易账号\n"
            "C003,2024-02-01,300,150,入,Y001,王五,ID003,A003\n"
        ))
        personnel_b = os.path.join(tmp, "建行_人员.csv")
        create_test_csv(personnel_b, "姓名,身份证号\n王五,3200003\n")
        account_b = os.path.join(tmp, "建行_账户.csv")
        create_test_csv(account_b, "交易卡号,交易账号,交易户名,交易证件号码\nC003,A003,王五,ID003\n")
        sub_b = os.path.join(tmp, "建行_关联子账户.csv")
        create_test_csv(sub_b, "主子账户,关联状态\n主2-子2,激活\n")

        bank_b_detail_zip = os.path.join(tmp, "建设银行交易明细信息.zip")
        create_zip(bank_b_detail_zip, {"建设银行交易明细信息.csv": detail_b})
        bank_b_personnel_zip = os.path.join(tmp, "建设银行人员信息.zip")
        create_zip(bank_b_personnel_zip, {"建设银行人员信息.csv": personnel_b})
        bank_b_account_zip = os.path.join(tmp, "建设银行账户信息.zip")
        create_zip(bank_b_account_zip, {"建设银行账户信息.csv": account_b})
        bank_b_sub_zip = os.path.join(tmp, "建设银行关联子账户信息.zip")
        create_zip(bank_b_sub_zip, {"建设银行关联子账户信息.csv": sub_b})

        # 顶层任务 CSV
        task_success = os.path.join(tmp, "任务信息(成功).csv")
        create_test_csv(task_success, "任务ID,状态\nT1,成功\n")
        task_fail = os.path.join(tmp, "任务信息(失败).csv")
        create_test_csv(task_fail, "任务ID,状态\nT2,失败\n")

        # 打包案件 ZIP
        case_zip = os.path.join(tmp, "案件A.zip")
        create_zip(case_zip, {
            "工商银行交易明细信息.zip": bank_a_detail_zip,
            "工商银行人员信息.zip": bank_a_personnel_zip,
            "工商银行账户信息.zip": bank_a_account_zip,
            "工商银行关联子账户信息.zip": bank_a_sub_zip,
            "建设银行交易明细信息.zip": bank_b_detail_zip,
            "建设银行人员信息.zip": bank_b_personnel_zip,
            "建设银行账户信息.zip": bank_b_account_zip,
            "建设银行关联子账户信息.zip": bank_b_sub_zip,
            "任务信息(成功).csv": task_success,
            "任务信息(失败).csv": task_fail,
        })

        # === 运行 Pipeline ===
        output_dir = os.path.join(tmp, "output")
        pipeline = Pipeline([case_zip], output_dir, keep_temp=True, stop_on_error=True)
        success = pipeline.run()

        assert success, "Pipeline 应该成功完成"

        # === 验证输出 XLSX ===
        expected_files = [
            "交易明细信息_合并.xlsx",
            "人员信息_合并.xlsx",
            "账户信息_合并.xlsx",
            "关联子账户信息_合并.xlsx",
            "任务信息(成功)_合并.xlsx",
            "任务信息(失败)_合并.xlsx",
        ]
        for fname in expected_files:
            fpath = os.path.join(output_dir, fname)
            assert os.path.exists(fpath), f"缺少文件: {fname}"

        # V1.9：交易时间为空但金额有值的行保留，4 行均保留
        detail_df = pd.read_excel(
            os.path.join(output_dir, "交易明细信息_合并.xlsx"),
            dtype=str, keep_default_na=False
        )
        assert len(detail_df) == 4, f"交易明细应有4行, 实际: {len(detail_df)}"
        assert detail_df.iloc[0]["交易户名"] == "张三"

        # 分表
        split_dir = os.path.join(output_dir, "分表")
        assert os.path.exists(split_dir)
        split_files = os.listdir(split_dir)
        assert len(split_files) >= 2, f"分表数量不足: {split_files}"

        # 错误日志
        log_path = os.path.join(output_dir, "error.log")
        assert os.path.exists(log_path)

        # 人员信息合并：2行
        personnel_df = pd.read_excel(
            os.path.join(output_dir, "人员信息_合并.xlsx"),
            dtype=str, keep_default_na=False
        )
        assert len(personnel_df) == 2, f"人员信息应有2行, 实际: {len(personnel_df)}"


def test_pipeline_handles_duplicate_detail():
    """测试去重功能"""
    with tempfile.TemporaryDirectory() as tmp:
        detail = os.path.join(tmp, "detail.csv")
        create_test_csv(detail, (
            "交易卡号,交易时间,交易金额,收付标志,交易对手账卡号,交易余额,交易户名,交易证件号码,交易账号\n"
            "C001,2024-01-01,100,出,X001,50,张三,ID001,A001\n"
            "C001,2024-01-01,100,出,X001,50,张三,ID001,A001\n"
        ))
        account = os.path.join(tmp, "account.csv")
        create_test_csv(account, "交易卡号,交易账号,交易户名,交易证件号码\nC001,A001,张三,ID001\n")

        bank_detail_zip = os.path.join(tmp, "测试银行交易明细信息.zip")
        create_zip(bank_detail_zip, {"测试银行交易明细信息.csv": detail})
        bank_account_zip = os.path.join(tmp, "测试银行账户信息.zip")
        create_zip(bank_account_zip, {"测试银行账户信息.csv": account})

        case_zip = os.path.join(tmp, "案件.zip")
        create_zip(case_zip, {
            "测试银行交易明细信息.zip": bank_detail_zip,
            "测试银行账户信息.zip": bank_account_zip,
        })

        output_dir = os.path.join(tmp, "output")
        pipeline = Pipeline([case_zip], output_dir, keep_temp=True, stop_on_error=True)
        success = pipeline.run()
        assert success

        detail_result = pd.read_excel(
            os.path.join(output_dir, "交易明细信息_合并.xlsx"),
            dtype=str, keep_default_na=False
        )
        assert len(detail_result) == 1, f"去重后应有1行, 实际: {len(detail_result)}"


def test_pipeline_keeps_rows_with_different_balance():
    """V1.8 端到端：同卡同秒同金额同对手、仅交易余额不同的两笔交易都必须保留。"""
    with tempfile.TemporaryDirectory() as tmp:
        detail = os.path.join(tmp, "detail.csv")
        create_test_csv(detail, (
            "交易卡号,交易时间,交易金额,交易余额,收付标志,交易对手账卡号,交易户名,交易证件号码,交易账号\n"
            "C001,2024-01-01 10:00:00,100,900,出,X001,张三,ID001,A001\n"
            "C001,2024-01-01 10:00:00,100,800,出,X001,张三,ID001,A001\n"
            "C001,2024-01-01 10:00:00,100,800,出,X001,张三,ID001,A001\n"
        ))
        account = os.path.join(tmp, "account.csv")
        create_test_csv(account, "交易卡号,交易账号,交易户名,交易证件号码\nC001,A001,张三,ID001\n")

        bank_detail_zip = os.path.join(tmp, "测试银行交易明细信息.zip")
        create_zip(bank_detail_zip, {"测试银行交易明细信息.csv": detail})
        bank_account_zip = os.path.join(tmp, "测试银行账户信息.zip")
        create_zip(bank_account_zip, {"测试银行账户信息.csv": account})

        case_zip = os.path.join(tmp, "案件.zip")
        create_zip(case_zip, {
            "测试银行交易明细信息.zip": bank_detail_zip,
            "测试银行账户信息.zip": bank_account_zip,
        })

        output_dir = os.path.join(tmp, "output")
        pipeline = Pipeline([case_zip], output_dir, keep_temp=True, stop_on_error=True)
        assert pipeline.run()

        detail_result = pd.read_excel(
            os.path.join(output_dir, "交易明细信息_合并.xlsx"),
            dtype=str, keep_default_na=False
        )
        # 3 行中：余额 900 / 800 各保留 1 行，完全重复的那 1 行被去掉 → 2 行
        assert len(detail_result) == 2, f"应保留余额不同的 2 笔交易, 实际: {len(detail_result)}"
        assert sorted(detail_result["交易余额"].tolist()) == ["800", "900"]


def test_v19_transaction_pipeline_full_sequence():
    """V1.9：全字段去重、同时空删除、双键补全、标准化、六字段最终去重。"""
    with tempfile.TemporaryDirectory() as tmp:
        detail = os.path.join(tmp, "detail.csv")
        create_test_csv(detail, (
            "交易卡号,交易账号,交易时间,交易金额,交易余额,收付标志,交易对手账卡号,交易户名,交易证件号码\n"
            " C001 ,A001, 2024-01-01 10:00:00 , 100.20 , 50 ,D, X , ,\n"
            "C001,A001,2024-01-01 10:00:00,100.2,50,d,X,其他名,\n"
            ",A002,, 10 ,20,1,Z,,\n"
            ",,,,30,2,EMPTY,,\n"
            "C003,,2024-01-03 10:00:00,20.126,1,转出,Y,,\n"
            "C999,A999,2024-01-04 10:00:00,30,2,特殊,U,,\n"
            "  C001 , A001 , 2024-01-01 10:00:00 , 100.20 , 50 , D , X , , \n"
        ))
        account = os.path.join(tmp, "account.csv")
        create_test_csv(account, (
            "交易卡号,交易账号,交易户名,交易证件号码\n"
            "C001,A001,张三,ID001\n"
            "C002,A002,李四,ID002\n"
            "C003,A003,王五,ID003\n"
        ))

        bank_detail_zip = os.path.join(tmp, "测试银行交易明细信息.zip")
        create_zip(bank_detail_zip, {"测试银行交易明细信息.csv": detail})
        bank_account_zip = os.path.join(tmp, "测试银行账户信息.zip")
        create_zip(bank_account_zip, {"测试银行账户信息.csv": account})
        case_zip = os.path.join(tmp, "案件.zip")
        create_zip(case_zip, {
            "测试银行交易明细信息.zip": bank_detail_zip,
            "测试银行账户信息.zip": bank_account_zip,
        })

        output_dir = os.path.join(tmp, "output")
        assert Pipeline([case_zip], output_dir, keep_temp=True).run()

        result = pd.read_excel(
            os.path.join(output_dir, "交易明细信息_合并.xlsx"),
            dtype=str,
            keep_default_na=False,
        )
        assert len(result) == 4
        by_card = result.set_index("交易卡号")

        assert "C001" in by_card.index
        assert by_card.loc["C001", "交易户名"] == "张三"
        assert by_card.loc["C001", "收付标志"] == "出"
        assert float(by_card.loc["C001", "交易金额"]) == 100.2

        assert "C002" in by_card.index
        assert by_card.loc["C002", "交易时间"] == ""
        assert by_card.loc["C002", "交易户名"] == "李四"
        assert by_card.loc["C002", "收付标志"] == "出"

        assert "C003" in by_card.index
        assert by_card.loc["C003", "交易账号"] == "A003"
        assert by_card.loc["C003", "收付标志"] == "出"
        assert float(by_card.loc["C003", "交易金额"]) == 20.13

        assert "C999" in by_card.index
        assert by_card.loc["C999", "交易户名"] == ""
        assert by_card.loc["C999", "收付标志"] == "特殊"
