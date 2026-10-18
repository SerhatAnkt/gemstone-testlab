# SPDX-License-Identifier: Apache-2.0
from .types import Target

TARGETS = (
    Target("can.c.sender", "canbus/c/sender", "c", "canbus-sender", ("main.c",)),
    Target("can.c.receiver", "canbus/c/receiver", "c", "canbus-receiver", ("main.c",)),
    Target("can.cpp.sender", "canbus/cpp/sender", "cpp", "canbus-sender",
           ("main.cpp", "can_sender.cpp"), ("can_sender.h",)),
    Target("can.cpp.receiver", "canbus/cpp/receiver", "cpp", "canbus-receiver",
           ("main.cpp", "can_receiver.cpp"), ("can_receiver.h",)),
    Target("serial.c", "serial/c", "c", "serial", ("main.c",)),
    Target("serial.cpp", "serial/cpp", "cpp", "serial",
           ("main.cpp", "serial_terminal.cpp"), ("serial_terminal.h",)),
)
BY_ID = {target.id: target for target in TARGETS}


def select_targets(ids: list[str] | None = None) -> tuple[Target, ...]:
    if ids is None:
        return TARGETS
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Select at least one target; duplicate target ids are not allowed")
    unknown = set(ids) - BY_ID.keys()
    if unknown:
        raise ValueError(f"Unknown target ids: {', '.join(sorted(unknown))}")
    return tuple(BY_ID[name] for name in ids)
