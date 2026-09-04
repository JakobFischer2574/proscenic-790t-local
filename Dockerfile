FROM python:3.13-alpine

ARG BUILD_VERSION=0.1.0
ARG BUILD_ARCH=amd64

LABEL org.opencontainers.image.source="https://github.com/JakobFischer2574/proscenic-790t-local" \
      org.opencontainers.image.description="Fully local RobotBona server for Proscenic 790T" \
      io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}"

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

ENV ROBOTBONA_HTTP_HOST=0.0.0.0 \
    ROBOTBONA_HTTP_PORT=18080 \
    ROBOTBONA_TCP_HOST=0.0.0.0 \
    ROBOTBONA_TCP_PORT=20008 \
    ROBOTBONA_API_HOST=0.0.0.0 \
    ROBOTBONA_API_PORT=8090 \
    ROBOTBONA_DATA_DIR=/data

VOLUME ["/data"]
EXPOSE 18080/tcp 20008/tcp 8090/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json,os,urllib.request; json.load(urllib.request.urlopen('http://127.0.0.1:'+os.getenv('ROBOTBONA_API_PORT','8090')+'/api/health', timeout=3))" || exit 1

CMD ["python", "-m", "robotbona"]
