#!/usr/bin/env python3
"""
Android TV Remote daemon.

- Discovers the TV dynamically using its MAC address.
- Uses native Linux tools (ip, adb, optionally nmap); no Scapy.
- Maintains an ADB connection.
- Checks/reconnects every 30 minutes.
- Exposes a small JSON-over-Unix-socket command interface.
"""

import datetime
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

TV_MAC = "ec:fa:5c:bf:70:7c".lower()

CHECK_INTERVAL = 30 * 60
SOCKET_PATH = "/run/tvandroidremote/remote.sock"

TV_IP = None
ADB_DEVICE = None
state_lock = threading.RLock()


def log(message):
    """Log to stdout; systemd/journald will collect it."""
    timestamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    print(f"[{timestamp}] {message}", flush=True)


def run(cmd, timeout=30):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def get_network_info():
    """Return (CIDR, interface) for a non-container connected IPv4 LAN."""
    result = run(["ip", "-4", "route", "show", "scope", "link"])

    routes = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if not parts or "/" not in parts[0] or "dev" not in parts:
            continue
        try:
            interface = parts[parts.index("dev") + 1]
        except (ValueError, IndexError):
            continue
        routes.append((parts[0], interface))

    preferred = [
        item for item in routes
        if not item[1].startswith(("docker", "br-", "virbr", "veth"))
    ]

    return (preferred or routes or [(None, None)])[0]


def get_adb_devices():
    result = run(["adb", "devices"])
    devices = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))

    return devices


def adb_is_usable():
    """Verify that the selected ADB device is really responding."""
    global ADB_DEVICE

    if not ADB_DEVICE:
        return False

    devices = dict(get_adb_devices())
    if devices.get(ADB_DEVICE) != "device":
        return False

    result = run(
        ["adb", "-s", ADB_DEVICE, "shell", "echo", "TVREMOTE_OK"],
        timeout=10,
    )
    return result.returncode == 0 and "TVREMOTE_OK" in result.stdout


def find_tv_from_neighbours():
    """Find TV IP using the Linux neighbour table."""
    _, interface = get_network_info()
    if not interface:
        return None

    result = run(["ip", "neigh", "show", "dev", interface])

    pattern = re.compile(
        r"^(\d+\.\d+\.\d+\.\d+)\s+.*?\blladdr\s+([0-9a-fA-F:]{17})\b"
    )

    for line in result.stdout.splitlines():
        match = pattern.match(line.strip())
        if match and match.group(2).lower() == TV_MAC:
            return match.group(1)

    return None


def find_tv_with_nmap():
    """Fallback: find a host with TCP/5555 open on the connected LAN."""
    nmap = shutil.which("nmap")
    if not nmap:
        return None

    cidr, _ = get_network_info()
    if not cidr:
        return None

    result = run(
        [nmap, "-n", "-p", "5555", "--open", cidr],
        timeout=120,
    )

    current_ip = None
    candidates = []

    for line in result.stdout.splitlines():
        match = re.match(
            r"^Nmap scan report for (\d+\.\d+\.\d+\.\d+)$",
            line.strip(),
        )
        if match:
            current_ip = match.group(1)
        elif current_ip and "5555/tcp" in line and "open" in line:
            candidates.append(current_ip)
            current_ip = None

    # Prefer a candidate that can actually become an ADB device.
    for ip in candidates:
        result = run(["adb", "connect", f"{ip}:5555"], timeout=10)
        if result.returncode == 0:
            for serial, state in get_adb_devices():
                if serial == f"{ip}:5555" and state == "device":
                    return ip

    return None


def discover_tv():
    global TV_IP

    ip = find_tv_from_neighbours()
    if ip:
        TV_IP = ip
        log(f"TV discovered from Linux neighbour table: {TV_IP}")
        return True

    log("TV not in Linux neighbour table; trying nmap fallback.")

    ip = find_tv_with_nmap()
    if ip:
        TV_IP = ip
        log(f"TV discovered by ADB port scan: {TV_IP}")
        return True

    return False


def connect_or_reuse():
    """Reuse an existing ADB connection or connect to the discovered TV."""
    global ADB_DEVICE

    subprocess.run(["adb", "start-server"], check=False)

    # First: use an existing connection matching the discovered IP.
    if TV_IP:
        for serial, state in get_adb_devices():
            if (
                state == "device"
                and (
                    serial == TV_IP
                    or serial == f"{TV_IP}:5555"
                    or serial.startswith(TV_IP + ":")
                )
            ):
                ADB_DEVICE = serial
                if adb_is_usable():
                    log(f"Using existing ADB connection: {ADB_DEVICE}")
                    return True

    if not TV_IP:
        return False

    log(f"Attempting ADB connection to {TV_IP}:5555")

    result = run(["adb", "connect", f"{TV_IP}:5555"], timeout=10)
    message = (result.stdout.strip() or result.stderr.strip())
    if message:
        log(f"adb: {message}")

    for serial, state in get_adb_devices():
        if (
            state == "device"
            and (
                serial == TV_IP
                or serial == f"{TV_IP}:5555"
                or serial.startswith(TV_IP + ":")
            )
        ):
            ADB_DEVICE = serial
            if adb_is_usable():
                log(f"ADB connection established: {ADB_DEVICE}")
                return True

    ADB_DEVICE = None
    return False


