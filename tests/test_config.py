import sys
sys.path.insert(0, '.')
from utils.config import (
    CSV_CATEGORIES, LONG_NUMBER_KEYWORDS,
    DEDUP_COLS_DETAIL,
    get_output_category, get_default_output_dir,
    parse_bank_zip_name, parse_bank_zip_name_v2, BANK_ZIP_TYPE_KEYWORDS
)

def test_csv_categories_count():
    assert len(CSV_CATEGORIES) == 8

def test_long_number_keywords_not_empty():
    assert len(LONG_NUMBER_KEYWORDS) > 0

def test_dedup_cols_detail_count():
    # V1.8：去重键由 5 列扩为 6 列（新增"交易余额"）
    assert len(DEDUP_COLS_DETAIL) == 6

def test_dedup_cols_uses_shoufu():
    assert "收付标志" in DEDUP_COLS_DETAIL

def test_dedup_cols_contains_balance():
    # V1.8：必须包含"交易余额"——余额不同即不同笔交易，不能合并
    assert "交易余额" in DEDUP_COLS_DETAIL

def test_dedup_cols_v18_order():
    assert DEDUP_COLS_DETAIL == [
        "交易卡号", "交易时间", "交易金额", "交易余额", "收付标志", "交易对手账卡号"
    ]

def test_get_output_category_detail():
    assert get_output_category("交易明细信息_工商银行_001") == "交易明细信息"

def test_get_output_category_account():
    assert get_output_category("关联子账户信息_建设银行") == "关联子账户信息"

def test_get_output_category_force_measure():
    assert get_output_category("强制措施信息_中国银行") == "强制措施信息"

def test_get_output_category_shared_priority():
    assert get_output_category("共有优先权信息_北京银行") == "共有优先权信息"

def test_get_output_category_unknown():
    assert get_output_category("某个未知文件") is None

def test_get_output_category_success_task():
    assert get_output_category("任务信息(成功)") == "任务信息(成功)"

def test_get_output_category_fail_task():
    assert get_output_category("任务信息(失败)") == "任务信息(失败)"

def test_get_default_output_dir():
    import os
    result = get_default_output_dir()
    assert os.path.isabs(result)

def test_parse_bank_zip_name_basic():
    result = parse_bank_zip_name("莱商银行股份有限公司交易明细信息.zip")
    assert result == ("莱商银行股份有限公司", "交易明细信息")

def test_parse_bank_zip_name_sub_account():
    result = parse_bank_zip_name("莱商银行股份有限公司关联子账户信息.zip")
    assert result == ("莱商银行股份有限公司", "关联子账户信息")

def test_parse_bank_zip_name_force():
    result = parse_bank_zip_name("中国建设银行强制措施信息.zip")
    assert result == ("中国建设银行", "强制措施信息")

def test_parse_bank_zip_name_shared_priority():
    result = parse_bank_zip_name("北京银行共有优先权信息.zip")
    assert result == ("北京银行", "共有优先权信息")

def test_parse_bank_zip_name_personnel():
    result = parse_bank_zip_name("招商银行股份有限公司人员信息.zip")
    assert result == ("招商银行股份有限公司", "人员信息")

def test_parse_bank_zip_name_account():
    result = parse_bank_zip_name("威海银行股份有限公司账户信息.zip")
    assert result == ("威海银行股份有限公司", "账户信息")


def test_parse_bank_zip_name_numbered_suffix():
    """支持数字后缀：如 '中国农业银行交易明细信息3.zip'"""
    result = parse_bank_zip_name("中国农业银行交易明细信息3.zip")
    assert result == ("中国农业银行", "交易明细信息")


def test_parse_bank_zip_name_numbered_suffix_large():
    """支持大多位数字后缀"""
    result = parse_bank_zip_name("中国农业银行交易明细信息11.zip")
    assert result == ("中国农业银行", "交易明细信息")


def test_parse_bank_zip_name_numbered_suffix_multiple_types():
    """多种类型带数字后缀"""
    assert parse_bank_zip_name("中国工商银行交易明细信息2.zip") == ("中国工商银行", "交易明细信息")
    assert parse_bank_zip_name("中国建设银行交易明细信息2.zip") == ("中国建设银行", "交易明细信息")
    assert parse_bank_zip_name("中国邮政储蓄银行有限责任公司交易明细信息2.zip") == ("中国邮政储蓄银行有限责任公司", "交易明细信息")
    assert parse_bank_zip_name("山东省农村信用社联合社交易明细信息2.zip") == ("山东省农村信用社联合社", "交易明细信息")


# ==================== V1.7 新版逐卡格式 ====================

def test_parse_bank_zip_name_v2_basic_card():
    """新版：{银行}{类型}({卡号}).zip"""
    result = parse_bank_zip_name_v2("中国农业银行交易明细信息(6228411333029998167).zip")
    assert result == ("中国农业银行", "交易明细信息", "6228411333029998167")


def test_parse_bank_zip_name_v2_batch_suffix():
    """卡号带批量后缀 _001/_000000 → 剥离"""
    assert parse_bank_zip_name_v2((
        "内蒙古农村商业银行股份有限公司交易明细信息(6229760090301199840_000000).zip"
    )) == ("内蒙古农村商业银行股份有限公司", "交易明细信息", "6229760090301199840")
    assert parse_bank_zip_name_v2((
        "北京银行交易明细信息(6214685094193551_001).zip"
    )) == ("北京银行", "交易明细信息", "6214685094193551")


def test_parse_bank_zip_name_v2_dash_card():
    """卡号为 '-' / '--' → 视为无卡号"""
    assert parse_bank_zip_name_v2("中国光大银行股份有限公司交易明细信息(-).zip")[2] == ""


def test_parse_bank_zip_name_v2_old_format_no_card():
    """旧版文件名无括号卡号 → 卡号为 ''"""
    result = parse_bank_zip_name_v2("莱商银行股份有限公司交易明细信息.zip")
    assert result == ("莱商银行股份有限公司", "交易明细信息", "")


def test_parse_bank_zip_name_v2_non_detail_card():
    """非明细类型（如账户信息）不带卡号"""
    result = parse_bank_zip_name_v2("北京银行账户信息.zip")
    assert result == ("北京银行", "账户信息", "")


def test_parse_bank_zip_name_v2_unknown():
    assert parse_bank_zip_name_v2("无法识别.zip") is None


def test_parse_bank_zip_name_v2_keeps_bank_with_suffix():
    """银行名中带尾巴仍能正确拆出（如 '交明细信息' 类特例不含 '交易明细信息' 关键词应返回 None）"""
    # 不含任何关键词 → None
    assert parse_bank_zip_name_v2("中国农业银行交明细信息(6666669617998699).zip") is None
