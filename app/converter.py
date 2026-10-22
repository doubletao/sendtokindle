from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Iterator
from pathlib import Path

from ebook_converter_lib import convert

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POPPLER_DIR = PROJECT_ROOT / "poppler_bin"

SUPPORTED_EXTS = {
    ".azw",
    ".azw3",
    ".mobi",
    ".prc",
    ".epub",
    ".docx",
    ".html",
    ".htm",
    ".txt",
    ".md",
    ".markdown",
    ".pdf",
    ".odt",
    ".fb2",
    ".rtf",
}


class ConversionError(Exception):
    pass


@contextlib.contextmanager
def poppler_path_scope() -> Iterator[None]:
    if not POPPLER_DIR.is_dir():
        yield
        return
    poppler = str(POPPLER_DIR)
    old_path = os.environ.get("PATH", "")
    if poppler in old_path.split(os.pathsep):
        yield
        return
    os.environ["PATH"] = poppler + os.pathsep + old_path
    try:
        yield
    finally:
        os.environ["PATH"] = old_path


def is_supported(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTS


def book_title(path: str | Path) -> str:
    return Path(path).stem


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name).strip(" .")
    return cleaned or "book"


def convert_to_epub(src: str | Path, workdir: Path) -> Path:
    src = Path(src).resolve()
    if src.suffix.lower() == ".epub":
        return src
    dest = workdir / f"{_safe_filename(book_title(src))}.epub"
    counter = 1
    while dest.exists():
        dest = workdir / f"{_safe_filename(book_title(src))}_{counter}.epub"
        counter += 1
    with poppler_path_scope():
        result = convert(str(src), str(dest))
    if not result.get("success") or not dest.exists():
        message = result.get("message") or "未知错误"
        raise ConversionError(message)
    return dest
