# Tests

Protocol refactors should be protected by regression tests before the monolithic reference is retired.

Priority test areas:

- 20-byte frame construction/parsing
- login ACK bytes and JSON payload shape
- normal ACK and keepalive ACK framing
- control packet header/magic
- command sequence handling
- ordered parameter serialization (`mode`/`fan` before `transitCmd`)
- status parsing while preserving unknown/raw values
- map and track decoding with sanitized fixtures

Never commit raw packet captures or unredacted robot messages as fixtures.
