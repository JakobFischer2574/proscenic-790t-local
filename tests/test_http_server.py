from datetime import datetime, timezone

from robotbona.http_server import HTTPServiceConfig, chunked_response, token_response_body


def test_token_body_has_cloud_compatible_shape_without_real_credentials():
    body = token_response_body(
        HTTPServiceConfig("SANITIZED_APP", "SANITIZED_DEVICE", "LOCAL_DUMMY_TOKEN")
    )
    assert body == (
        b'{"msg":"ok","result":"0","data":{"appKey":"SANITIZED_APP",'
        b'"deviceNo":"SANITIZED_DEVICE","token":"LOCAL_DUMMY_TOKEN"},'
        b'"version":"1.0.0"}'
    )


def test_response_uses_chunked_transfer_encoding_like_working_baseline():
    body = b'{"msg":"ok"}'
    response = chunked_response(
        body, now=datetime(2026, 9, 4, 11, 0, 0, tzinfo=timezone.utc)
    )
    assert b"Transfer-Encoding: chunked\r\n" in response
    assert b"Content-Type: application/json;charset=UTF-8\r\n" in response
    chunk_prefix = f"{len(body):x}\r\n".encode("ascii")
    assert response.endswith(chunk_prefix + body + b"\r\n0\r\n\r\n")
