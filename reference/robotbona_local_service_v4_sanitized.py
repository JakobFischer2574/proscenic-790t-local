import json
import os
import socket
import socketserver
import struct
import threading
from datetime import datetime, timezone
from pathlib import Path

# ============================================================
# Proscenic 790T - fully local RobotBona replacement
# SANITIZED PUBLIC REFERENCE of the empirically working v4 baseline.
# Installation-specific identifiers have been replaced with environment values.
# HTTP token server on :80
# TCP status/control server on :20008
# ============================================================

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 80
TCP_HOST = "0.0.0.0"
TCP_PORT = 20008

# Public/sanitized reference: configure installation-specific values via environment.
APP_KEY = os.getenv("ROBOTBONA_APP_KEY", "REPLACE_WITH_APP_KEY")
DEVICE_ID = os.getenv("ROBOTBONA_DEVICE_ID", "REPLACE_WITH_DEVICE_ID")

# Completely local, self-generated 32-character token. The tested firmware did
# not require cloud validation. This default is intentionally a public dummy.
LOCAL_TOKEN = os.getenv(
    "ROBOTBONA_LOCAL_TOKEN",
    "LOCAL790T00000000000000000000000",
)

LOG_FILE = Path("robotbona_local_service.log")
STATE_FILE = Path("latest_state.json")
MAP_FILE = Path("latest_map.txt")
TRACK_FILE = Path("latest_track.txt")
MESSAGES_FILE = Path("robotbona_local_messages.jsonl")

active_lock = threading.Lock()
active_conn = None
active_addr = None

robot_info = {
    "deviceId": None,
    "authCode": None,
    "deviceIp": None,
    "devicePort": "8888",
}

latest_state = {}

command_seq_lock = threading.Lock()
command_seq = 0x2701
command_target_id = "0"


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def log(msg):
    line = f"[{stamp()}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ============================================================
# HTTP :80
# ============================================================

def chunked_response(body: bytes):
    date_value = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    head = (
        b"HTTP/1.1 200 \r\n"
        b"Server: nginx\r\n"
        + f"Date: {date_value}\r\n".encode("ascii")
        + b"Content-Type: application/json;charset=UTF-8\r\n"
        + b"Transfer-Encoding: chunked\r\n"
        + b"Connection: close\r\n"
        + b"\r\n"
    )
    return head + f"{len(body):x}\r\n".encode("ascii") + body + b"\r\n0\r\n\r\n"


class HTTPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        data = bytearray()

        while b"\r\n\r\n" not in data:
            part = self.request.recv(4096)
            if not part:
                return
            data.extend(part)

        header_end = data.index(b"\r\n\r\n") + 4
        header = bytes(data[:header_end])

        content_length = 0
        for line in header.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                try:
                    content_length = int(line.split(b":", 1)[1].strip())
                except ValueError:
                    pass

        while len(data) - header_end < content_length:
            part = self.request.recv(content_length - (len(data) - header_end))
            if not part:
                break
            data.extend(part)

        request_line = header.split(b"\r\n", 1)[0]
        body_in = bytes(data[header_end:])

        log(f"HTTP {self.client_address[0]} -> {request_line.decode(errors='replace')}")

        if b"/baole-web/common/getToken.do" in request_line:
            body = (
                '{"msg":"ok","result":"0","data":{'
                f'"appKey":"{APP_KEY}",'
                f'"deviceNo":"{DEVICE_ID}",'
                f'"token":"{LOCAL_TOKEN}"'
                '},"version":"1.0.0"}'
            ).encode("utf-8")
            self.request.sendall(chunked_response(body))
            log("HTTP getToken -> local token configured")

        elif b"/baole-web/common/uploadLog.do" in request_line:
            body = b'{"msg":"ok","result":"0","version":"1.0.0"}'
            self.request.sendall(chunked_response(body))
            log("HTTP uploadLog -> OK")

        else:
            body = b'{"msg":"ok","result":"0","version":"1.0.0"}'
            self.request.sendall(chunked_response(body))
            log("HTTP generic -> OK")


class HTTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ============================================================
# TCP :20008
# ============================================================

def recv_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("connection closed")
        data.extend(chunk)
    return bytes(data)


def build_packet(magic4, payload_bytes, seq, middle4=b"\x01\x00\x00\x00",
                 flag4=b"\x00\x00\x00\x00"):
    total_len = 20 + len(payload_bytes)
    return (
        struct.pack("<I", total_len)
        + magic4
        + middle4
        + struct.pack("<I", seq)
        + flag4
        + payload_bytes
    )


