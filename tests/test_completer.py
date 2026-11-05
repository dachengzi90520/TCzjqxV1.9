import sys
sys.path.insert(0, '.')
import os
import tempfile
import pandas as pd
from core.completer import (
    complete_transaction_detail,
    fill_missing_account_keys,
)


def test_complete_by_card():
    detail = pd.DataFrame({
        "交易卡号": ["C001", "C002", "C003"],
        "交易账号": ["A001", "A002", "A003"],
        "交易户名": ["", "", "已有名"],
        "交易证件号码": ["", "", "已有证号"],
    })
    account = pd.DataFrame({
        "交易卡号": ["C001", "C002"],
        "交易账号": ["A001", "A002"],
        "交易户名": ["张三", "李四"],
        "交易证件号码": ["ID001", "ID002"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"
    assert result.iloc[1]["交易户名"] == "李四"
    assert result.iloc[2]["交易户名"] == "已有名"


def test_complete_by_account_fallback():
    detail = pd.DataFrame({
        "交易卡号": ["C999"],
        "交易账号": ["A001"],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["C001"],
        "交易账号": ["A001"],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"


def test_complete_no_match():
    detail = pd.DataFrame({
        "交易卡号": ["C999"],
        "交易账号": ["A999"],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["C001"],
        "交易账号": ["A001"],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == ""


def test_clean_key_strips_underscore_suffix():
    """_clean_key 去除 _后所有内容"""
    from core.completer import _clean_key
    assert _clean_key("6217002210035674693_156_1") == "6217002210035674693"
    assert _clean_key("6217002210035674693") == "6217002210035674693"
    assert _clean_key("") == ""
    assert _clean_key("C001_A_1") == "C001"


def test_clean_key_strips_dash_prefix():
    """V1.3: _clean_key 去除 - 及其之前的所有字符"""
    from core.completer import _clean_key
    assert _clean_key("123456-7890123456789") == "7890123456789"
    assert _clean_key("001-6222021234567890") == "6222021234567890"
    # 无 - 时不受影响
    assert _clean_key("6217002210035674693") == "6217002210035674693"


def test_clean_key_strips_dash_and_underscore_combined():
    """V1.3: _clean_key 同时处理 - 前缀和 _ 后缀"""
    from core.completer import _clean_key
    assert _clean_key("123456-7890123456789_156_1") == "7890123456789"
    assert _clean_key("001-6222021234567890_1_2") == "6222021234567890"


def test_complete_with_dash_prefix_in_account():
    """V1.3: 账户表中卡号带 - 前缀时仍能匹配"""
    detail = pd.DataFrame({
        "交易卡号": ["7890123456789"],
        "交易账号": [""],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["123456-7890123456789"],
        "交易账号": [""],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"
    assert result.iloc[0]["交易证件号码"] == "ID001"


def test_complete_with_dash_prefix_in_detail():
    """V1.3: 交易明细中卡号带 - 前缀时仍能匹配"""
    detail = pd.DataFrame({
        "交易卡号": ["001-6222021234567890"],
        "交易账号": [""],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["6222021234567890"],
        "交易账号": [""],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"


def test_complete_with_dash_suffix_in_detail():
    """V1.4: 交易明细中卡号/账号带 -后缀时仍能匹配（"-" 作调证序号分隔符）"""
    detail = pd.DataFrame({
        "交易卡号": ["6222021234567890-001"],
        "交易账号": ["6222021234567890-001"],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": [""],
        "交易账号": ["6222021234567890"],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"
    assert result.iloc[0]["交易证件号码"] == "ID001"


def test_complete_with_underscore_suffix_in_account():
    """账户表中卡号带 _后缀 时仍能匹配"""
    detail = pd.DataFrame({
        "交易卡号": ["6217002210035674693"],
        "交易账号": [""],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["6217002210035674693_156_1"],
        "交易账号": [""],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"
    assert result.iloc[0]["交易证件号码"] == "ID001"


def test_complete_with_underscore_suffix_in_detail():
    """交易明细中卡号带 _后缀 时仍能匹配"""
    detail = pd.DataFrame({
        "交易卡号": ["6217002210035674693_156_1"],
        "交易账号": [""],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["6217002210035674693"],
        "交易账号": [""],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"


def test_complete_card_blank_use_account():
    """V1.2: 交易卡号为空时，用交易账号匹配补全"""
    detail = pd.DataFrame({
        "交易卡号": [""],
        "交易账号": ["A001"],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["C001"],
        "交易账号": ["A001"],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"
    assert result.iloc[0]["交易证件号码"] == "ID001"


def test_complete_account_blank_use_card():
    """V1.2: 交易账号为空时，用交易卡号匹配补全"""
    detail = pd.DataFrame({
        "交易卡号": ["C001"],
        "交易账号": [""],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["C001"],
        "交易账号": ["A001"],
        "交易户名": ["张三"],
        "交易证件号码": ["ID001"],
    })

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"
    assert result.iloc[0]["交易证件号码"] == "ID001"


def test_complete_card_match_poor_fallback_to_account():
    """V1.2: 卡号匹配到空名空证号时，回退用账号补充"""
    detail = pd.DataFrame({
        "交易卡号": ["C001"],
        "交易账号": ["A002"],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["C001", "C002"],
        "交易账号": ["A001", "A002"],
        "交易户名": ["", "张三"],
        "交易证件号码": ["", "ID002"],
    })

    result = complete_transaction_detail(detail, account)
    # 卡号 C001 匹配到空名空证号，应回退用账号 A002 匹配到张三
    assert result.iloc[0]["交易户名"] == "张三"
    assert result.iloc[0]["交易证件号码"] == "ID002"


def test_complete_all_csv():
    """complete_all 从 CSV 读取并写回 CSV"""
    import os
    import tempfile
    from core.completer import complete_all

    with tempfile.TemporaryDirectory() as tmp:
        # 创建交易明细 CSV
        detail_path = os.path.join(tmp, "交易明细信息_合并.csv")
        detail = pd.DataFrame({
            "交易卡号": ["C001", "C002", "C003"],
            "交易账号": ["A001", "A002", "A003"],
            "交易户名": ["", "", "已有名"],
            "交易证件号码": ["", "", "已有证号"],
        })
        detail.to_csv(detail_path, index=False, encoding="utf-8-sig")

        # 创建账户信息 CSV
        account_path = os.path.join(tmp, "账户信息_合并.csv")
        account = pd.DataFrame({
            "交易卡号": ["C001", "C002"],
            "交易账号": ["A001", "A002"],
            "交易户名": ["张三", "李四"],
            "交易证件号码": ["ID001", "ID002"],
        })
        account.to_csv(account_path, index=False, encoding="utf-8-sig")

        # 执行补全
        filled = complete_all([detail_path, account_path])
        assert filled == 2

        # 验证结果
        result = pd.read_csv(detail_path, dtype=str, keep_default_na=False)
        assert result.iloc[0]["交易户名"] == "张三"
        assert result.iloc[1]["交易户名"] == "李四"
        assert result.iloc[2]["交易户名"] == "已有名"


def test_v19_fill_account_keys_before_identity():
    detail = pd.DataFrame({
        "交易卡号": ["", "C002", "C999"],
        "交易账号": ["A001", "", "A999"],
        "交易户名": ["", "", ""],
        "交易证件号码": ["", "", ""],
    })
    account = pd.DataFrame({
        "交易卡号": ["C001", "C002"],
        "交易账号": ["A001", "A002"],
        "交易户名": ["张三", "李四"],
        "交易证件号码": ["ID001", "ID002"],
    })

    keyed = fill_missing_account_keys(detail.copy(), account)
    assert keyed.iloc[0]["交易卡号"] == "C001"
    assert keyed.iloc[1]["交易账号"] == "A002"
    assert keyed.iloc[2]["交易卡号"] == "C999"
    assert keyed.iloc[2]["交易账号"] == "A999"

    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易户名"] == "张三"
    assert result.iloc[1]["交易户名"] == "李四"
    assert result.iloc[2]["交易户名"] == ""


def test_v19_vlookup_uses_first_account_match():
    detail = pd.DataFrame({
        "交易卡号": [""],
        "交易账号": ["A001"],
        "交易户名": [""],
        "交易证件号码": [""],
    })
    account = pd.DataFrame({
        "交易卡号": ["C001", "C002"],
        "交易账号": ["A001", "A001"],
        "交易户名": ["张三", "李四"],
        "交易证件号码": ["ID001", "ID002"],
    })
    result = complete_transaction_detail(detail, account)
    assert result.iloc[0]["交易卡号"] == "C001"
    assert result.iloc[0]["交易户名"] == "张三"
