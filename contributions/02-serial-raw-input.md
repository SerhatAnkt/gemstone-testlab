# serial: preserve raw input bytes in the C and C++ terminals

The C and C++ serial examples retain terminal input translation flags. With
default PTY settings, sending `5258007f80ff0d0a0d454e44` produces
`5258007f80ff0a0a0a454e44`: CR bytes become LF. A fragmented duplex transfer
also corrupts its CR/LF fragment.

Clear the input translation, stripping, and parity-processing flags when
configuring raw I/O. The two affected files are `serial/c/main.c` and
`serial/cpp/serial_terminal.cpp`; the patch is
`patches/0002-serial-preserve-raw-input-bytes.patch`.

Independent PTY tests compare exact CR/LF, NUL, and high bytes. The fixture
deliberately leaves initial device input flags intact so it can expose the
application's configuration error.

```sh
.venv-testlab/bin/python tools/check_contributions.py --entry 02 --output artifacts/pr02-first
```

Validation scope: four focused baseline failures, then four passing cases
with this patch alone. Attach the actual before/after JSON/JUnit and transfer
logs. These Linux PTY tests validate software byte handling, not electrical
UART behavior, physical baud timing, or O1 hardware.

Base: `2619a7584d39203a057abc08ab7c6698dc476868`. Verify against the target branch
before submission. This draft has not been submitted.