def ensure_connection():
    """Discover/reconnect the TV. Returns True if usable."""
    global TV_IP, ADB_DEVICE

    with state_lock:
        if adb_is_usable():
            return True

        ADB_DEVICE = None

        if not discover_tv():
            log("connection lost, probably TV is switched off.")
            return False

        if not connect_or_reuse():
            log("connection lost, probably TV is switched off.")
            return False

        return True


def adb_command(args, timeout=30):
    """Run an ADB command against the currently connected TV."""
    with state_lock:
        if not adb_is_usable():
            return False, "TV is not connected."

        result = run(
            ["adb", "-s", ADB_DEVICE, *args],
            timeout=timeout,
        )

        if result.returncode != 0:
            # Mark connection unavailable; the monitor will retry.
            return False, (result.stderr.strip() or result.stdout.strip() or "ADB command failed.")

        return True, result.stdout.strip()


COMMANDS = {
    "up": ["shell", "input", "keyevent", "19"],
    "down": ["shell", "input", "keyevent", "20"],
    "left": ["shell", "input", "keyevent", "21"],
    "right": ["shell", "input", "keyevent", "22"],
    "select": ["shell", "input", "keyevent", "66"],
    "back": ["shell", "input", "keyevent", "4"],
    "home": ["shell", "input", "keyevent", "3"],
    "power": ["shell", "input", "keyevent", "26"],
    "vol_up": ["shell", "input", "keyevent", "24"],
    "vol_down": ["shell", "input", "keyevent", "25"],
    "mute": ["shell", "input", "keyevent", "164"],
    "youtube": [
        "shell", "am", "start",
        "-n", "com.google.android.youtube.tv/.MainActivity"
    ],
    "netflix": [
        "shell", "am", "start",
        "-n", "com.netflix.ninja/.MainActivity"
    ],
}


def execute_command(request):
    """
    Request format:
      {"command": "up"}
      {"command": "youtube"}
      {"command": "type_text", "text": "hello world"}
      {"command": "screenshot"}
      {"command": "status"}
    """
    command = request.get("command")

    if command == "status":
        connected = adb_is_usable()
        return {
            "ok": connected,
            "connected": connected,
            "tv_ip": TV_IP,
            "adb_device": ADB_DEVICE,
        }

    if command == "type_text":
        text = str(request.get("text", ""))
        if not text:
            return {"ok": False, "error": "text is empty"}

        # Android's input text command uses %s for spaces.
        text = text.replace(" ", "%s")
        ok, output = adb_command(["shell", "input", "text", text])
        return {"ok": ok, "output": output}

    if command == "screenshot":
        filename = request.get("filename")
        if not filename:
            filename = f"tvshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        remote = "/sdcard/tvremote_screen.png"

        ok, output = adb_command(["shell", "screencap", "-p", remote])
        if not ok:
            return {"ok": False, "error": output}

        result = run(["adb", "-s", ADB_DEVICE, "pull", remote, filename], timeout=60)
        if result.returncode != 0:
            return {
                "ok": False,
                "error": result.stderr.strip() or result.stdout.strip(),
            }

        return {"ok": True, "filename": filename}

    if command in COMMANDS:
        ok, output = adb_command(COMMANDS[command])
        return {"ok": ok, "output": output}

    return {
        "ok": False,
        "error": f"Unknown command: {command}",
    }


def client_thread(conn):
    try:
        data = conn.recv(65536)
        if not data:
            return

        request = json.loads(data.decode("utf-8"))
        response = execute_command(request)

        conn.sendall(
            (json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8")
        )
    except Exception as exc:
        response = {"ok": False, "error": str(exc)}
        try:
            conn.sendall(
                (json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8")
            )
        except Exception:
            pass
    finally:
        conn.close()


def socket_server():
    path = Path(SOCKET_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        path.unlink()
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o660)
    server.listen(16)

    log(f"Command socket listening on {SOCKET_PATH}")

    while True:
        conn, _ = server.accept()
        threading.Thread(
            target=client_thread,
            args=(conn,),
            daemon=True,
        ).start()


def connection_monitor():
    while True:
        time.sleep(CHECK_INTERVAL)

        if not ensure_connection():
            log("connection lost, probably TV is switched off.")


def main():
    log("Android TV Remote daemon starting.")

    # Initial connection attempt.
    if not ensure_connection():
        log("connection lost, probably TV is switched off.")
        log("Will retry connection in 30 minutes.")

    threading.Thread(
        target=connection_monitor,
        daemon=True,
        name="connection-monitor",
    ).start()

    socket_server()


if __name__ == "__main__":
    main()
