from __future__ import annotations

import copy
import json
from pathlib import Path

from .paths import app_dir

CONFIG_PATH = app_dir() / "config.json"

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

SECURITY_OPTIONS = ("ssl", "starttls", "plain")

DEFAULT_PORTS = {"ssl": 465, "starttls": 587, "plain": 25}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULT_CONFIG)
    config = copy.deepcopy(DEFAULT_CONFIG)
    _merge(config, data)
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _merge(base[key], value)
        else:
            base[key] = value


def validate_config(config: dict) -> list[str]:
    errors: list[str] = []
    smtp = config.get("smtp", {})
    if not smtp.get("server", "").strip():
        errors.append("SMTP 服务器地址不能为空")
    if not str(smtp.get("port", "")).strip().isdigit():
        errors.append("SMTP 端口必须是数字")
    if not smtp.get("username", "").strip():
        errors.append("邮箱账号不能为空")
    if not smtp.get("password", ""):
        errors.append("邮箱密码/授权码不能为空")
    if not config.get("target_email", "").strip():
        errors.append("目标邮箱不能为空")
    return errors
