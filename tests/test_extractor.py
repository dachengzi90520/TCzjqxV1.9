import sys
sys.path.insert(0, '.')
import os
import tempfile
import zipfile
from core.extractor import extract_all


def create_test_csv(path, content="col1,col2\nv1,v2\n"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def create_zip(zip_path, files: dict):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, src_path in files.items():
            zf.write(src_path, arcname)


def test_extract_single_case():
    """单个案件：银行ZIP(银行名+类型) + 任务CSV"""
    with tempfile.TemporaryDirectory() as tmp:
        bank_csv = os.path.join(tmp, "交易明细.csv")
        create_test_csv(bank_csv, "交易卡号,交易金额,收付标志\n123,100,出\n")

        bank_zip = os.path.join(tmp, "工商银行交易明细信息.zip")
        create_zip(bank_zip, {"工商银行交易明细信息.csv": bank_csv})

        task_success = os.path.join(tmp, "任务信息(成功).csv")
        create_test_csv(task_success, "任务流水号,状态\nT1,成功\n")
        task_fail = os.path.join(tmp, "任务信息(失败).csv")
        create_test_csv(task_fail, "任务ID\nT2\n")

        case_zip = os.path.join(tmp, "案件A.zip")
        create_zip(case_zip, {
            "工商银行交易明细信息.zip": bank_zip,
            "任务信息(成功).csv": task_success,
            "任务信息(失败).csv": task_fail,
        })

        output_dir = os.path.join(tmp, "output")
        result = extract_all([case_zip], output_dir)

        assert "交易明细信息" in result
        assert "任务信息(成功)" in result
        assert "任务信息(失败)" in result
        assert len(result["交易明细信息"]) == 1
        bank_name, csv_path = result["交易明细信息"][0]
        assert bank_name == "工商银行"
        assert os.path.exists(csv_path)


def test_extract_multi_banks_same_type():
    """多个银行同类型 ZIP"""
    with tempfile.TemporaryDirectory() as tmp:
        bank_a_csv = os.path.join(tmp, "a.csv")
        create_test_csv(bank_a_csv, "卡号\nA001\n")
        bank_a_zip = os.path.join(tmp, "工商银行交易明细信息.zip")
        create_zip(bank_a_zip, {"工商银行交易明细信息.csv": bank_a_csv})

        bank_b_csv = os.path.join(tmp, "b.csv")
        create_test_csv(bank_b_csv, "卡号\nB001\n")
        bank_b_zip = os.path.join(tmp, "建设银行交易明细信息.zip")
        create_zip(bank_b_zip, {"建设银行交易明细信息.csv": bank_b_csv})

        case_zip = os.path.join(tmp, "案件.zip")
        create_zip(case_zip, {
            "工商银行交易明细信息.zip": bank_a_zip,
            "建设银行交易明细信息.zip": bank_b_zip,
        })

        output_dir = os.path.join(tmp, "output")
        result = extract_all([case_zip], output_dir)

        assert len(result["交易明细信息"]) == 2
        banks = {name for name, _ in result["交易明细信息"]}
        assert banks == {"工商银行", "建设银行"}


def test_extract_sub_account_not_confused():
    """关联子账户信息不被误匹配为账户信息"""
    with tempfile.TemporaryDirectory() as tmp:
        sub_csv = os.path.join(tmp, "sub.csv")
        create_test_csv(sub_csv, "主子账户\n主1-子1\n")
        sub_zip = os.path.join(tmp, "莱商银行股份有限公司关联子账户信息.zip")
        create_zip(sub_zip, {"莱商银行股份有限公司关联子账户信息.csv": sub_csv})

        case_zip = os.path.join(tmp, "案件.zip")
        create_zip(case_zip, {"莱商银行股份有限公司关联子账户信息.zip": sub_zip})

        output_dir = os.path.join(tmp, "output")
        result = extract_all([case_zip], output_dir)

        assert "关联子账户信息" in result
        assert result["关联子账户信息"][0][0] == "莱商银行股份有限公司"


def test_extract_force_measure():
    """强制措施信息类型"""
    with tempfile.TemporaryDirectory() as tmp:
        force_csv = os.path.join(tmp, "force.csv")
        create_test_csv(force_csv, "账号,冻结金额\n001,100\n")
        force_zip = os.path.join(tmp, "中国建设银行强制措施信息.zip")
        create_zip(force_zip, {"中国建设银行强制措施信息.csv": force_csv})

        case_zip = os.path.join(tmp, "案件.zip")
        create_zip(case_zip, {"中国建设银行强制措施信息.zip": force_zip})

        output_dir = os.path.join(tmp, "output")
        result = extract_all([case_zip], output_dir)

        assert "强制措施信息" in result
        assert result["强制措施信息"][0][0] == "中国建设银行"


def test_extract_shared_priority_info():
    """V1.5: 支持'共有优先权信息'类型（北京银行反馈包）"""
    with tempfile.TemporaryDirectory() as tmp:
        priority_csv = os.path.join(tmp, "priority.csv")
        create_test_csv(priority_csv, "账号,优先权类型\n001,普通\n")
        priority_zip = os.path.join(tmp, "北京银行共有优先权信息.zip")
        create_zip(priority_zip, {"北京银行共有优先权信息.csv": priority_csv})

        case_zip = os.path.join(tmp, "案件.zip")
        create_zip(case_zip, {"北京银行共有优先权信息.zip": priority_zip})

        output_dir = os.path.join(tmp, "output")
        result = extract_all([case_zip], output_dir)

        assert "共有优先权信息" in result
        assert result["共有优先权信息"][0][0] == "北京银行"
