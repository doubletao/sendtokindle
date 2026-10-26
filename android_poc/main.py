"""SendToKindle Android 版：选择本地电子书，转换为 EPUB 后用 SMTP 发到 Kindle 邮箱。"""
from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import DEFAULT_FONT, LabelBase
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import NoTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from stk import config as cfg_mod
from stk.android_picker import pick_files
from stk.convert import ConversionError, book_title, is_supported, prepare_for_send
from stk.sender import send_book

ROW_H = dp(48)
INBOX = Path(tempfile.gettempdir()) / "stk_inbox"

# Kivy 默认的 Roboto 没有中文字形，用系统自带的 CJK 字体覆盖默认字体
_CJK_FONTS = (
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/NotoSansSC-Regular.otf",
    "/system/fonts/DroidSansFallback.ttf",
    "C:/Windows/Fonts/msyh.ttc",  # 桌面调试
    "C:/Windows/Fonts/simhei.ttf",
)


def _register_cjk_font() -> None:
    for font in _CJK_FONTS:
        if Path(font).is_file():
            LabelBase.register(DEFAULT_FONT, font)
            return


def _set_keep_screen_on(on: bool) -> None:
    """发送期间保持亮屏，避免锁屏后进程被挂起导致发送中断。"""
    if platform != "android":
        return
    from android.runnable import run_on_ui_thread  # p4a 自带模块
    from jnius import autoclass

    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    flag = autoclass("android.view.WindowManager$LayoutParams").FLAG_KEEP_SCREEN_ON

    @run_on_ui_thread
    def _apply() -> None:
        window = activity.getWindow()
        if on:
            window.addFlags(flag)
        else:
            window.clearFlags(flag)

    _apply()


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def _alert(title: str, text: str) -> None:
    body = Label(text=text, halign="left", valign="top", size_hint_y=None)
    body.bind(
        width=lambda w, v: setattr(w, "text_size", (v, None)),
        texture_size=lambda w, v: setattr(w, "height", v[1]),
    )
    scroll = ScrollView()
    scroll.add_widget(body)
    content = BoxLayout(orientation="vertical", spacing=dp(6))
    popup = Popup(title=title, content=content, size_hint=(0.9, 0.7))
    content.add_widget(scroll)
    content.add_widget(Button(text="确定", size_hint_y=None, height=ROW_H, on_release=popup.dismiss))
    popup.open()