def json_payload(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"


def build_login_ack(seq):
    payload = {
        "msg": "login succeed",
        "result": 0,
        "version": "1.0",
        "time": datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
    }
    return build_packet(b"\x11\x00\xc8\x00", json_payload(payload), seq)


def build_normal_ack(seq):
    return build_packet(
        b"\x19\x00\xc8\x00",
        json_payload({"msg": "OK", "result": 0, "version": "1.0"}),
        seq,
        middle4=b"\x01\x00\x00\x00",
        flag4=b"\x01\x00\x00\x00",
    )


def build_keepalive_ack(seq):
    return build_packet(
        b"\x11\x01\xc8\x00",
        b"",
        seq,
        middle4=b"\x01\x00\x00\x00",
        flag4=b"\xe7\x03\x00\x00",
    )


def next_command_seq():
    global command_seq
    with command_seq_lock:
        value = command_seq
        command_seq += 1
        return value


def save_state():
    data = {
        "updated": stamp(),
        "connected": active_conn is not None,
        "robot": robot_info,
        "state": latest_state,
    }
    try:
        STATE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def handle_json(obj):
    if not isinstance(obj, dict):
        return

    try:
        with MESSAGES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": stamp(), "message": obj}, ensure_ascii=False) + "\n")
    except Exception:
        pass

    value = obj.get("value") or {}

    if "token" in value:
        robot_info["deviceId"] = value.get("deviceId")
        robot_info["authCode"] = value.get("authCode")
        robot_info["deviceIp"] = value.get("deviceIp")
        robot_info["devicePort"] = value.get("devicePort") or "8888"

        log("LOGIN: robot credentials learned from active session")
        save_state()

    note = value.get("noteCmd")

    if note == "102":
        latest_state.update({
            "workState": value.get("workState"),
            "workMode": value.get("workMode"),
            "battery": value.get("battery"),
            "fan": value.get("fan"),
            "error": value.get("error"),
            "direction": value.get("direction"),
            "brush": value.get("brush"),
        })
        log(
            "STATUS: "
            f"workState={value.get('workState')} "
            f"workMode={value.get('workMode')} "
            f"battery={value.get('battery')} "
            f"fan={value.get('fan')} "
            f"error={value.get('error')}"
        )
        save_state()

    if note == "101":
        latest_state.update({
            "clearArea": value.get("clearArea"),
            "clearTime": value.get("clearTime"),
            "clearSign": value.get("clearSign"),
            "clearModule": value.get("clearModule"),
        })

        map_data = value.get("map")
        track_data = value.get("track")

        if map_data:
            MAP_FILE.write_text(map_data, encoding="ascii")
        if track_data:
            TRACK_FILE.write_text(track_data, encoding="ascii")

        log(
            "MAP/TRACK: "
            f"clearTime={value.get('clearTime')} "
            f"clearArea={value.get('clearArea')} "
            f"map_chars={len(map_data) if isinstance(map_data, str) else 0} "
            f"track_chars={len(track_data) if isinstance(track_data, str) else 0}"
        )
        save_state()


def set_active(conn, addr):
    global active_conn, active_addr
    with active_lock:
        active_conn = conn
        active_addr = addr
    save_state()


def clear_active(conn):
    global active_conn, active_addr
    with active_lock:
        if active_conn is conn:
            active_conn = None
            active_addr = None
    save_state()


def build_control_command(transit_cmd, extra_value=None):
    if not robot_info["authCode"]:
        raise RuntimeError("Robot not logged in yet.")
    if not robot_info["deviceIp"]:
        raise RuntimeError("Robot IP unknown.")

    # Important: original RobotBona captures for commands such as 106 (mode)
    # and 110 (fan) place their extra parameter BEFORE "transitCmd". The
    # tested ESP8266-side parser is sensitive to this wire order.
    value_obj = {}
    if extra_value:
        for key, value in extra_value.items():
            value_obj[str(key)] = str(value)
    value_obj["transitCmd"] = str(transit_cmd)

    body_obj = {
        "cmd": 0,
        "control": {
            "authCode": str(robot_info["authCode"]),
            "deviceIp": str(robot_info["deviceIp"]),
            "devicePort": str(robot_info.get("devicePort") or "8888"),
            "targetId": str(command_target_id),
            "targetType": "3",
        },
        "seq": 0,
        "value": value_obj,
    }

    body = json_payload(body_obj)
    seq = next_command_seq()

    packet = build_packet(
        b"\xfa\x00\xc8\x00",
        body,
        seq,
        middle4=b"\x00\x00\x09\x01",
        flag4=b"\x00\x00\x00\x00",
    )

    return seq, packet


def send_control(transit_cmd, name, extra_value=None):
    with active_lock:
        conn = active_conn
        addr = active_addr

    if conn is None:
        log(f"CONTROL {name}: no active robot connection.")
        return

    try:
        seq, packet = build_control_command(transit_cmd, extra_value=extra_value)
        conn.sendall(packet)

        extras = ""
        if extra_value:
            extras = " " + " ".join(f"{k}={v}" for k, v in extra_value.items())

        log(
            f"TX CONTROL {name}: transitCmd={transit_cmd}{extras} "
            f"seq={seq} targetId={command_target_id} "
            f"to {addr[0]}:{addr[1]}"
        )
        if extra_value:
            ordered_value = {}
            for key, value in extra_value.items():
                ordered_value[str(key)] = str(value)
            ordered_value["transitCmd"] = str(transit_cmd)
            log("TX CONTROL VALUE: " + json.dumps(
                ordered_value, separators=(",", ":")
            ))
    except Exception as e:
        log(f"CONTROL {name} ERROR: {type(e).__name__}: {e}")


def handle_tcp_client(conn, addr):
    log(f"ROBOT CONNECTED from {addr[0]}:{addr[1]}")
    conn.settimeout(90)

    try:
        while True:
            header = recv_exact(conn, 20)

            total_len = struct.unpack("<I", header[0:4])[0]
            magic = header[4:8]
            seq = struct.unpack("<I", header[12:16])[0]

            if total_len < 20 or total_len > 1024 * 1024:
                raise ValueError(f"invalid packet length {total_len}")

            payload_raw = recv_exact(conn, total_len - 20) if total_len > 20 else b""

            obj = None
            if payload_raw:
                text = payload_raw.decode("utf-8", errors="replace").rstrip("\x00\r\n")
                try:
                    obj = json.loads(text)
                    handle_json(obj)
                except json.JSONDecodeError:
                    log(f"RX non-JSON payload: {text}")
            else:
                log(f"RX keepalive seq={seq}")

            value = obj.get("value") if isinstance(obj, dict) else None

            if isinstance(value, dict) and "token" in value:
                conn.sendall(build_login_ack(seq))
                set_active(conn, addr)
                log(f"TX LOGIN ACK seq={seq}: login succeed")
                log("CONTROL READY: start / stop / home / map / info")

            elif magic == b"\xfa\x00\x00\x00":
                log(f"CONTROL RESPONSE received for seq={seq}")

            elif total_len == 20:
                conn.sendall(build_keepalive_ack(seq))

            else:
                conn.sendall(build_normal_ack(seq))

    except (ConnectionError, ConnectionResetError, BrokenPipeError) as e:
        log(f"ROBOT DISCONNECTED: {e}")
    except socket.timeout:
        log("ROBOT CONNECTION TIMEOUT")
    except Exception as e:
        log(f"TCP ERROR: {type(e).__name__}: {e}")
    finally:
        clear_active(conn)
        try:
            conn.close()
        except Exception:
            pass
        log(f"CONNECTION CLOSED for {addr[0]}:{addr[1]}")


def tcp_server_loop():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((TCP_HOST, TCP_PORT))
        server.listen(5)

        log(f"TCP server listening on {TCP_HOST}:{TCP_PORT}")

        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_tcp_client,
                args=(conn, addr),
                daemon=True,
            ).start()


