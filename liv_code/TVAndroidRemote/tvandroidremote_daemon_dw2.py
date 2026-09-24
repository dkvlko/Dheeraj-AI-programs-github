#!/usr/bin/env python3
"""
Android TV Remote v2 daemon.

Replaces the former ADB control path with androidtvremote2.

Architecture:
    Flask/UI -> Unix socket -> this daemon -> Android TV Remote v2 -> Mi Box

The daemon:
- Discovers Android TV Remote v2 services using mDNS.
- Selects the configured Mi Box using its advertised Bluetooth MAC.
- Uses the persistent Remote v2 client certificate/key.
- Connects to TCP 6466; pairing is TCP 6467.
- Keeps the existing JSON-over-Unix-socket command interface.
- Retries connection establishment 5 times with 5-second delays.
- Lets androidtvremote2 handle normal reconnects after an established session.
- Re-discovers the TV every 30 minutes.
"""

import asyncio
import datetime
import json
import os
import socket
import threading
import time
from pathlib import Path

from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# This is the Bluetooth MAC advertised by the Mi Box's
# _androidtvremote2._tcp.local service.
# It is NOT the Wi-Fi/LAN MAC used by the old ADB daemon.
TV_BT_MAC = "ec:fa:5c:c0:f7:1c".lower()

TV_SERVICE_TYPE = "_androidtvremote2._tcp.local."

CHECK_INTERVAL = 30 * 60

# Refresh the Remote v2 session every CHECK_INTERVAL.  This is deliberate:
# androidtvremote2 can remain apparently connected while its outgoing command
# channel has become stale.  A fresh connection prevents a long-lived stale
# session from silently accepting commands without affecting the TV.
REFRESH_CONNECTION_EVERY_CHECK = True

CONNECTION_ATTEMPTS = 5
CONNECTION_RETRY_DELAY = 5

# The TV's IP address is normally stable, but DHCP can change it.
# Keep the last successfully connected address so startup can try the
# fastest path first.  The Bluetooth MAC remains the permanent identity.
LAST_IP_FILE = Path("/home/dkvlko/.config/tvandroidremote/last_ip")

# These are the certificates successfully created and paired during testing.
BASE_DIR = Path("/home/dkvlko/live_code/TVAndroidRemote")
CERT_FILE = BASE_DIR / "mibox4_remote_cert.pem"
KEY_FILE = BASE_DIR / "mibox4_remote_key.pem"

CLIENT_NAME = "Dheeraj Ubuntu TV Remote"

SOCKET_PATH = "/run/tvandroidremote/remote.sock"

# Discovery wait time for each attempt.
DISCOVERY_TIMEOUT = 5

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

TV_IP = None
TV_SERVICE_NAME = None
TV_BT_MAC_FOUND = None

remote = None

CONNECTED = False
IS_ON = None
CURRENT_APP = None
VOLUME_INFO = None

state_lock = threading.RLock()
remote_loop = None


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(message):
    """Log to stdout; systemd/journald will collect it."""
    timestamp = datetime.datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %z"
    )
    print(f"[{timestamp}] {message}", flush=True)


# ---------------------------------------------------------------------------
# Persistent IP address
# ---------------------------------------------------------------------------

def load_last_ip():
    """Return the last successfully connected TV IP, if one is saved."""
    try:
        ip = LAST_IP_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except Exception as exc:
        log(f"Could not read saved TV IP {LAST_IP_FILE}: {exc}")
        return None

    # Keep this deliberately simple: the value is written by this daemon.
    # A malformed value is ignored and normal mDNS discovery will be used.
    try:
        socket.inet_aton(ip)
    except OSError:
        log(f"Ignoring invalid saved TV IP: {ip!r}")
        return None

    return ip


def save_last_ip(ip):
    """Persist an IP only after a successful Remote v2 connection."""
    if not ip:
        return

    try:
        LAST_IP_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = LAST_IP_FILE.with_suffix(".tmp")
        tmp.write_text(f"{ip}\n", encoding="utf-8")
        os.replace(tmp, LAST_IP_FILE)
        os.chmod(LAST_IP_FILE, 0o600)
        log(f"Saved TV IP for next startup: {ip}")
    except Exception as exc:
        # A saved IP is an optimization, not a requirement.  Never make a
        # working remote daemon fail because the cache cannot be written.
        log(f"Could not save TV IP {ip}: {exc}")


