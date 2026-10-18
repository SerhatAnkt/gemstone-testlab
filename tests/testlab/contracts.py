# SPDX-License-Identifier: Apache-2.0
"""Reviewed message expectations, independent of the sender implementations."""
from dataclasses import dataclass
import re
import struct

CONTRACT = "can_examples_v1"


@dataclass(frozen=True)
class CanFrame:
    can_id: int
    data: bytes

    def evidence(self):
        return {"can_id": self.can_id, "length": len(self.data), "data_hex": self.data.hex()}


FIRST = {"c": CanFrame(0x123, b"MSG_000\x00"),
         "cpp": CanFrame(0x123, b"MSG_000\x00"),
         "python": CanFrame(0x123, b"MSG_000")}
END = CanFrame(0x124, b"END")
READY = CanFrame(0x321, b"GTLREADY")


def encode_classic_frame(frame):
    if not isinstance(frame.can_id, int) or not 0 <= frame.can_id <= 0x7FF:
        raise ValueError("Expected standard CAN ID in 0..0x7ff")
    if not isinstance(frame.data, bytes) or len(frame.data) > 8:
        raise ValueError("Expected at most eight payload bytes")
    return struct.pack("=IB3x8s", frame.can_id, len(frame.data), frame.data)


def receiver_text(data):
    return ''.join(chr(value) if 32 <= value <= 126 else '.' for value in data)


@dataclass(frozen=True)
class ReceiverOutput:
    frame: CanFrame
    text: str

    def evidence(self):
        return {**self.frame.evidence(), "text": self.text}


def parse_receiver_line(line):
    """Ignore banners; reject malformed frame lines without losing any bytes."""
    line = line.rstrip(b"\r\n")
    if not line.startswith(b"Received:"):
        return None
    match = re.fullmatch(rb"Received: ID=0x([0-9A-Fa-f]{1,8}), DLC=([0-9]+), Data=(.*?)\('(.*)'\)", line)
    if not match:
        raise ValueError(f"Malformed receiver frame line: {line!r}")
    identifier, length, hexadecimal, text = match.groups()
    tokens = hexadecimal.split()
    if any(re.fullmatch(rb"[0-9A-Fa-f]{2}", token) is None for token in tokens):
        raise ValueError("Receiver hex output contains malformed bytes")
    frame = CanFrame(int(identifier, 16), bytes(int(token, 16) for token in tokens))
    encode_classic_frame(frame)  # Same standard-ID/length boundary as the reference endpoint.
    if len(frame.data) != int(length):
        raise ValueError("Receiver DLC does not match its hex output")
    expected_text = receiver_text(frame.data).encode('ascii')
    if text != expected_text:
        raise ValueError("Receiver text does not match the printable-byte contract")
    return ReceiverOutput(frame, text.decode('ascii'))


def decode_classic_frame(raw):
    if len(raw) != 16:
        raise ValueError(f"Expected Linux classic CAN frame size 16, got {len(raw)}")
    can_id, length, payload = struct.unpack("=IB3x8s", raw)
    if can_id > 0x7FF:
        raise ValueError(f"Expected standard data frame without EFF/RTR/ERR flags: {can_id:#x}")
    if length > 8:
        raise ValueError(f"Classic CAN data length exceeds eight: {length}")
    return CanFrame(can_id, payload[:length])


def require_frame(actual, expected):
    if actual != expected:
        raise AssertionError(f"CAN frame mismatch: expected={expected.evidence()}, actual={actual.evidence()}")
