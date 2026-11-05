"""全局常量配置"""
import os

CSV_CATEGORIES = [
    ("共有优先权信息", "共有优先权信息"),
    ("关联子账户信息", "关联子账户信息"),
    ("强制措施信息", "强制措施信息"),
    ("任务信息(成功)", "任务信息(成功)"),
    ("任务信息(失败)", "任务信息(失败)"),
    ("交易明细信息", "交易明细信息"),
    ("人员信息", "人员信息"),
    ("账户信息", "账户信息"),
]

# 银行ZIP文件名中的类型关键词（长优先，用于从文件名剥离银行名）
BANK_ZIP_TYPE_KEYWORDS = [
    "共有优先权信息",   # 7字，北京银行等反馈包中的类型
    "关联子账户信息",   # 7字，需在"账户信息"之前
    "强制措施信息",     # 6字
    "交易明细信息",     # 6字
    "人员信息",         # 4字
    "账户信息",         # 4字，必须最后
]

LONG_NUMBER_KEYWORDS = ["卡号", "账号", "证件号码", "身份证", "手机", "电话"]

# V1.9 交易流水最终去重键（6 列）。
# 交易流水先按全字段去重；在补全和收付标志标准化完成后再使用该键去重。
DEDUP_COLS_DETAIL = ["交易卡号", "交易时间", "交易金额", "交易余额", "收付标志", "交易对手账卡号"]

# V1.9 收付标志标准化：仅替换下列精确值，其他内容保持原样。
PAYMENT_FLAG_MAPPING = {
    "借": "出",
    "1": "出",
    "D": "出",
    "d": "出",
    "转出": "出",
    "贷": "进",
    "2": "进",
    "C": "进",
    "c": "进",
    "入": "进",
    "转入": "进",
}

CLEAN_REQUIRED_TIME_COL = "交易时间"
CLEAN_REQUIRED_AMOUNT_COLS = ["交易金额", "交易余额"]

COMPLETE_TARGET_COLS = ["交易户名", "交易证件号码"]
COMPLETE_MATCH_COLS = ["交易卡号", "交易账号"]

ACCOUNT_INFO_KEY_COLS = ["交易卡号", "交易账号"]
ACCOUNT_INFO_VALUE_COLS = ["交易户名", "交易证件号码"]


def get_output_category(filename: str) -> str | None:
    basename = os.path.basename(filename)
    for keyword, category in CSV_CATEGORIES:
        if keyword in basename:
            return category
    return None


def get_default_output_dir() -> str:
    if os.name == 'nt':
        return os.path.join(os.environ.get('USERPROFILE', 'C:\\'), 'Desktop')
    else:
        return os.path.join(os.environ.get('HOME', '/'), 'Desktop')


def is_long_number_column(col_name: str) -> bool:
    for kw in LONG_NUMBER_KEYWORDS:
        if kw in col_name:
            return True
    return False


def find_column(df_columns, keyword: str) -> str | None:
    for col in df_columns:
        if keyword in str(col):
            return col
    return None


def find_columns(df_columns, keywords: list[str]) -> list[str]:
    result = []
    for kw in keywords:
        found = find_column(df_columns, kw)
        if found:
            result.append(found)
    return result


def parse_bank_zip_name(zip_name: str) -> tuple[str, str] | None:
    """从银行ZIP文件名解析 (银行名, CSV类型)。
    如 "莱商银行股份有限公司交易明细信息.zip" → ("莱商银行股份有限公司", "交易明细信息")
    支持数字后缀：如 "中国农业银行交易明细信息3.zip" → ("中国农业银行", "交易明细信息")
    """
    basename = os.path.splitext(os.path.basename(zip_name))[0]
    for keyword in BANK_ZIP_TYPE_KEYWORDS:
        # 用 find 而非 endswith，兼容关键词后跟数字后缀的情况
        pos = basename.find(keyword)
        if pos >= 0:
            bank_name = basename[:pos]
            return (bank_name, keyword)
    return None


def _extract_card_from_tail(tail: str) -> str:
    """从类型关键词之后的尾部解析卡号（V1.7 新版逐卡格式）。

    新版文件名形如 "{银行名}{类型}({卡号}).zip"，类型关键词之后是 "(6228411333029998167)" 等。
    卡号可能带批量后缀 _001/_000000，统一剥离；为 "-"、"--" 或空视为无卡号。
    """
    tail = (tail or "").strip()
    if not (tail.startswith("(") and tail.endswith(")")):
        return ""
    inner = tail[1:-1].strip()
    if not inner:
        return ""
    # 剥离批量后缀 _NNN（如 _001 / _000000）
    underscore_pos = inner.find("_")
    if underscore_pos > 0:
        inner = inner[:underscore_pos]
    inner = inner.strip()
    if inner in ("", "-", "--"):
        return ""
    return inner


def parse_bank_zip_name_v2(zip_name: str) -> tuple[str, str, str] | None:
    """V1.7 新版格式解析：从银行 ZIP/CSV 文件名解析 (银行名, CSV类型, 卡号)。

    新版：{银行名}{类型}({卡号}).zip，如 "中国农业银行交易明细信息(6228411333029998167).zip"
    → ("中国农业银行", "交易明细信息", "6228411333029998167")。
    旧版：{银行名}{类型}.zip，此时卡号返回 ""。
    保留原有 parse_bank_zip_name 的 keyword 匹配逻辑（find 而非 endswith），仅额外返回卡号。
    """
    basename = os.path.splitext(os.path.basename(zip_name))[0]
    for keyword in BANK_ZIP_TYPE_KEYWORDS:
        pos = basename.find(keyword)
        if pos >= 0:
            bank_name = basename[:pos]
            card = _extract_card_from_tail(basename[pos + len(keyword):])
            return (bank_name, keyword, card)
    return None