# ---------------------------------------------------------------------------
# mDNS / Android TV Remote v2 discovery
# ---------------------------------------------------------------------------

async def discover_android_tv(timeout=DISCOVERY_TIMEOUT):
    """
    Discover Android TV Remote v2 services and return the target IPv4 address.

    The Android TV Remote v2 mDNS TXT property 'bt' contains the TV's
    Bluetooth MAC. We use that to identify the target Mi Box.
    """

    found = []
    zc = AsyncZeroconf()

    async def inspect_service(name):
        try:
            info = await zc.async_get_service_info(
                TV_SERVICE_TYPE,
                name,
                timeout=3000,
            )

            if info is None:
                return

            addresses = info.parsed_scoped_addresses()

            # zeroconf returns TXT properties as bytes.
            properties = {}
            for key, value in info.properties.items():
                key_text = (
                    key.decode("utf-8", errors="replace")
                    if isinstance(key, bytes)
                    else str(key)
                )
                value_text = (
                    value.decode("utf-8", errors="replace")
                    if isinstance(value, bytes)
                    else str(value)
                )
                properties[key_text.lower()] = value_text

            bt_mac = properties.get("bt", "").lower()

            ipv4_addresses = [
                address
                for address in addresses
                if "." in address
            ]

            found.append(
                {
                    "name": name,
                    "addresses": addresses,
                    "ipv4": ipv4_addresses,
                    "port": info.port,
                    "bt_mac": bt_mac,
                    "properties": properties,
                }
            )

        except Exception as exc:
            log(f"Error reading mDNS service {name}: {exc}")

    def state_change(
        zeroconf,
        service_type,
        name,
        state_change,
    ):
        if state_change is ServiceStateChange.Added:
            asyncio.create_task(inspect_service(name))

    browser = AsyncServiceBrowser(
        zc.zeroconf,
        [TV_SERVICE_TYPE],
        handlers=[state_change],
    )

    try:
        await asyncio.sleep(timeout)
    finally:
        await browser.async_cancel()
        await zc.async_close()

    # Prefer exact Bluetooth-MAC match.
    for item in found:
        if item["bt_mac"] == TV_BT_MAC:
            if item["ipv4"]:
                return item

    # No exact MAC match.
    return None


# ---------------------------------------------------------------------------
# Remote state callbacks
# ---------------------------------------------------------------------------

def on_available(is_available):
    global CONNECTED

    with state_lock:
        CONNECTED = bool(is_available)

    log(f"Android TV Remote v2 availability: {CONNECTED}")


def on_power_changed(is_on):
    global IS_ON

    with state_lock:
        IS_ON = is_on

    log(f"Android TV power state changed: {is_on}")


def on_current_app_changed(current_app):
    global CURRENT_APP

    with state_lock:
        CURRENT_APP = current_app

    log(f"Android TV current app changed: {current_app}")


def on_volume_changed(volume_info):
    global VOLUME_INFO

    with state_lock:
        VOLUME_INFO = volume_info

    log(f"Android TV volume changed: {volume_info}")


# ---------------------------------------------------------------------------
# Remote object management
# ---------------------------------------------------------------------------

def remove_callbacks(old_remote):
    """Remove callbacks from an old remote object when possible."""
    if old_remote is None:
        return

    callbacks = (
        (
            "remove_is_available_updated_callback",
            on_available,
        ),
        (
            "remove_is_on_updated_callback",
            on_power_changed,
        ),
        (
            "remove_current_app_updated_callback",
            on_current_app_changed,
        ),
        (
            "remove_volume_info_updated_callback",
            on_volume_changed,
        ),
    )

    for method_name, callback in callbacks:
        method = getattr(old_remote, method_name, None)
        if method is not None:
            try:
                method(callback)
            except Exception:
                pass


