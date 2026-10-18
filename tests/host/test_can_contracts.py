# SPDX-License-Identifier: Apache-2.0
import sys
import unittest

from tests.testlab.can import validate_interface_name
from tests.testlab.contracts import CanFrame, FIRST, END, decode_classic_frame, require_frame


def golden(header, length, payload):
    raw_id = bytes.fromhex(header)
    if sys.byteorder == "big":
        raw_id = raw_id[::-1]
    return raw_id+bytes([length, 0, 0, 0])+payload.ljust(8, b"\0")


class CanContractTests(unittest.TestCase):
    def test_c_and_cpp_first_frame_keeps_nul_byte(self):
        frame = decode_classic_frame(golden("23010000", 8, b"MSG_000\0"))
        require_frame(frame, FIRST["c"])
        require_frame(frame, FIRST["cpp"])

    def test_python_first_frame_is_seven_bytes(self):
        frame = decode_classic_frame(golden("23010000", 7, b"MSG_000"))
        require_frame(frame, FIRST["python"])
        with self.assertRaises(AssertionError):
            require_frame(frame, FIRST["c"])

    def test_wrong_id_payload_or_length_fails(self):
        for frame in (CanFrame(0x125, b"END"), CanFrame(0x124, b"BAD"), CanFrame(0x124, b"END\0")):
            with self.subTest(frame=frame), self.assertRaises(AssertionError):
                require_frame(frame, END)

    def test_non_classic_or_invalid_lengths_are_rejected(self):
        for raw in (b"", b"\0"*15, b"\0"*72, golden("23010000", 9, b"12345678")):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                decode_classic_frame(raw)

    def test_extended_remote_and_error_flags_are_not_masked(self):
        for header in ("23010080", "23010040", "23010020", "00080000"):
            with self.subTest(header=header), self.assertRaises(ValueError):
                decode_classic_frame(golden(header, 0, b""))

    def test_interface_name_boundary_precedes_privileged_operations(self):
        self.assertEqual(validate_interface_name("gtl0123456789"), "gtl0123456789")
        for name in ("vcan0", "eth0", "gtl", "gtl0123456789;", "gtl01234567890", "gtlABCDEFGHIJ"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_interface_name(name)
