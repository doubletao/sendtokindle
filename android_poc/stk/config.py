"""配置读写，移植自桌面版 app/config.py。

与桌面版的差异：
- 配置路径由调用方传入（Android 上是 App.user_data_dir，应用私有目录）。
- 去掉 plain 加密方式，避免授权码明文传输。
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

DEFAULT_CONFIG: dict = {
    "smtp": {
        "server": "",
        "port": 465,
        "security": "ssl",
        "username": "",
        "password": "",
    },
    "target_email": "",
}

SECURITY_OPTIONS = ("ssl", "starttls")

DEFAULT_PORTS = {"ssl": 465, "starttls": 587}


def default_config() -> dict:
    return copy.deepcopy(DEFAULT_CONFIG)


def load_config(path: Path) -> dict:
    """读取配置；文件不存在或损坏时返回默认配置，由用户重新填写。"""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default_config()
    config = default_config()
    if isinstance(data, dict):
        _merge(config, data)
    return config


def save_config(path: Path, config: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _merge(base[key], value)
        else:
            base[key] = value


def validate_config(config: dict) -> list[str]:
    errors: list[str] = []
    smtp = config.get("smtp") or {}
    if not str(smtp.get("server", "")).strip():
        errors.append("SMTP 服务器地址不能为空")
    if not str(smtp.get("port", "")).strip().isdigit():
        errors.append("SMTP 端口必须是数字")
    if smtp.get("security") not in SECURITY_OPTIONS:
        errors.append("加密方式只能是 ssl 或 starttls")
    if not str(smtp.get("username", "")).strip():
        errors.append("邮箱账号不能为空")
    if not smtp.get("password", ""):
        errors.append("邮箱密码/授权码不能为空")
    if not str(config.get("target_email", "")).strip():
        errors.append("Kindle 邮箱不能为空")
    return errors