def add_callbacks(new_remote):
    new_remote.add_is_available_updated_callback(on_available)
    new_remote.add_is_on_updated_callback(on_power_changed)
    new_remote.add_current_app_updated_callback(on_current_app_changed)
    new_remote.add_volume_info_updated_callback(on_volume_changed)


async def disconnect_remote():
    global remote, CONNECTED

    if remote is not None:
        old_remote = remote
        remote = None

        remove_callbacks(old_remote)

        try:
            old_remote.disconnect()
        except Exception:
            pass

    with state_lock:
        CONNECTED = False


async def create_and_connect(host):
    """
    Create a new AndroidTVRemote object and connect it to host.

    Pairing is deliberately NOT attempted automatically. The daemon is
    non-interactive; the persistent certificate must already be paired.
    """

    global remote, CONNECTED, IS_ON, CURRENT_APP, VOLUME_INFO

    if not CERT_FILE.exists():
        raise RuntimeError(
            f"Remote certificate does not exist: {CERT_FILE}"
        )

    if not KEY_FILE.exists():
        raise RuntimeError(
            f"Remote private key does not exist: {KEY_FILE}"
        )

    await disconnect_remote()

    new_remote = AndroidTVRemote(
        CLIENT_NAME,
        str(CERT_FILE),
        str(KEY_FILE),
        host,
    )

    add_callbacks(new_remote)
    remote = new_remote

    await new_remote.async_connect()

    with state_lock:
        CONNECTED = True
        IS_ON = new_remote.is_on
        CURRENT_APP = new_remote.current_app
        VOLUME_INFO = new_remote.volume_info

    return new_remote


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

async def ensure_connection():
    """
    Establish the Remote v2 connection using a persistent-IP-first strategy.

    Lookup strategy:
      1. On the first attempt, try the last successfully connected IP.
      2. If that IP does not work, perform mDNS discovery.
      3. mDNS discovery examines all Android TV Remote v2 services and
         selects the device whose advertised Bluetooth MAC matches TV_BT_MAC.
      4. Save the newly discovered IP after a successful connection.
      5. Repeat the overall process up to CONNECTION_ATTEMPTS times.

    The Bluetooth MAC is the device identity; the IP address is only a
    cached connection hint.
    """

    global TV_IP, TV_SERVICE_NAME, TV_BT_MAC_FOUND, CONNECTED
    
    with state_lock:
        current_remote = remote
        current_connected = CONNECTED

    if current_remote is not None and current_connected:
        return True

    last_error = None
    saved_ip = load_last_ip()

    if saved_ip:
        log(f"Loaded saved TV IP: {saved_ip}")
    else:
        log(f"No saved TV IP found at {LAST_IP_FILE}; starting with mDNS discovery.")

    for attempt in range(1, CONNECTION_ATTEMPTS + 1):
        # Attempt 1 gets the fast path: try the saved address directly.
        # If it fails, discovery is performed immediately in the same
        # attempt.  Later attempts use fresh mDNS discovery.
        if attempt == 1 and saved_ip:
            try:
                log(
                    f"Connection attempt {attempt}: trying saved TV IP "
                    f"{saved_ip} first."
                )

                await create_and_connect(saved_ip)

                with state_lock:
                    TV_IP = saved_ip
                    TV_SERVICE_NAME = None
                    TV_BT_MAC_FOUND = TV_BT_MAC

                device_info = remote.device_info

                log(
                    f"Android TV Remote v2 connection established using "
                    f"saved IP on attempt {attempt}: {saved_ip}"
                )
                log(f"Device info: {device_info}")

                save_last_ip(saved_ip)
                return True

            except InvalidAuth:
                last_error = (
                    "Remote v2 authorization failed; the persistent certificate "
                    "is not currently authorized by the TV"
                )
                log(last_error)
                break

            except (CannotConnect, ConnectionClosed) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log(
                    f"Saved IP {saved_ip} could not be used: {last_error}. "
                    "Falling back to Bluetooth-MAC-based mDNS discovery."
                )

            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log(
                    f"Saved IP {saved_ip} could not be used: {last_error}. "
                    "Falling back to Bluetooth-MAC-based mDNS discovery."
                )

        # Discovery is authoritative.  It does not assume the cached IP
        # is still valid and searches all advertised Remote v2 devices.
        try:
            log(
                f"Connection attempt {attempt}: searching mDNS for Android "
                f"TV Remote v2 device with Bluetooth MAC {TV_BT_MAC}."
            )

            discovered = await discover_android_tv()

            if discovered is None:
                last_error = (
                    f"Android TV Remote v2 device with Bluetooth MAC "
                    f"{TV_BT_MAC} was not found"
                )
            else:
                ip = discovered["ipv4"][0]

                log(
                    f"Bluetooth-MAC match found on attempt {attempt}: "
                    f"{ip}"
                )
                log(
                    f"  Service: {discovered['name']}; "
                    f"Bluetooth MAC: {discovered['bt_mac']}; "
                    f"port: {discovered['port']}"
                )

                await create_and_connect(ip)

                with state_lock:
                    TV_IP = ip
                    TV_SERVICE_NAME = discovered["name"]
                    TV_BT_MAC_FOUND = discovered["bt_mac"]

                device_info = remote.device_info

                log(
                    f"Android TV Remote v2 connection established on "
                    f"attempt {attempt}: {ip}"
                )
                log(f"Device info: {device_info}")

                save_last_ip(ip)
                return True

        except InvalidAuth:
            last_error = (
                "Remote v2 authorization failed; the persistent certificate "
                "is not currently authorized by the TV"
            )
            log(last_error)
            break

        except (CannotConnect, ConnectionClosed) as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < CONNECTION_ATTEMPTS:
            log(
                f"Android TV Remote v2 connection attempt {attempt} failed: "
                f"{last_error}. Retrying in {CONNECTION_RETRY_DELAY} seconds."
            )
            await asyncio.sleep(CONNECTION_RETRY_DELAY)

    with state_lock:
        CONNECTED = False

    if last_error:
        log(f"Android TV Remote v2 connection failed: {last_error}")

    log("connection lost, probably TV is switched off.")
    return False


