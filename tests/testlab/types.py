# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    id: str
    directory: str
    language: str
    binary: str
    sources: tuple[str, ...]
    headers: tuple[str, ...] = ()

    @property
    def inputs(self) -> tuple[str, ...]:
        return tuple(f"{self.directory}/{name}"
                     for name in ("Makefile", *self.sources, *self.headers))
