import unittest

from meter_scanner.protocol import (
    HexFrameError,
    build_read_addr_frame,
    calc_checksum,
    extract_complete_frame,
    parse_hex_frame_text,
    verify_frame,
)


def make_frame(ctrl=0x93, data=b""):
    frame = bytearray([0x68, 1, 2, 3, 4, 5, 6, 0x68, ctrl, len(data)])
    frame.extend(data)
    frame.append(calc_checksum(frame))
    frame.append(0x16)
    return bytes(frame)


class ProtocolTests(unittest.TestCase):
    def test_parse_hex_frame_rejects_odd_digit_count(self):
        with self.assertRaises(HexFrameError):
            parse_hex_frame_text("68 A")

    def test_parse_hex_frame_rejects_empty_input(self):
        with self.assertRaises(HexFrameError):
            parse_hex_frame_text(" , ; ")

    def test_extract_complete_frame_uses_length_field_not_first_16_byte(self):
        frame = make_frame(data=bytes([0x16, 0x33]))
        self.assertEqual(extract_complete_frame(frame), frame)
        self.assertEqual(extract_complete_frame(frame[:-1]), None)

    def test_verify_frame_rejects_unknown_control_code(self):
        ok, msg, addr = verify_frame(make_frame(ctrl=0x81))
        self.assertFalse(ok)
        self.assertEqual(addr, "060504030201")
        self.assertIn("未知应答控制码", msg)

    def test_verify_frame_accepts_trailing_bytes_after_complete_frame(self):
        ok, msg, addr = verify_frame(build_read_addr_frame() + b"\x99")
        self.assertFalse(ok)
        self.assertIn("未知应答控制码", msg)


if __name__ == "__main__":
    unittest.main()