async def connection_monitor():
    """
    Periodically refresh the Remote v2 session and rediscover the TV.

    Every check:
      1. Discover the target by Bluetooth MAC.
      2. Detect a DHCP/IP change.
      3. Proactively recreate the Remote v2 connection.

    The proactive reconnect is intentional.  The Remote v2 session can remain
    apparently connected and continue delivering state callbacks while its
    outgoing command channel has become stale.  Recreating the session every
    30 minutes prevents that long-lived stale state.

    If discovery cannot find the TV, the existing connection is left alone
    rather than being destroyed unnecessarily.
    """

    global TV_IP, TV_SERVICE_NAME, TV_BT_MAC_FOUND

    while True:
        await asyncio.sleep(CHECK_INTERVAL)

        try:
            discovered = await discover_android_tv()

            if discovered is None:
                log(
                    "Periodic discovery: target TV not found; "
                    "keeping the current Remote v2 session unchanged."
                )
                continue

            discovered_ip = discovered["ipv4"][0]

            with state_lock:
                current_ip = TV_IP
                connected = CONNECTED

            if connected and current_ip == discovered_ip:
                log(
                    f"Periodic Remote v2 session refresh: "
                    f"recreating connection to {discovered_ip}."
                )
            elif current_ip != discovered_ip:
                log(
                    f"TV IP changed from {current_ip} to {discovered_ip}; "
                    "recreating Remote v2 connection."
                )
            else:
                log(
                    f"Periodic Remote v2 recovery: "
                    f"reconnecting to {discovered_ip}."
                )

            await create_and_connect(discovered_ip)

            with state_lock:
                TV_IP = discovered_ip
                TV_SERVICE_NAME = discovered["name"]
                TV_BT_MAC_FOUND = discovered["bt_mac"]

            save_last_ip(discovered_ip)

            log(
                f"Periodic Remote v2 connection refresh successful: "
                f"{discovered_ip}"
            )

        except InvalidAuth as exc:
            log(f"Periodic Remote v2 authorization failure: {exc}")

        except (CannotConnect, ConnectionClosed) as exc:
            log(
                f"Periodic Remote v2 refresh connection failed: "
                f"{type(exc).__name__}: {exc}"
            )

            # Let the normal five-attempt persistent-IP-first /
            # Bluetooth-MAC mDNS fallback strategy recover the session.
            try:
                await disconnect_remote()
                if await ensure_connection():
                    log("Periodic Remote v2 recovery successful.")
                else:
                    log("Periodic Remote v2 recovery failed.")
            except Exception as recovery_exc:
                log(
                    f"Periodic Remote v2 recovery raised "
                    f"{type(recovery_exc).__name__}: {recovery_exc}"
                )

        except Exception as exc:
            log(
                f"Periodic Remote v2 connection refresh failed: "
                f"{type(exc).__name__}: {exc}"
            )

            # A stale connection can surface as a library-specific exception,
            # so also use the standard recovery path for unexpected failures.
            try:
                await disconnect_remote()
                if await ensure_connection():
                    log("Periodic Remote v2 recovery successful.")
                else:
                    log("Periodic Remote v2 recovery failed.")
            except Exception as recovery_exc:
                log(
                    f"Periodic Remote v2 recovery raised "
                    f"{type(recovery_exc).__name__}: {recovery_exc}"
                )