class MainScreen(Screen):
    def __init__(self, app: "SendToKindleApp", **kwargs) -> None:
        super().__init__(name="main", **kwargs)
        self.app = app
        self.files: list[Path] = []
        self.busy = False

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        header = BoxLayout(size_hint_y=None, height=ROW_H, spacing=dp(6))
        header.add_widget(Label(text="SendToKindle", bold=True, font_size="18sp"))
        self.settings_btn = Button(text="设置", size_hint_x=None, width=dp(90), on_release=self._open_settings)
        header.add_widget(self.settings_btn)
        root.add_widget(header)

        self.file_grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(2))
        self.file_grid.bind(minimum_height=self.file_grid.setter("height"))
        file_scroll = ScrollView(size_hint_y=0.45)
        file_scroll.add_widget(self.file_grid)
        root.add_widget(file_scroll)

        actions = BoxLayout(size_hint_y=None, height=ROW_H, spacing=dp(6))
        self.add_btn = Button(text="添加文件", on_release=self._add_files)
        self.clear_btn = Button(text="清空", on_release=self._clear_files)
        self.send_btn = Button(text="转换并发送", on_release=self._start_send)
        for btn in (self.add_btn, self.clear_btn, self.send_btn):
            actions.add_widget(btn)
        root.add_widget(actions)

        self.status = Label(text="请添加文件", size_hint_y=None, height=dp(32))
        root.add_widget(self.status)

        self.log_view = TextInput(text="", readonly=True, font_size="12sp", size_hint_y=0.35)
        root.add_widget(self.log_view)

        self.add_widget(root)
        self._refresh_list()

    # ------------------------------------------------------------ 日志 / 状态

    def log(self, line: str) -> None:
        """线程安全：可在后台线程调用。"""

        def _do(_dt: object) -> None:
            self.log_view.text += line + "\n"
            self.log_view.cursor = (0, len(self.log_view.text))

        Clock.schedule_once(_do)

    def set_status(self, text: str) -> None:
        Clock.schedule_once(lambda _dt: setattr(self.status, "text", text))

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for btn in (self.add_btn, self.clear_btn, self.send_btn, self.settings_btn):
            btn.disabled = busy
        self._refresh_list()

    # ------------------------------------------------------------ 文件列表

    def _refresh_list(self) -> None:
        self.file_grid.clear_widgets()
        if not self.files:
            self.file_grid.add_widget(Label(text="（还没有文件）", size_hint_y=None, height=ROW_H, color=(0.6, 0.6, 0.6, 1)))
            return
        for path in self.files:
            row = BoxLayout(size_hint_y=None, height=ROW_H, spacing=dp(4))
            supported = is_supported(path)
            try:
                size = _human_size(path.stat().st_size)
            except OSError:
                size = "?"
            text = f"{path.name}  ({size})" if supported else f"{path.name}  [不支持的格式]"
            name = Label(
                text=text,
                halign="left",
                valign="middle",
                shorten=True,
                shorten_from="center",
                color=(1, 1, 1, 1) if supported else (0.5, 0.5, 0.5, 1),
            )
            name.bind(size=lambda w, v: setattr(w, "text_size", v))
            row.add_widget(name)
            remove = Button(text="×", size_hint_x=None, width=ROW_H, disabled=self.busy)
            remove.bind(on_release=lambda _btn, p=path: self._remove_file(p))
            row.add_widget(remove)
            self.file_grid.add_widget(row)

    def _remove_file(self, path: Path) -> None:
        if path in self.files:
            self.files.remove(path)
        self._refresh_list()
        self.status.text = f"共 {len(self.files)} 个文件"

    def _clear_files(self, *_args) -> None:
        self.files.clear()
        shutil.rmtree(INBOX, ignore_errors=True)
        self._refresh_list()
        self.status.text = "请添加文件"

    def _add_files(self, *_args) -> None:
        self.status.text = "正在选择文件..."
        self.add_btn.disabled = True

        def on_done(paths: list[Path], errors: list[str]) -> None:
            self.add_btn.disabled = False
            for err in errors:
                self.log(err)
            for path in paths:
                if path not in self.files:
                    self.files.append(path)
            self._refresh_list()
            self.status.text = f"共 {len(self.files)} 个文件"

        try:
            pick_files(INBOX, on_done)
        except Exception as exc:  # noqa: BLE001
            self.add_btn.disabled = False
            self.status.text = "打开文件选择失败"
            self.log(f"打开文件选择失败: {type(exc).__name__}: {exc}")

    def _open_settings(self, *_args) -> None:
        self.manager.current = "settings"

    # ------------------------------------------------------------ 转换并发送

    def _start_send(self, *_args) -> None:
        if self.busy:
            return
        files = [p for p in self.files if is_supported(p)]
        if not files:
            _alert("提示", "请先添加支持格式的文件")
            return
        errors = cfg_mod.validate_config(self.app.config_data)
        if errors:
            _alert("配置不完整", "请到「设置」里补全：\n\n" + "\n".join(errors))
            return
        self._set_busy(True)
        _set_keep_screen_on(True)
        self.log_view.text = ""
        threading.Thread(target=self._worker, args=(files,), daemon=True).start()

    def _worker(self, files: list[Path]) -> None:
        smtp_config = dict(self.app.config_data["smtp"])
        target = str(self.app.config_data["target_email"]).strip()
        sent: list[Path] = []
        failures: list[str] = []
        workdir = Path(tempfile.mkdtemp(prefix="stk_work_"))
        try:
            for i, path in enumerate(files, start=1):
                self.set_status(f"正在处理 {i}/{len(files)}: {path.name}")
                self.log(f"[{i}/{len(files)}] {path.name}")
                try:
                    attachment = prepare_for_send(path, workdir)
                except Exception as exc:  # noqa: BLE001  转换内核可能抛任意异常
                    failures.append(f"{path.name}：转换失败 - {exc}")
                    self.log(f"  转换失败: {exc}")
                    continue
                try:
                    self.log(f"  发送 {attachment.name} ...")
                    send_book(smtp_config, target, book_title(path), attachment)
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{path.name}：发送失败 - {type(exc).__name__}: {exc}")
                    self.log(f"  发送失败: {type(exc).__name__}: {exc}")
                    continue
                sent.append(path)
                self.log("  已发送")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            Clock.schedule_once(lambda _dt: self._finish(sent, failures))

    def _finish(self, sent: list[Path], failures: list[str]) -> None:
        _set_keep_screen_on(False)
        # 发送成功的文件移出列表，失败的保留，方便改好配置后重试
        for path in sent:
            self._discard(path)
        self._set_busy(False)
        self.status.text = f"完成：成功 {len(sent)} 个，失败 {len(failures)} 个"
        summary = f"成功发送 {len(sent)} 个文件"
        if failures:
            summary += "\n\n失败详情：\n" + "\n".join(failures)
        _alert("处理结果", summary)

    def _discard(self, path: Path) -> None:
        """移出列表；如果是 SAF 复制进 inbox 的副本，顺带删除。"""
        if path in self.files:
            self.files.remove(path)
        try:
            path.relative_to(INBOX)
        except ValueError:
            return  # 桌面调试时是用户的原文件，不能删
        shutil.rmtree(path.parent, ignore_errors=True)


