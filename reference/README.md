# Reference implementation

This directory preserves a **sanitized public reference** of the monolithic v4 service that was empirically proven to work with the tested Proscenic 790T before the project is refactored into modules.

The public copy must never contain the real device ID, auth code, MAC address, Wi-Fi credentials, LAN IP assignments, captured tokens or raw packet/log data.

`robotbona_local_service_v4_sanitized.py` keeps the known working framing, ACK handling, command construction, state parsing and console controls. Installation-specific values are replaced by environment variables/placeholders.

This file is a regression/reference artifact, not the desired final architecture. New development belongs under `src/`, with tests protecting the proven wire behaviour.
