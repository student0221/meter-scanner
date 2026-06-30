import unittest

from meter_scanner.scanner import MeterScanner


class ScannerTests(unittest.TestCase):
    def test_make_result_includes_progress_metadata_when_supplied(self):
        scanner = MeterScanner(port="COM1")
        result = scanner._make_result(
            2400, 8, "E", 1, False, "无应答", b"", "",
            index=2, total=4,
        )

        self.assertEqual(result["index"], 2)
        self.assertEqual(result["total"], 4)


if __name__ == "__main__":
    unittest.main()
