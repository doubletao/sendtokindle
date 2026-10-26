import tempfile
import unittest
import zipfile
from pathlib import Path

from stk.convert import (
    ConversionError,
    _safe_filename,
    book_title,
    is_supported,
    prepare_for_send,
)

ASSETS = Path(__file__).resolve().parent.parent / "assets"


class HelpersTest(unittest.TestCase):
    def test_is_supported(self) -> None:
        for name in ("a.txt", "a.MOBI", "a.azw3", "a.epub", "a.pdf", "a.docx"):
            self.assertTrue(is_supported(name), name)
        for name in ("a.odt", "a.zip", "noext"):
            self.assertFalse(is_supported(name), name)

    def test_book_title(self) -> None:
        self.assertEqual(book_title("/x/三体.mobi"), "三体")

    def test_safe_filename(self) -> None:
        self.assertEqual(_safe_filename('a:b?"c'), "a_b__c")
        self.assertEqual(_safe_filename(" .. "), "book")


class PrepareForSendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_epub_and_pdf_sent_as_is(self) -> None:
        for name in ("a.epub", "b.PDF"):
            src = self.workdir / name
            src.write_bytes(b"x")
            self.assertEqual(prepare_for_send(src, self.workdir), src)

    def test_unsupported_raises(self) -> None:
        with self.assertRaises(ConversionError):
            prepare_for_send(self.workdir / "a.odt", self.workdir)

    def _assert_epub(self, path: Path) -> None:
        self.assertTrue(path.is_file())
        self.assertEqual(path.suffix, ".epub")
        with zipfile.ZipFile(path) as zf:
            self.assertEqual(zf.read("mimetype"), b"application/epub+zip")

    def test_convert_samples(self) -> None:
        for name in ("sample.txt", "sample.mobi", "sample.azw3"):
            with self.subTest(name=name):
                out = prepare_for_send(ASSETS / name, self.workdir)
                self._assert_epub(out)

    def test_same_title_does_not_overwrite(self) -> None:
        first = prepare_for_send(ASSETS / "sample.txt", self.workdir)
        second = prepare_for_send(ASSETS / "sample.mobi", self.workdir)
        self.assertNotEqual(first, second)
        self.assertEqual(second.name, "sample_1.epub")
        self._assert_epub(first)


if __name__ == "__main__":
    unittest.main()