# ---------------------------------------------------------------------------
# Remote command execution
# ---------------------------------------------------------------------------

def require_remote():
    with state_lock:
        current_remote = remote
        connected = CONNECTED

    if current_remote is None or not connected:
        return None

    return current_remote


async def send_key(command):
    """
    Send a normal short key press using Android TV Remote v2.
    """

    key_map = {
        "up": "KEYCODE_DPAD_UP",
        "down": "KEYCODE_DPAD_DOWN",
        "left": "KEYCODE_DPAD_LEFT",
        "right": "KEYCODE_DPAD_RIGHT",
        "select": "KEYCODE_DPAD_CENTER",
        "back": "KEYCODE_BACK",
        "home": "KEYCODE_HOME",
        "power": "KEYCODE_POWER",
        "vol_up": "KEYCODE_VOLUME_UP",
        "vol_down": "KEYCODE_VOLUME_DOWN",
        "mute": "KEYCODE_VOLUME_MUTE",
    }

    key_code = key_map.get(command)

    if key_code is None:
        return False, f"Unknown key command: {command}"

    tv = require_remote()

    if tv is None:
        return False, "TV is not connected."

    try:
        tv.send_key_command(key_code)
        return True, ""
    except ConnectionClosed as exc:
        log(
            f"Remote v2 key command detected a closed connection: {exc}. "
            "Attempting immediate recovery."
        )

        try:
            await disconnect_remote()

            if await ensure_connection():
                tv = require_remote()

                if tv is not None:
                    tv.send_key_command(key_code)
                    log(
                        f"Remote v2 key command '{command}' succeeded "
                        "after reconnection."
                    )
                    return True, ""

        except Exception as recovery_exc:
            log(
                f"Remote v2 immediate command recovery failed: "
                f"{type(recovery_exc).__name__}: {recovery_exc}"
            )

        return False, f"Remote connection closed: {exc}"

    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


async def send_text(text):
    tv = require_remote()

    if tv is None:
        return False, "TV is not connected."

    try:
        tv.send_text(text)
        return True, ""
    except ConnectionClosed as exc:
        return False, f"Remote connection closed: {exc}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


async def launch_app(package_or_link):
    tv = require_remote()

    if tv is None:
        return False, "TV is not connected."

    try:
        tv.send_launch_app_command(package_or_link)
        return True, ""
    except ConnectionClosed as exc:
        return False, f"Remote connection closed: {exc}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# JSON command interface
# ---------------------------------------------------------------------------

KEY_COMMANDS = {
    "up",
    "down",
    "left",
    "right",
    "select",
    "back",
    "home",
    "power",
    "vol_up",
    "vol_down",
    "mute",
}