# ============================================================
# Console
# ============================================================

def console_loop():
    mode_names = {
        "auto": "11",
        "spiral": "1",
        "turn": "1",
        "random": "3",
        "edge": "4",
        "border": "4",
        "area": "6",
        "deep": "8",
        "scrub": "10",
        "scrubbing": "10",
    }

    fan_names = {
        "off": "1",
        "normal": "2",
        "turbo": "3",
        "eco": "4",
    }

    print()
    print("Commands:")
    print("  start                 - start cleaning")
    print("  stop                  - stop/pause")
    print("  home                  - return to dock")
    print("  map                   - request map/status")
    print("  voice on              - enable robot sounds")
    print("  voice off             - disable robot sounds")
    print("")
    print("  mode auto             - mode=11")
    print("  mode spiral           - mode=1")
    print("  mode random           - mode=3")
    print("  mode edge             - mode=4")
    print("  mode area             - mode=6")
    print("  mode deep             - mode=8")
    print("  mode scrub            - mode=10")
    print("  mode <1|3|4|6|8|10|11>")
    print("")
    print("  fan off               - fan=1")
    print("  fan normal            - fan=2")
    print("  fan turbo             - fan=3")
    print("  fan eco               - fan=4")
    print("  fan <1|2|3|4>")
    print("")
    print("  time now <0|1|2>      - set robot clock to current local PC time")
    print("  time YYYYMMDDhhmm <0|1|2>")
    print("                         - sends set_time=YYYYMMDDhhmm000x")
    print("                           NOTE: meaning of final x is not fully known")
    print("")
    print("  info                  - show last known state")
    print()

    while True:
        try:
            cmd = input().strip().lower()
        except EOFError:
            return

        if not cmd:
            continue

        parts = cmd.split()

        if cmd == "start":
            send_control("100", "START")

        elif cmd == "stop":
            send_control("102", "STOP")

        elif cmd in ("home", "dock"):
            send_control("104", "HOME")

        elif cmd == "map":
            send_control("131", "MAP")

        elif cmd == "voice on":
            send_control("123", "VOICE ON")

        elif cmd == "voice off":
            send_control("125", "VOICE OFF")

        elif parts[0] == "mode":
            if len(parts) != 2:
                print("Usage: mode auto|spiral|random|edge|area|deep|scrub|1|3|4|6|8|10|11")
                continue

            value = mode_names.get(parts[1], parts[1])

            if value not in {"1", "3", "4", "6", "8", "10", "11"}:
                print("Invalid mode. Allowed: 1,3,4,6,8,10,11")
                continue

            name = next(
                (k.upper() for k, v in mode_names.items()
                 if v == value and k not in {"turn", "border", "scrubbing"}),
                value
            )
            send_control("106", f"MODE {name}", {"mode": value})

        elif parts[0] == "fan":
            if len(parts) != 2:
                print("Usage: fan off|normal|turbo|eco|1|2|3|4")
                continue

            value = fan_names.get(parts[1], parts[1])

            if value not in {"1", "2", "3", "4"}:
                print("Invalid fan value. Allowed: 1,2,3,4")
                continue

            name = next((k.upper() for k, v in fan_names.items() if v == value), value)
            send_control("110", f"FAN {name}", {"fan": value})

        elif parts[0] == "time":
            # Known reverse-engineered format:
            # set_time = YYYYMMDDhhmm000x
            # The final digit x has been observed as 0/1/2, but its exact
            # semantic meaning is still uncertain.
            if len(parts) == 3 and parts[1] == "now":
                suffix = parts[2]
                if suffix not in {"0", "1", "2"}:
                    print("Suffix must be 0, 1 or 2.")
                    continue

                dt = datetime.now()
                base = dt.strftime("%Y%m%d%H%M")
                set_time = base + "000" + suffix
                send_control("139", "SET TIME", {"set_time": set_time})
                print(f"Sent local PC time as set_time={set_time}")

            elif len(parts) == 3:
                base = parts[1]
                suffix = parts[2]

                if len(base) != 12 or not base.isdigit():
                    print("Time must be YYYYMMDDhhmm, e.g. 202608312030")
                    continue

                if suffix not in {"0", "1", "2"}:
                    print("Suffix must be 0, 1 or 2.")
                    continue

                try:
                    datetime.strptime(base, "%Y%m%d%H%M")
                except ValueError:
                    print("Invalid date/time.")
                    continue

                set_time = base + "000" + suffix
                send_control("139", "SET TIME", {"set_time": set_time})
                print(f"Sent set_time={set_time}")

            else:
                print("Usage:")
                print("  time now 0")
                print("  time YYYYMMDDhhmm 0")

        elif cmd == "info":
            print(json.dumps({
                "robot": robot_info,
                "state": latest_state,
                "connected": active_conn is not None,
            }, indent=2))

        else:
            print("Unknown command.")
            print("Use: start, stop, home, map, voice on/off, mode ..., fan ..., time ..., info")


def main():
    log("============================================================")
    log("Proscenic 790T FULLY LOCAL service v4")
    log(f"HTTP :{HTTP_PORT} + TCP :{TCP_PORT}")
    log(f"Local token configured: {len(LOCAL_TOKEN)} characters")
    log("NO RobotBona cloud required")
    log("============================================================")

    http_server = HTTPServer((HTTP_HOST, HTTP_PORT), HTTPHandler)

    threading.Thread(
        target=http_server.serve_forever,
        daemon=True,
    ).start()

    threading.Thread(
        target=tcp_server_loop,
        daemon=True,
    ).start()

    console_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
