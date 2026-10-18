# SPDX-License-Identifier: Apache-2.0
import sys
import unittest

from tests.testlab.contracts import CanFrame, encode_classic_frame, parse_receiver_line, require_frame


class ReceiverContractTests(unittest.TestCase):
    def test_encoder_matches_linux_classic_layout(self):
        identifier = (0x123).to_bytes(4, sys.byteorder)
        self.assertEqual(encode_classic_frame(CanFrame(0x123, b'A')), identifier+b'\x01\x00\x00\x00A'+b'\x00'*7)

    def test_encoder_rejects_invalid_standard_frames(self):
        for frame in (CanFrame(-1, b''), CanFrame(0x800, b''), CanFrame(0x80000123, b''),
                      CanFrame(0x123, b'123456789'), CanFrame(0x123, 'A')):
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                encode_classic_frame(frame)

    def test_zero_one_and_eight_byte_console_frames(self):
        samples = ((b"Received: ID=0x123, DLC=0, Data=('')", b''),
                   (b"Received: ID=0x123, DLC=1, Data=41 ('A')", b'A'),
                   (b"Received: ID=0x123, DLC=8, Data=41 42 43 44 45 46 47 48 ('ABCDEFGH')", b'ABCDEFGH'))
        for line, payload in samples:
            with self.subTest(payload=payload):
                require_frame(parse_receiver_line(line).frame, CanFrame(0x123, payload))

    def test_nonprintable_hex_bytes_are_preserved(self):
        output = parse_receiver_line(b"Received: ID=0x123, DLC=8, Data=00 01 1F 20 7F 80 FF 41 ('... ...A')")
        self.assertEqual(output.frame.data, b'\x00\x01\x1f \x7f\x80\xffA')
        self.assertEqual(output.text, '... ...A')

    def test_id_case_spacing_and_crlf_are_presentation_only(self):
        output = parse_receiver_line(b"Received: ID=0x0a, DLC=1, Data=7e  ('~')\r\n")
        require_frame(output.frame, CanFrame(0xA, b'~'))
        with self.assertRaises(AssertionError):
            require_frame(output.frame, CanFrame(0xB, b'~'))

    def test_dlc_hex_and_text_corruption_are_rejected(self):
        lines = (b"Received: ID=0x123, DLC=1, Data=('')",
                 b"Received: ID=0x123, DLC=0, Data=00 ('.')",
                 b"Received: ID=0x123, DLC=1, Data=GG ('.')",
                 b"Received: ID=0x123, DLC=1, Data=0 ('.')",
                 b"Received: ID=0x123, DLC=1, Data=41 ('B')",
                 b"Received: ID=0x123, DLC=1, Data=00 ('')",
                 b"Received: ID=0x123, DLC=9, Data=('')",
                 b"Received: broken")
        for line in lines:
            with self.subTest(line=line), self.assertRaises(ValueError):
                parse_receiver_line(line)

    def test_flagged_id_is_not_silently_masked(self):
        for identifier in (b'800', b'80000123', b'40000123', b'20000123'):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                parse_receiver_line(b"Received: ID=0x"+identifier+b", DLC=0, Data=('')")

    def test_quotes_remain_payload_and_banners_are_ignored(self):
        output = parse_receiver_line(b"Received: ID=0x123, DLC=3, Data=27 28 29 (''()')")
        self.assertEqual(output.frame.data, b"'()")
        self.assertIsNone(parse_receiver_line(b'CAN Receiver starting on interface: gtl0123456789'))
        self.assertIsNone(parse_receiver_line(b'Received END message, stopping receiver'))
