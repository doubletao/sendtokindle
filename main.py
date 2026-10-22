from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.paths import app_dir


def _emit(lines: list[str], log_path: Path) -> None:
    text = "\n".join(lines)
    log_path.write_text(text + "\n", encoding="utf-8")
    stream = getattr(sys, "stdout", None)
    if stream is not None:
        try:
            print(text)
        except OSError:
            pass


def run_check() -> int:
    lines: list[str] = ["SendToKindle self-check"]
    ok = True

    try:
        from ebook_converter_lib import check_deps_str

        result = check_deps_str()
        lines.append(f"[{'OK' if result == 'Dependencies available.' else 'FAIL'}] deps: {result}")
        ok = ok and result == "Dependencies available."
    except Exception as exc:
        lines.append(f"[FAIL] deps: {exc}")
        ok = False

    poppler = app_dir() / "poppler_bin"
    pdfinfo = poppler / "pdfinfo.exe"
    if pdfinfo.is_file():
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(poppler) + os.pathsep + old_path
        try:
            proc = subprocess.run(
                [str(pdfinfo), "-v"], capture_output=True, text=True, timeout=15
            )
            version = (proc.stderr or proc.stdout or "").splitlines()
            lines.append(f"[OK] poppler: {version[0] if version else 'pdfinfo runnable'}")
        except Exception as exc:
            lines.append(f"[FAIL] poppler: {exc}")
            ok = False
        finally:
            os.environ["PATH"] = old_path
    else:
        lines.append(f"[FAIL] poppler: {pdfinfo} not found")
        ok = False

    try:
        from app.converter import convert_to_epub

        with tempfile.TemporaryDirectory(prefix="stk_check_") as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "check.txt"
            src.write_text("self check content", encoding="utf-8")
            epub = convert_to_epub(src, tmp_path)
            if epub.is_file() and epub.stat().st_size > 0:
                lines.append(f"[OK] convert: txt -> epub ({epub.stat().st_size} bytes)")
            else:
                lines.append("[FAIL] convert: output missing or empty")
                ok = False
    except Exception as exc:
        lines.append(f"[FAIL] convert: {exc}")
        ok = False

    lines.append(f"RESULT: {'PASS' if ok else 'FAIL'}")
    _emit(lines, app_dir() / "sendtokindle_check.log")
    return 0 if ok else 1


def main() -> None:
    if "--check" in sys.argv[1:]:
        sys.exit(run_check())
    from app.ui import App

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