class SettingsScreen(Screen):
    def __init__(self, app: "SendToKindleApp", **kwargs) -> None:
        super().__init__(name="settings", **kwargs)
        self.app = app

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        root.add_widget(Label(text="设置", bold=True, font_size="18sp", size_hint_y=None, height=ROW_H))

        form = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        form.bind(minimum_height=form.setter("height"))

        def field(label: str, widget):  # noqa: ANN001, ANN202
            form.add_widget(Label(text=label, halign="left", size_hint_y=None, height=dp(24),
                                  text_size=(Window.width - dp(16), None)))
            widget.size_hint_y = None
            widget.height = ROW_H
            form.add_widget(widget)
            return widget

        self.server = field("SMTP 服务器（如 smtp.qq.com）", TextInput(multiline=False))
        self.security = field("加密方式", Spinner(values=cfg_mod.SECURITY_OPTIONS, text="ssl"))
        self.security.bind(text=self._on_security)
        self.port = field("端口", TextInput(multiline=False, input_filter="int"))
        self.username = field("发件邮箱", TextInput(multiline=False))
        self.password = field("授权码 / 密码", TextInput(multiline=False, password=True))
        self.target = field("Kindle 邮箱（xxx@kindle.com）", TextInput(multiline=False))
        form.add_widget(Label(
            text="提示：发件邮箱需要先加进 Amazon「已认可的发件人电子邮箱列表」",
            size_hint_y=None, height=dp(40), color=(0.7, 0.7, 0.7, 1), font_size="12sp",
            text_size=(Window.width - dp(16), None),
        ))

        scroll = ScrollView()
        scroll.add_widget(form)
        root.add_widget(scroll)

        buttons = BoxLayout(size_hint_y=None, height=ROW_H, spacing=dp(6))
        buttons.add_widget(Button(text="保存", on_release=self._save))
        buttons.add_widget(Button(text="返回", on_release=self._back))
        root.add_widget(buttons)
        self.add_widget(root)
        self._snapshot: dict = self._collect()

    def on_pre_enter(self, *_args) -> None:
        smtp = self.app.config_data["smtp"]
        self.server.text = str(smtp.get("server", ""))
        security = smtp.get("security", "ssl")
        self.security.text = security if security in cfg_mod.SECURITY_OPTIONS else "ssl"
        self.port.text = str(smtp.get("port", ""))
        self.username.text = str(smtp.get("username", ""))
        self.password.text = str(smtp.get("password", ""))
        self.target.text = str(self.app.config_data.get("target_email", ""))
        # 记下表单初始状态，返回时据此判断是否有未保存的修改
        self._snapshot = self._collect()

    def _on_security(self, _spinner, value: str) -> None:  # noqa: ANN001
        # 端口为空或仍是另一种方式的默认端口时，自动切换
        if not self.port.text or self.port.text in {str(p) for p in cfg_mod.DEFAULT_PORTS.values()}:
            self.port.text = str(cfg_mod.DEFAULT_PORTS[value])

    def _collect(self) -> dict:
        port = self.port.text.strip()
        return {
            "smtp": {
                "server": self.server.text.strip(),
                "port": int(port) if port.isdigit() else port,
                "security": self.security.text,
                "username": self.username.text.strip(),
                "password": self.password.text,
            },
            "target_email": self.target.text.strip(),
        }

    def _save(self, *_args) -> None:
        config = self._collect()
        errors = cfg_mod.validate_config(config)
        if errors:
            _alert("配置不完整", "\n".join(errors))
            return
        try:
            cfg_mod.save_config(self.app.config_path, config)
        except OSError as exc:
            _alert("保存失败", f"{type(exc).__name__}: {exc}")
            return
        self.app.config_data = config
        self.manager.current = "main"

    def _back(self, *_args) -> None:
        if self._collect() == self._snapshot:
            self.manager.current = "main"
            return

        content = BoxLayout(orientation="vertical", spacing=dp(6))
        popup = Popup(title="提示", content=content, size_hint=(0.9, None), height=dp(200),
                      auto_dismiss=False)

        def on_save(*_a) -> None:
            popup.dismiss()
            self._save()  # 校验不通过时会弹出提示并留在设置页

        def on_discard(*_a) -> None:
            popup.dismiss()
            self.manager.current = "main"  # 下次进入设置页会按已保存的配置重新填充

        content.add_widget(Label(text="配置还未保存，是否保存？"))
        buttons = BoxLayout(size_hint_y=None, height=ROW_H, spacing=dp(6))
        buttons.add_widget(Button(text="保存", on_release=on_save))
        buttons.add_widget(Button(text="放弃", on_release=on_discard))
        buttons.add_widget(Button(text="取消", on_release=lambda *_a: popup.dismiss()))
        content.add_widget(buttons)
        popup.open()


class SendToKindleApp(App):
    title = "SendToKindle"

    def build(self):  # noqa: ANN201
        _register_cjk_font()
        Window.softinput_mode = "below_target"  # 软键盘不遮挡输入框
        self.config_path = Path(self.user_data_dir) / "config.json"
        self.config_data = cfg_mod.load_config(self.config_path)
        # 上次进程被杀时残留的 SAF 副本
        shutil.rmtree(INBOX, ignore_errors=True)

        manager = ScreenManager(transition=NoTransition())
        manager.add_widget(MainScreen(self))
        manager.add_widget(SettingsScreen(self))
        if cfg_mod.validate_config(self.config_data):
            manager.current = "settings"  # 首次使用或配置损坏：直接进设置页
        return manager

    def on_pause(self) -> bool:
        return True  # 切到后台不退出，后台线程继续发送

    def on_resume(self) -> None:
        pass


if __name__ == "__main__":
    SendToKindleApp().run()
