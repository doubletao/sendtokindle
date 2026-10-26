import tempfile
import unittest
from pathlib import Path

from stk import config as cfg


def _valid() -> dict:
    return {
        "smtp": {
            "server": "smtp.example.com",
            "port": 465,
            "security": "ssl",
            "username": "me@example.com",
            "password": "secret",
        },
        "target_email": "me@kindle.com",
    }


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sub" / "config.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_missing_file_returns_default(self) -> None:
        self.assertEqual(cfg.load_config(self.path), cfg.DEFAULT_CONFIG)

    def test_round_trip(self) -> None:
        cfg.save_config(self.path, _valid())
        self.assertEqual(cfg.load_config(self.path), _valid())

    def test_round_trip_keeps_chinese(self) -> None:
        data = _valid()
        data["smtp"]["password"] = "中文授权码"
        cfg.save_config(self.path, data)
        self.assertEqual(cfg.load_config(self.path)["smtp"]["password"], "中文授权码")

    def test_partial_file_merged_with_defaults(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"smtp": {"server": "s"}}', encoding="utf-8")
        loaded = cfg.load_config(self.path)
        self.assertEqual(loaded["smtp"]["server"], "s")
        self.assertEqual(loaded["smtp"]["port"], 465)
        self.assertEqual(loaded["target_email"], "")

    def test_corrupt_json_returns_default(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(cfg.load_config(self.path), cfg.DEFAULT_CONFIG)

    def test_non_dict_json_returns_default(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(cfg.load_config(self.path), cfg.DEFAULT_CONFIG)

    def test_default_is_not_shared(self) -> None:
        cfg.load_config(self.path)["smtp"]["server"] = "changed"
        self.assertEqual(cfg.DEFAULT_CONFIG["smtp"]["server"], "")

    def test_validate_ok(self) -> None:
        self.assertEqual(cfg.validate_config(_valid()), [])

    def test_validate_default_reports_all_missing(self) -> None:
        errors = cfg.validate_config(cfg.default_config())
        self.assertEqual(len(errors), 4)  # server / username / password / target

    def test_validate_rejects_plain_and_bad_port(self) -> None:
        data = _valid()
        data["smtp"]["security"] = "plain"
        data["smtp"]["port"] = "abc"
        errors = cfg.validate_config(data)
        self.assertTrue(any("端口" in e for e in errors))
        self.assertTrue(any("加密方式" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
