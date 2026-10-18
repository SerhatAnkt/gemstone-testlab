# serial: reject malformed baud arguments before opening the device

`atoi("9600oops")` and `std::atoi("9600oops")` both return 9600. The C and C++
examples therefore open the device and print the startup message for a
malformed argument. A later terminal initialization error does not mean the
baud argument was rejected at the correct stage.

Use `strtol` with an end pointer and range checks. Reject an empty conversion,
trailing characters, `ERANGE`, nonpositive values, and values beyond `INT_MAX`
before device initialization. Existing supported-speed checks remain in place.
The patch changes `serial/c/main.c` and `serial/cpp/main.cpp`:
`patches/0003-serial-reject-partial-baud-arguments.patch`.

```sh
.venv-testlab/bin/python tools/check_contributions.py --entry 03 --output artifacts/pr03-first
```

Validation scope: the two `9600oops` baseline cases fail because the startup
message appears, then both pass with this patch alone. Broader zero,
nonnumeric, unsupported-speed, and valid-transfer checks belong to the full
serial suite. Attach actual before/after JSON/JUnit and CLI logs. No physical
baud-rate measurement is claimed.

Base: `2619a7584d39203a057abc08ab7c6698dc476868`. Verify against the target branch
before submission. This draft has not been submitted.
