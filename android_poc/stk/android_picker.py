"""选择本地文件。

Android：通过 SAF（ACTION_OPEN_DOCUMENT）多选，把 content:// 文件复制到 inbox 目录，
不需要任何存储权限。桌面调试：用 Kivy FileChooser 弹窗，直接返回原路径。

回调约定：on_done(paths: list[Path], errors: list[str])，总是在 Kivy 主线程调用。
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from kivy.clock import Clock
from kivy.utils import platform

DoneFn = Callable[[list[Path], list[str]], None]

_REQUEST_CODE = 4021
_RESULT_OK = -1  # android.app.Activity.RESULT_OK
_DISPLAY_NAME = "_display_name"  # android.provider.OpenableColumns.DISPLAY_NAME


def pick_files(inbox: Path, on_done: DoneFn) -> None:
    if platform == "android":
        _pick_android(Path(inbox), on_done)
    else:
        _pick_desktop(on_done)


def _safe_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return cleaned or "book"


# ---------------------------------------------------------------- Android

def _pick_android(inbox: Path, on_done: DoneFn) -> None:
    from android import activity  # p4a 自带模块
    from jnius import autoclass

    # 类在 Kivy 主线程解析好再交给后台线程使用（后台线程的类加载器找不到 App 类）
    python_activity = autoclass("org.kivy.android.PythonActivity")
    intent_cls = autoclass("android.content.Intent")
    uri_cls = autoclass("android.net.Uri")

    current = python_activity.mActivity
    resolver = current.getContentResolver()

    intent = intent_cls(intent_cls.ACTION_OPEN_DOCUMENT)
    intent.addCategory(intent_cls.CATEGORY_OPENABLE)
    intent.setType("*/*")
    intent.putExtra(intent_cls.EXTRA_ALLOW_MULTIPLE, True)

    def on_result(request_code: int, result_code: int, data) -> None:  # noqa: ANN001
        if request_code != _REQUEST_CODE:
            return
        # 不在回调遍历过程中修改回调列表
        Clock.schedule_once(lambda _dt: activity.unbind(on_activity_result=on_result))
        uris: list[str] = []
        if result_code == _RESULT_OK and data is not None:
            clip = data.getClipData()
            if clip is not None:
                for i in range(clip.getItemCount()):
                    uris.append(clip.getItemAt(i).getUri().toString())
            elif data.getData() is not None:
                uris.append(data.getData().toString())
        if not uris:
            Clock.schedule_once(lambda _dt: on_done([], []))
            return
        threading.Thread(
            target=_copy_all, args=(resolver, uri_cls, uris, inbox, on_done), daemon=True
        ).start()

    activity.bind(on_activity_result=on_result)
    current.startActivityForResult(intent, _REQUEST_CODE)


def _copy_all(resolver, uri_cls, uris: list[str], inbox: Path, on_done: DoneFn) -> None:  # noqa: ANN001
    from jnius import detach

    paths: list[Path] = []
    errors: list[str] = []
    try:
        inbox.mkdir(parents=True, exist_ok=True)
        for uri_str in uris:
            try:
                paths.append(_copy_one(resolver, uri_cls.parse(uri_str), inbox))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"复制失败 {uri_str}: {type(exc).__name__}: {exc}")
    finally:
        Clock.schedule_once(lambda _dt: on_done(paths, errors))
        detach()


def _display_name(resolver, uri) -> str | None:  # noqa: ANN001
    cursor = resolver.query(uri, [_DISPLAY_NAME], None, None, None)
    if cursor is None:
        return None
    try:
        if cursor.moveToFirst():
            index = cursor.getColumnIndex(_DISPLAY_NAME)
            if index >= 0:
                return cursor.getString(index)
    finally:
        cursor.close()
    return None


def _copy_one(resolver, uri, inbox: Path) -> Path:  # noqa: ANN001
    name = _display_name(resolver, uri) or uri.getLastPathSegment() or "book"
    # 每个文件单独一个子目录：同名文件不冲突，文件名（即邮件标题）保持原样
    dest = Path(tempfile.mkdtemp(dir=inbox)) / _safe_name(name)
    pfd = resolver.openFileDescriptor(uri, "r")
    if pfd is None:
        raise OSError("无法打开文件")
    # 接管 fd 后用 Python 原生 IO 复制，比逐块调 Java InputStream 快
    fd = pfd.detachFd()
    pfd.close()
    with os.fdopen(fd, "rb") as src, open(dest, "wb") as out:
        shutil.copyfileobj(src, out, 1024 * 1024)
    return dest


# ---------------------------------------------------------------- 桌面调试

def _pick_desktop(on_done: DoneFn) -> None:
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.filechooser import FileChooserListView
    from kivy.uix.popup import Popup

    chooser = FileChooserListView(path=str(Path.home()), multiselect=True)
    content = BoxLayout(orientation="vertical", spacing=dp(6))
    buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
    popup = Popup(title="选择文件（可多选）", content=content, size_hint=(0.95, 0.95))

    def on_add(*_args) -> None:
        popup.dismiss()
        on_done([Path(p) for p in chooser.selection if Path(p).is_file()], [])

    buttons.add_widget(Button(text="添加", on_release=on_add))
    buttons.add_widget(Button(text="取消", on_release=lambda *_: popup.dismiss()))
    content.add_widget(chooser)
    content.add_widget(buttons)
    popup.open()