async def execute_command_async(request):
    command = request.get("command")

    if command == "status":
        with state_lock:
            return {
                "ok": CONNECTED,
                "connected": CONNECTED,
                "tv_ip": TV_IP,
                "protocol": "androidtvremote2",
                "tv_service": TV_SERVICE_NAME,
                "tv_bt_mac": TV_BT_MAC_FOUND,
                "device_info": (
                    remote.device_info
                    if remote is not None
                    else None
                ),
                "power": IS_ON,
                "current_app": CURRENT_APP,
                "volume": VOLUME_INFO,
            }

    if command in KEY_COMMANDS:
        ok, output = await send_key(command)
        return {
            "ok": ok,
            "output": output,
        }

    if command == "type_text":
        text = str(request.get("text", ""))

        if not text:
            return {
                "ok": False,
                "error": "text is empty",
            }

        ok, output = await send_text(text)

        return {
            "ok": ok,
            "output": output,
        }

    if command == "youtube":
        ok, output = await launch_app("com.google.android.youtube.tv")

        return {
            "ok": ok,
            "output": output,
        }

    if command == "netflix":
        ok, output = await launch_app("com.netflix.ninja")

        return {
            "ok": ok,
            "output": output,
        }

    if command == "launch_app":
        package_or_link = str(request.get("package", "")).strip()

        if not package_or_link:
            return {
                "ok": False,
                "error": "package is empty",
            }

        ok, output = await launch_app(package_or_link)

        return {
            "ok": ok,
            "output": output,
        }

    if command == "screenshot":
        return {
            "ok": False,
            "error": (
                "Screenshot is not supported by Android TV Remote v2. "
                "It was previously provided by ADB."
            ),
        }

    return {
        "ok": False,
        "error": f"Unknown command: {command}",
    }


def execute_command(request):
    """
    Run a command on the dedicated Remote v2 asyncio event loop.
    """

    if remote_loop is None:
        return {
            "ok": False,
            "error": "Remote event loop is not running.",
        }

    future = asyncio.run_coroutine_threadsafe(
        execute_command_async(request),
        remote_loop,
    )

    try:
        return future.result(timeout=15)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


# ---------------------------------------------------------------------------
# Unix socket server
# ---------------------------------------------------------------------------

def client_thread(conn):
    try:
        data = conn.recv(65536)

        if not data:
            return

        request = json.loads(data.decode("utf-8"))
        response = execute_command(request)

        conn.sendall(
            (
                json.dumps(response, separators=(",", ":")) + "\n"
            ).encode("utf-8")
        )

    except Exception as exc:
        response = {
            "ok": False,
            "error": str(exc),
        }

        try:
            conn.sendall(
                (
                    json.dumps(response, separators=(",", ":")) + "\n"
                ).encode("utf-8")
            )
        except Exception:
            pass

    finally:
        conn.close()


def socket_server():
    path = Path(SOCKET_PATH)

    # RuntimeDirectory=tvandroidremote creates this under systemd.
    # The mkdir also permits manual execution when the user has already
    # created/owned the directory.
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


# ---------------------------------------------------------------------------
# Asyncio event-loop thread
# ---------------------------------------------------------------------------

async def remote_main():
    log("Android TV Remote v2 daemon starting.")

    if not CERT_FILE.exists():
        log(f"ERROR: certificate not found: {CERT_FILE}")

    if not KEY_FILE.exists():
        log(f"ERROR: private key not found: {KEY_FILE}")

    connected = await ensure_connection()

    if not connected:
        log(
            f"Initial connection failed. "
            f"Will retry every {CHECK_INTERVAL // 60} minutes."
        )

    asyncio.create_task(connection_monitor())

    # Keep this asyncio loop alive.
    await asyncio.Event().wait()


def start_remote_loop():
    global remote_loop

    remote_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(remote_loop)

    try:
        remote_loop.run_until_complete(remote_main())
    finally:
        remote_loop.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    remote_thread = threading.Thread(
        target=start_remote_loop,
        daemon=True,
        name="androidtvremote2-loop",
    )
    remote_thread.start()

    # Wait until the asyncio loop has been created before accepting commands.
    while remote_loop is None:
        time.sleep(0.05)

    socket_server()


if __name__ == "__main__":
    main()
