"""编码自动检测，使用 chardet + GBK 兜底"""
import chardet


def detect_encoding(file_path: str, sample_size: int = 100_000) -> str:
    """
    检测文件编码。chardet 对中文短文本置信度可能很低，
    因此任何 GB18030/GB2312 检测结果都直接信任，UTF/ASCII 需高置信度。
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read(sample_size)

        if len(raw) == 0:
            return "gbk"

        result = chardet.detect(raw)
        encoding = result.get("encoding")
        confidence = result.get("confidence", 0)

        if encoding:
            enc_lower = encoding.lower()
            # 中文编码：低置信度也可信
            if enc_lower in ("gb2312", "gb18030", "gbk"):
                return "gbk"
            # ASCII → UTF-8
            if "ascii" in enc_lower:
                return "utf-8"
            # 其他编码需要高置信度
            if confidence > 0.5:
                return encoding

        return "gbk"
    except Exception:
        return "gbk"
