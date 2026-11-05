"""CSV 分隔符检测 + 自动编码读取"""
import csv
import re
import pandas as pd
from utils.encoding import detect_encoding

# Excel/XML 1.0 不允许写入工作表的控制字符
# （openpyxl 遇到会抛 IllegalCharacterError，如数据中夹杂的 \x1c 文件分隔符）
ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_excel_string(value) -> str:
    """移除字符串中 Excel 不允许的控制字符，防止写入 XLSX 时报错。"""
    if value is None:
        return ""
    return ILLEGAL_XML_CHARS_RE.sub("", str(value))


def detect_delimiter(file_path: str) -> str:
    """
    检测 CSV 分隔符。针对银行系统 CSV 格式做了特殊处理：
    特征是字段用双引号包裹、逗号分隔，字段值尾部含 \t。
    csv.Sniffer 容易被尾部 \t 误导，故加入二次验证。
    """
    encoding = detect_encoding(file_path)

    # 读取文件内容用于检测
    raw_text = ""
    for enc in [encoding, "gbk", "utf-8"]:
        try:
            with open(file_path, "r", encoding=enc, errors="replace") as f:
                raw_text = f.read(100_000)
            break
        except Exception:
            continue

    if not raw_text.strip():
        return ","

    # 先用 csv.Sniffer
    sniffer_delim = None
    try:
        dialect = csv.Sniffer().sniff(raw_text, delimiters=",\t|")
        sniffer_delim = dialect.delimiter
    except Exception:
        pass

    # 如果 Sniffer 说 tab，做二次验证：看逗号是否更合理
    if sniffer_delim == "\t":
        lines = [l for l in raw_text.split("\n") if l.strip()][:10]
        # 统计 "," 模式出现次数（逗号在引号间 = 字段分隔）
        comma_field_count = 0
        tab_field_count = 0
        for line in lines:
            # 逗号分隔：数引号外的逗号..."，引号间才是字段分隔
            in_quote = False
            comma_sep = 1
            for i, ch in enumerate(line):
                if ch == '"':
                    in_quote = not in_quote
                elif ch == ',' and not in_quote:
                    comma_sep += 1
            comma_field_count = max(comma_field_count, comma_sep)

            # 制表符分隔
            tab_sep = 1
            in_quote = False
            for ch in line:
                if ch == '"':
                    in_quote = not in_quote
                elif ch == '\t' and not in_quote:
                    tab_sep += 1
            tab_field_count = max(tab_field_count, tab_sep)

        # 如果逗号能分出 >= 2 列，且列数 ≥ 制表符分出的列数，则用逗号
        if comma_field_count >= 2 and comma_field_count >= tab_field_count:
            return ","

        return "\t"

    return sniffer_delim if sniffer_delim else ","


def read_csv_auto(file_path: str, **kwargs) -> pd.DataFrame:
    """
    自动检测编码和分隔符读取 CSV。
    先用 C 引擎，失败回退到 Python 引擎 + GBK 兜底。
    所有字符串列去除前后空格（含尾部 \t）。
    """
    encoding = detect_encoding(file_path)
    delimiter = detect_delimiter(file_path)

    # 尝试多种编码组合（GBK 系列优先，银行系统 CSV 绝大多数为 GBK/GB18030）
    encodings_to_try = []
    # 1. 检测到的编码（如果是 GBK 系列则排最前）
    if encoding.lower() in ("gbk", "gb2312", "gb18030"):
        encodings_to_try.extend(["gbk", "gb18030"])
    else:
        encodings_to_try.append(encoding)
    # 2. GBK 系列兜底
    for enc in ["gbk", "gb18030"]:
        if enc not in encodings_to_try:
            encodings_to_try.append(enc)
    # 3. UTF 系列兜底
    for enc in ["utf-8", "utf-8-sig", "utf-16"]:
        if enc not in encodings_to_try:
            encodings_to_try.append(enc)

    last_error = None
    for enc in encodings_to_try:
        for engine in ["c", "python"]:
            try:
                df = pd.read_csv(
                    file_path,
                    encoding=enc,
                    sep=delimiter,
                    dtype=str,
                    keep_default_na=False,
                    engine=engine,
                    **kwargs
                )
                # 成功 → 清理数据
                df.columns = [
                    sanitize_excel_string(col)
                    .replace("\n", "")
                    .replace("\r", "")
                    .strip()
                    for col in df.columns
                ]

                for col in df.columns:
                    s = df[col].astype(str)
                    # 移除 Excel 非法控制字符（如 \x1c），再去除前后空白
                    df[col] = s.str.replace(ILLEGAL_XML_CHARS_RE, "", regex=True).str.strip()
                    df[col] = df[col].replace("nan", "")

                return df
            except Exception as e:
                last_error = e
                continue

    raise RuntimeError(f"无法读取CSV文件 {file_path}, 最后错误: {last_error}")


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """标准化列名：去除空格和换行符"""
    df.columns = [str(col).strip().replace("\n", "").replace("\r", "") for col in df.columns]
    return df
