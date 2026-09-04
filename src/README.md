# Source tree

The reusable RobotBona core/server will be extracted here from the sanitized v4 reference implementation.

Planned boundaries:

```text
robotbona/
  protocol.py
  commands.py
  state.py
  capabilities.py
  map_decoder.py
  http_server.py
  tcp_server.py
  service.py

robotbona_api/
  app.py
```

Do not implement Home Assistant-specific behaviour in this layer.
