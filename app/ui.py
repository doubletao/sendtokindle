from __future__ import annotations

import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import config as config_mod
from .converter import ConversionError, book_title, convert_to_epub, is_supported
from .sender import send_book

_FILE_TYPES = [
    ("电子书文件", "*.epub *.mobi *.azw *.azw3 *.prc *.docx *.html *.htm *.txt *.md *.markdown *.pdf *.odt *.fb2 *.rtf"),
    ("所有文件", "*.*"),
]


class ConfigDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, current: dict) -> None:
        super().__init__(parent)
        self.title("邮箱配置")
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None

        frame = ttk.Frame(self, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")

        self.server_var = tk.StringVar(value=current["smtp"]["server"])
        self.port_var = tk.StringVar(value=str(current["smtp"]["port"]))
        self.security_var = tk.StringVar(value=current["smtp"]["security"])
        self.username_var = tk.StringVar(value=current["smtp"]["username"])
        self.password_var = tk.StringVar(value=current["smtp"]["password"])
        self.target_var = tk.StringVar(value=current["target_email"])

        rows = [
            ("SMTP 服务器", self.server_var),
            ("端口", self.port_var),
            ("邮箱账号", self.username_var),
            ("密码/授权码", self.password_var),
            ("目标邮箱", self.target_var),
        ]
        for i, (label, var) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=4)
            show = "•" if "密码" in label else ""
            ttk.Entry(frame, textvariable=var, width=36, show=show).grid(
                row=i, column=1, sticky="ew", pady=4, padx=(8, 0)
            )

        ttk.Label(frame, text="加密方式").grid(row=5, column=0, sticky="w", pady=4)
        security_box = ttk.Combobox(
            frame,
            textvariable=self.security_var,
            values=list(config_mod.SECURITY_OPTIONS),
            state="readonly",
            width=34,
        )
        security_box.grid(row=5, column=1, sticky="ew", pady=4, padx=(8, 0))
        security_box.bind("<<ComboboxSelected>>", self._on_security_changed)

        btns = ttk.Frame(frame)
        btns.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btns, text="保存", command=self._save).grid(row=0, column=0, padx=6)
        ttk.Button(btns, text="取消", command=self.destroy).grid(row=0, column=1, padx=6)

    def _on_security_changed(self, _event: object = None) -> None:
        security = self.security_var.get()
        current_port = self.port_var.get().strip()
        known = {str(p) for p in config_mod.DEFAULT_PORTS.values()}
        if current_port in known or not current_port:
            self.port_var.set(str(config_mod.DEFAULT_PORTS.get(security, 587)))

    def _save(self) -> None:
        port_text = self.port_var.get().strip()
        if not port_text.isdigit():
            messagebox.showerror("配置错误", "端口必须是数字", parent=self)
            return
        self.result = {
            "smtp": {
                "server": self.server_var.get().strip(),
                "port": int(port_text),
                "security": self.security_var.get(),
                "username": self.username_var.get().strip(),
                "password": self.password_var.get(),
            },
            "target_email": self.target_var.get().strip(),
        }
        self.destroy()


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Send to Kindle")
        self.geometry("640x420")
        self.minsize(560, 360)

        self.config_data = config_mod.load_config()
        self.worker_queue: queue.Queue = queue.Queue()
        self.worker_thread: threading.Thread | None = None

        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=(10, 10, 10, 0))
        top.pack(fill="both", expand=True)

        list_frame = ttk.Frame(top)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_frame, selectmode="extended", yscrollcommand=scrollbar.set
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        btn_bar = ttk.Frame(top)
        btn_bar.pack(fill="x", pady=(8, 0))

        ttk.Button(btn_bar, text="添加文件", command=self._add_files).pack(side="left")
        ttk.Button(btn_bar, text="删除选中", command=self._remove_selected).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(btn_bar, text="配置", command=self._open_config).pack(side="left", padx=(6, 0))

        self.send_btn = ttk.Button(btn_bar, text="转换并发送", command=self._start_send)
        self.send_btn.pack(side="right")

        self.status_var = tk.StringVar(value="就绪")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(10, 6))
        status.pack(fill="x", side="bottom")

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(title="选择电子书文件", filetypes=_FILE_TYPES)
        existing = {self.listbox.get(i) for i in range(self.listbox.size())}
        added = 0
        for path in paths:
            if not is_supported(path):
                continue
            if path in existing:
                continue
            self.listbox.insert("end", path)
            existing.add(path)
            added += 1
        if paths and added == 0:
            self.status_var.set("所选文件已在列表中或格式不支持")

    def _remove_selected(self) -> None:
        for index in reversed(self.listbox.curselection()):
            self.listbox.delete(index)

    def _open_config(self) -> None:
        dialog = ConfigDialog(self, self.config_data)
        self.wait_window(dialog)
        if dialog.result is not None:
            self.config_data = dialog.result
            config_mod.save_config(self.config_data)
            self.status_var.set("配置已保存")

    def _start_send(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        files = [self.listbox.get(i) for i in range(self.listbox.size())]
        if not files:
            messagebox.showwarning("提示", "请先添加文件")
            return
        errors = config_mod.validate_config(self.config_data)
        if errors:
            messagebox.showwarning("配置不完整", "\n".join(errors))
            return
        self.send_btn.config(state="disabled")
        self.status_var.set("正在处理...")
        self.worker_thread = threading.Thread(
            target=self._worker, args=(files,), daemon=True
        )
        self.worker_thread.start()

    def _worker(self, files: list[str]) -> None:
        smtp_config = self.config_data["smtp"]
        target = self.config_data["target_email"].strip()
        ok = 0
        failures: list[str] = []
        with tempfile.TemporaryDirectory(prefix="sendtokindle_") as tmp:
            workdir = Path(tmp)
            for i, path in enumerate(files, start=1):
                name = Path(path).name
                self.worker_queue.put(("status", f"正在处理 {i}/{len(files)}: {name}"))
                try:
                    epub = convert_to_epub(path, workdir)
                    send_book(smtp_config, target, book_title(path), epub)
                except ConversionError as exc:
                    failures.append(f"{name}：转换失败 - {exc}")
                except Exception as exc:
                    failures.append(f"{name}：发送失败 - {exc}")
                else:
                    ok += 1
        self.worker_queue.put(("done", (ok, failures)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.worker_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                elif kind == "done":
                    ok, failures = payload
                    self.send_btn.config(state="normal")
                    self.status_var.set(f"完成：成功 {ok} 个，失败 {len(failures)} 个")
                    summary = f"成功发送 {ok} 个文件"
                    if failures:
                        summary += "\n\n失败详情：\n" + "\n".join(failures)
                    messagebox.showinfo("处理结果", summary)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)
