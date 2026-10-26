from __future__ import annotations

import shutil
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

LogFn = Callable[[str], None]


def _convert_step(name: str, src: Path, workdir: Path, log: LogFn) -> bool:
    from ebook_converter_lib import convert

    dest = workdir / (src.stem + "_" + name + ".epub")
    log(f"[RUN ] {name}: {src.name} -> {dest.name}")
    try:
        result = convert(str(src), str(dest))
    except Exception:
        log(f"[FAIL] {name}: exception\n{traceback.format_exc()}")
        return False
    if result.get("success") and dest.is_file() and dest.stat().st_size > 0:
        log(f"[PASS] {name}: {dest.stat().st_size} bytes")
        return True
    log(f"[FAIL] {name}: {result.get('message', 'unknown error')[:500]}")
    return False


def run_poc(log: LogFn = print) -> bool:
    log("=== SendToKindle Android PoC ===")
    ok = True

    log("[RUN ] step0: dependency check")
    try:
        from ebook_converter_lib import check_deps_str

        status = check_deps_str()
        if status == "Dependencies available.":
            log("[PASS] step0: dependencies available")
        else:
            log(f"[FAIL] step0: {status}")
            ok = False
    except Exception:
        log(f"[FAIL] step0: exception\n{traceback.format_exc()}")
        ok = False

    if not (ASSETS_DIR / "sample.txt").is_file():
        log(f"[FAIL] assets missing: {ASSETS_DIR}")
        return False

    workdir = Path(tempfile.mkdtemp(prefix="stkpoc_"))
    try:
        if not _convert_step("txt2epub", ASSETS_DIR / "sample.txt", workdir, log):
            ok = False
        if not _convert_step("mobi2epub", ASSETS_DIR / "sample.mobi", workdir, log):
            ok = False
        if not _convert_step("azw32epub", ASSETS_DIR / "sample.azw3", workdir, log):
            ok = False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    log(f"=== RESULT: {'PASS' if ok else 'FAIL'} ===")
    return ok
