"""转换为 EPUB，移植自桌面版 app/converter.py。

与桌面版的差异：
- 没有 poppler，PDF 和 EPUB 一样原样发送（Kindle 邮件原生支持 PDF）。
- 不支持 odt（依赖的 odfpy 没有打包）。
"""
from __future__ import annotations

import re
from pathlib import Path

SEND_AS_IS = {".epub", ".pdf"}

CONVERT_EXTS = {
    ".txt",
    ".mobi",
    ".azw",
    ".azw3",
    ".prc",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".docx",
    ".fb2",
    ".rtf",
}

SUPPORTED_EXTS = SEND_AS_IS | CONVERT_EXTS


class ConversionError(Exception):
    pass


def is_supported(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTS


def book_title(path: str | Path) -> str:
    return Path(path).stem


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name).strip(" .")
    return cleaned or "book"


def prepare_for_send(src: str | Path, workdir: Path) -> Path:
    """返回要作为附件发送的文件：epub/pdf 原样返回，其他格式转成 epub。"""
    src = Path(src)
    ext = src.suffix.lower()
    if ext in SEND_AS_IS:
        return src
    if ext not in CONVERT_EXTS:
        raise ConversionError(f"不支持的格式: {ext or '无扩展名'}")

    from ebook_converter_lib import convert

    base = _safe_filename(book_title(src))
    dest = workdir / f"{base}.epub"
    counter = 1
    while dest.exists():
        dest = workdir / f"{base}_{counter}.epub"
        counter += 1
    result = convert(str(src), str(dest))
    if not result.get("success") or not dest.is_file():
        message = result.get("message") or "未知错误"
        # 只保留异常摘要，traceback 太长不适合放进汇总
        raise ConversionError(message.splitlines()[0] if message else "未知错误")
    return dest
