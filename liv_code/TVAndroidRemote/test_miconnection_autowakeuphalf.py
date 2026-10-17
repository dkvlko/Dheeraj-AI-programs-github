#!/usr/bin/env python3

import asyncio
from pathlib import Path

from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
)

from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(
    "/home/dkvlko/live_code/TVAndroidRemote"
)

CERT_FILE = BASE_DIR / "mibox4_remote_cert.pem"
KEY_FILE = BASE_DIR / "mibox4_remote_key.pem"

# The Mi Box we want to test.
# This is used only to identify the TV.
# NO IP address is hard-coded.
TARGET_MAC = "ec:fa:5c:c0:f7:1c"

# Android TV Remote v2 mDNS service.
SERVICE_TYPE = "_androidtvremote2._tcp.local."

# How long to listen for mDNS advertisements.
DISCOVERY_TIME = 5

# How long to wait before testing the existing
# Remote v2 connection.
WAIT_TIME = 5
HOME_CONNECTION_TIMEOUT = 2 * 60
# Name shown to Android TV during pairing.
CLIENT_NAME = "MiBox Connection Monitor"


# ============================================================
# mDNS service collector
# ============================================================

class ServiceCollector:

    def __init__(self):
        self.service_names = set()

    def service_state_change(
        self,
        zeroconf,
        service_type,
        name,
        state_change,
    ):
        """
        Called by Zeroconf when an Android TV Remote v2
        service appears, disappears or changes.
        """

        if state_change in (
            ServiceStateChange.Added,
            ServiceStateChange.Updated,
        ):
            self.service_names.add(name)

            print(
                f"mDNS service discovered: {name}"
            )


# ============================================================
# Discover Android TV Remote v2 services
# ============================================================

async def discover_services():

    collector = ServiceCollector()

    azc = AsyncZeroconf()

    browser = None

    try:

        print("==============================================")
        print(" Android TV Remote v2 mDNS Discovery")
        print("==============================================")
        print(
            f"Searching for: {SERVICE_TYPE}"
        )
        print(
            f"Listening for {DISCOVERY_TIME} seconds..."
        )
        print()

        browser = AsyncServiceBrowser(
            azc.zeroconf,
            SERVICE_TYPE,
            handlers=[
                collector.service_state_change
            ],
        )

        await asyncio.sleep(DISCOVERY_TIME)

        return list(collector.service_names)

    finally:

        if browser is not None:

            try:
                await browser.async_cancel()
            except Exception:
                pass

        await azc.async_close()


# ============================================================
# Get IP address from an mDNS service
# ============================================================

async def get_service_addresses(
    azc,
    service_name,
):

    info = AsyncServiceInfo(
        SERVICE_TYPE,
        service_name,
    )

    success = await info.async_request(
        azc,
        3000,
    )

    if not success:
        return []

    return info.parsed_scoped_addresses()


# ============================================================
# Identify a TV using its Remote-v2 certificate
# ============================================================

async def identify_tv(
    host,
):
    """
    Connect to Remote v2 pairing port 6467 and let
    androidtvremote2 extract the Android TV's name
    and MAC from the TV's certificate.

    No pairing is performed here.
    """

    remote = AndroidTVRemote(
        CLIENT_NAME,
        str(CERT_FILE),
        str(KEY_FILE),
        host,
        enable_ime=False,
        enable_voice=False,
    )

    try:

        name, mac = await remote.async_get_name_and_mac()

        return name, mac

    except Exception as exc:

        print(
            f"  Could not identify {host}: {exc}"
        )

        return None, None

    finally:

        remote.disconnect()


# ============================================================
# Discover the target TV
# ============================================================

async def find_target_tv():

    service_names = await discover_services()

    if not service_names:

        print()
        print(
            "No Android TV Remote v2 services "
            "were discovered."
        )

        return None

    print()
    print("==============================================")
    print(" Identifying discovered Android TVs")
    print("==============================================")
    print()

    # A separate Zeroconf instance is used here because
    # the discovery browser above has already been closed.

    azc = AsyncZeroconf()

    try:

        for service_name in service_names:

            info = AsyncServiceInfo(
                SERVICE_TYPE,
                service_name,
            )

            success = await info.async_request(
                azc.zeroconf,
                3000,
            )

            if not success:

                print(
                    f"Could not obtain information for:"
                    f" {service_name}"
                )

                continue

            addresses = info.parsed_scoped_addresses()

            if not addresses:

                print(
                    f"No IP address for: {service_name}"
                )

                continue

            print(
                f"Service: {service_name}"
            )

            print(
                f"Addresses: {addresses}"
            )

            # ------------------------------------------------
            # Try each advertised IPv4 address.
            # ------------------------------------------------

            for address in addresses:

                # Skip IPv6 for this test.
                if ":" in address:
                    continue

                print(
                    f"  Checking Remote v2 device at "
                    f"{address}..."
                )

                name, mac = await identify_tv(
                    address
                )

                if mac is None:
                    continue

                normalized_mac = mac.lower()

                print(
                    f"  Device name: {name}"
                )

                print(
                    f"  Device MAC : {normalized_mac}"
                )

                # ------------------------------------------------
                # Compare with our target Mi Box.
                # ------------------------------------------------

                if normalized_mac == TARGET_MAC.lower():

                    print()
                    print(
                        "=============================================="
                    )
                    print(
                        " TARGET ANDROID TV FOUND"
                    )
                    print(
                        "=============================================="
                    )
                    print(
                        f"Name : {name}"
                    )
                    print(
                        f"MAC  : {normalized_mac}"
                    )
                    print(
                        f"IP   : {address}"
                    )
                    print()

                    return address

                print(
                    "  MAC does not match target."
                )

                print()

        return None

    finally:

        await azc.async_close()



# ============================================================
# Command / connection control
# ============================================================

# tconn describes how the current Remote v2 handle is being used.
#
#   fresh  = initial mDNS discovery + one Remote v2 object
#   wakeup = use the SAME Remote v2 object after standby and wait
#            for androidtvremote2.keep_reconnecting() to restore it.
#
# After standby, this program does NOT perform mDNS rediscovery and
# does NOT create a replacement AndroidTVRemote object.

tconn = "fresh"

# Current command being executed.
command = None

# Device state.
device_in_standby = False

# How long to wait after every command.
COMMAND_WAIT = 5

# How long to wait in standby before issuing the official WAKEUP key.
STANDBY_WAIT = 5 * 60

# After WAKEUP is sent, wait this long for the SAME Remote v2
# connection handle to become usable again.
WAKE_REQUEST_TIMEOUT = 2 * 60


# ------------------------------------------------------------
# Practical commands documented by androidtvremote2/TvKeys.txt.
#
# The full RemoteKeyCode enum contains many Android/system/CEC/
# gamepad/app-specific values which are not necessarily useful on
# an Android TV remote. These are the common TV remote functions.
# ------------------------------------------------------------

KEY_COMMANDS = [
    ("Up", "DPAD_UP"),
    ("Down", "DPAD_DOWN"),
    ("Left", "DPAD_LEFT"),
    ("Right", "DPAD_RIGHT"),
    ("Center", "DPAD_CENTER"),


    ("VolumeDown", "VOLUME_DOWN"),
    ("VolumeUp", "VOLUME_UP"),

    ("Home", "HOME"),
    ("Back", "BACK"),


    ("Enter", "ENTER"),
]


# ------------------------------------------------------------
# App launch commands.
#
# androidtvremote2 supports app IDs as well as URLs/deep links.
# The library converts a bare package ID to:
#
#     market://launch?id=<package>
#
# We retain the package IDs here because that is the documented
# androidtvremote2 package-launch path. The URL/deep-link field is
# retained as diagnostic fallback information, not automatically
# sent after a device error.
# ------------------------------------------------------------

APP_COMMANDS = [
    {
        "name": "YouTube",
        "package": "com.google.android.youtube.tv",
        "deep_link": "https://www.youtube.com/",
    },
    {
        "name": "Netflix",
        "package": "com.netflix.ninja",
        "deep_link": "https://www.netflix.com/",
    },
    {
        "name": "PrimeVideo",
        "package": "com.amazon.amazonvideo.livingroom",
        "deep_link": "https://app.primevideo.com/",
    },
]


def timestamp() -> str:
    """Return a compact local timestamp for terminal output."""
    from datetime import datetime

    return datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %z"
    )


def status_print(message: str) -> None:
    """Print a timestamped status message."""
    print(f"[{timestamp()}] {message}", flush=True)


def connection_is_alive(remote) -> bool:
    """
    Check the current Remote v2 transport without sending a command.

    These are private androidtvremote2 0.3.2 internals. Keeping this
    check in one function makes the rest of the program independent
    of those implementation details.
    """

    if remote is None:
        return False

    protocol = getattr(
        remote,
        "_remote_message_protocol",
        None,
    )

    if protocol is None:
        return False

    transport = getattr(
        remote,
        "_transport",
        None,
    )

    if transport is None:
        return False

    try:
        if transport.is_closing():
            return False
    except Exception:
        return False

    on_con_lost = getattr(
        protocol,
        "on_con_lost",
        None,
    )

    if on_con_lost is not None:
        try:
            if on_con_lost.done():
                return False
        except Exception:
            return False

    return True


def connection_status_changed(is_available: bool) -> None:
    """Diagnostic availability callback from androidtvremote2.

    This callback only observes availability. It does not create a new
    Remote object, perform mDNS discovery, or call async_connect().
    The existing keep_reconnecting() mechanism owns recovery.
    """
    if is_available:
        status_print(
            "Remote availability callback: AVAILABLE - "
            "androidtvremote2 reports the Remote v2 connection is usable"
        )
    else:
        status_print(
            "Remote availability callback: UNAVAILABLE - "
            "androidtvremote2 reports the Remote v2 connection is lost; "
            "keep_reconnecting() remains responsible for recovery"
        )


def attach_and_start_reconnection(remote) -> None:
    """Register diagnostic callback and start keep_reconnecting()."""
    remote.add_is_available_updated_callback(
        connection_status_changed
    )
    status_print(
        "Starting androidtvremote2 keep_reconnecting() for the current Remote object"
    )
    remote.keep_reconnecting()
    status_print(
        "androidtvremote2 keep_reconnecting() enabled"
    )


async def connect_to_discovered_tv(tv_ip: str):
    """
    Create a new Remote v2 object for a dynamically discovered IP,
    connect it, and start automatic reconnection.
    """

    remote = AndroidTVRemote(
        CLIENT_NAME,
        str(CERT_FILE),
        str(KEY_FILE),
        tv_ip,
        enable_ime=False,
        enable_voice=False,
    )

    try:
        status_print(
            f"Connecting to dynamically discovered {tv_ip}:6466"
        )

        await remote.async_connect()

        status_print(
            f"Remote v2 connection established at {tv_ip}:6466"
        )

        attach_and_start_reconnection(remote)

        return remote

    except InvalidAuth as exc:
        status_print(
            f"Connection authentication failed at {tv_ip}: {exc}"
        )

    except CannotConnect as exc:
        status_print(
            f"Cannot connect to {tv_ip}: {exc}"
        )

    except ConnectionClosed as exc:
        status_print(
            f"Connection closed while connecting to {tv_ip}: {exc}"
        )

    except Exception as exc:
        status_print(
            f"Unexpected connection error at {tv_ip}: {exc}"
        )

    try:
        remote.disconnect()
    except Exception:
        pass

    return None


async def getconnection(var: str, remote=None):
    """Obtain the initial connection or diagnose standby recovery.

    fresh: initial mDNS discovery, one Remote object, and keep_reconnecting().
    wakeup: send official WAKEUP through the existing Remote object first;
    then observe that same object for up to two minutes. No new mDNS discovery
    or replacement Remote object is created during standby recovery.
    """
    global tconn, command, device_in_standby
    var = var.lower().strip()
    if var not in ("fresh", "wakeup"):
        raise ValueError("tconn must be 'fresh' or 'wakeup'")
    if var == "fresh":
        status_print("tconn=fresh: starting initial mDNS discovery by MAC")
        tv_ip = await find_target_tv()
        if tv_ip is None:
            status_print("tconn=fresh: target Android TV not found")
            return None
        status_print(f"tconn=fresh: target discovered at {tv_ip}")
        remote = await connect_to_discovered_tv(tv_ip)
        if remote is None:
            return None
        tconn = "fresh"
        device_in_standby = False
        return remote

    status_print("tconn=wakeup: standby recovery requested")
    if remote is None:
        status_print("tconn=wakeup: no existing Remote v2 handle; cannot send WAKEUP")
        return None

    command = "Wakeup"
    status_print("tconn=wakeup: sending official Android WAKEUP command using the existing Remote v2 object")
    try:
        remote.send_key_command("WAKEUP")
        status_print("command=Wakeup: WAKEUP command sent")
    except Exception as exc:
        status_print(f"command=Wakeup: failed to send WAKEUP: {exc}")
        return None

    #status_print("command=Wakeup: waiting 10 seconds before checking Remote v2 availability")
    #await asyncio.sleep(10)
    status_print("command=Wakeup: beginning 2-minute Remote v2 connection recovery observation")

    deadline = asyncio.get_running_loop().time() + WAKE_REQUEST_TIMEOUT
    check_count = 0
    last_report_second = -10

    while not connection_is_alive(remote):
        check_count += 1
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            status_print("tconn=wakeup: request timeout - existing Remote v2 connection did not return within 2 minutes")
            return None
        elapsed_second = int(WAKE_REQUEST_TIMEOUT - remaining)
        if elapsed_second - last_report_second >= 10:
            last_report_second = elapsed_second
            status_print(f"tconn=wakeup: Remote v2 still unavailable; {remaining:.0f}s remaining; availability checks={check_count}")
        await asyncio.sleep(min(1.0, remaining))

    status_print("tconn=wakeup: EXISTING Remote v2 connection is usable again")
    device_in_standby = False
    tconn = "wakeup"
    status_print("tconn=wakeup: standby recovery completed using the existing Remote v2 connection")
    return remote


async def execute_command(remote, command_name, command_value):
    """Send one key command through the current Remote v2 handle."""

    global command

    command = command_name

    status_print(
        f"command={command}: sending {command_value}"
    )

    # Never send a command against a dead connection.
    if not connection_is_alive(remote):

        status_print(
            f"command={command}: connection unavailable; "
            "waiting for automatic reconnection"
        )

        for _ in range(60):

            if connection_is_alive(remote):
                break

            await asyncio.sleep(1)

    if not connection_is_alive(remote):

        status_print(
            f"command={command}: skipped - no usable connection"
        )

        return False

    try:

        remote.send_key_command(command_value)

        status_print(
            f"command={command}: sent"
        )

        return True

    except Exception as exc:

        status_print(
            f"command={command}: failed: {exc}"
        )

        return False


async def execute_app_command(remote, app_definition):
    """
    Launch an Android TV application using its package ID.

    The package ID is the documented androidtvremote2 app-launch
    mechanism. The library converts it to market://launch?id=....

    If the Mi Box returns a RemoteError, that is reported as a
    device/app-launch error. It is not silently converted into a
    successful launch.
    """

    global command

    command = app_definition["name"]
    package_id = app_definition["package"]
    deep_link = app_definition["deep_link"]

    status_print(
        f"command={command}: launching package {package_id}"
    )

    status_print(
        f"command={command}: documented deep-link fallback is "
        f"{deep_link}"
    )

    if not connection_is_alive(remote):

        status_print(
            f"command={command}: connection unavailable; "
            "waiting for automatic reconnection"
        )

        for _ in range(60):

            if connection_is_alive(remote):
                break

            await asyncio.sleep(1)

    if not connection_is_alive(remote):

        status_print(
            f"command={command}: skipped - no usable connection"
        )

        return False

    try:

        remote.send_launch_app_command(package_id)

        status_print(
            f"command={command}: package launch request sent"
        )

    except Exception as exc:

        status_print(
            f"command={command}: launch request failed: {exc}"
        )

        return False

    # androidtvremote2 0.3.2 can receive/log a RemoteError from
    # the device. Give the device a short window to report it.
    await asyncio.sleep(1)

    if not connection_is_alive(remote):

        status_print(
            f"command={command}: Remote v2 connection closed after "
            "the app-launch request; the device may have rejected "
            "the app-link request"
        )

        return False

    status_print(
        f"command={command}: Remote v2 connection remains active "
        "after app-launch request"
    )

    return True


async def run_all_commands(remote):
    """
    Execute the complete configured command sequence.

    Command execution stops only when the connection is unusable
    for a command; it never pretends that a skipped command was sent.
    """

    global command

    status_print(
        f"Beginning command test: {len(KEY_COMMANDS)} key commands "
        f"and {len(APP_COMMANDS)} app launches"
    )

    # --------------------------------------------------------
    # Remote keys
    # --------------------------------------------------------

    for command_name, command_value in KEY_COMMANDS:

        if not connection_is_alive(remote):

            status_print(
                "Command sequence paused: no usable connection"
            )

            return False

        success = await execute_command(
            remote,
            command_name,
            command_value,
        )

        if not success:

            status_print(
                f"Command sequence stopped at command={command_name}"
            )

            return False

        await asyncio.sleep(COMMAND_WAIT)

    # --------------------------------------------------------
    # Application launch commands
    # --------------------------------------------------------

    for app_definition in APP_COMMANDS:

        if not connection_is_alive(remote):

            status_print(
                "App sequence paused: no usable connection"
            )

            return False

        success = await execute_app_command(
            remote,
            app_definition,
        )

        if not success:

            # Do not pretend an app launch succeeded.
            # Continue with the next app only if the connection
            # has actually recovered.
            if not connection_is_alive(remote):

                status_print(
                    "App launch sequence stopped because the "
                    "Remote v2 connection is unavailable"
                )

                return False

        await asyncio.sleep(COMMAND_WAIT)

    status_print(
        "All configured commands exhausted"
    )

    return True


async def force_standby(remote):
    """
    Force Android TV into standby using POWER.

    POWER remains outside KEY_COMMANDS so that it is only sent
    after the command sequence has completed.
    """

    global command
    global device_in_standby

    command = "Power"

    status_print(
        "command=Power: forcing Android TV into standby"
    )

    if not connection_is_alive(remote):

        status_print(
            "command=Power: waiting for automatic reconnection"
        )

        for _ in range(60):

            if connection_is_alive(remote):
                break

            await asyncio.sleep(1)

    if not connection_is_alive(remote):

        status_print(
            "command=Power: no usable connection; "
            "cannot send standby command"
        )

        return False

    try:

        remote.send_key_command("POWER")

        device_in_standby = True

        status_print(
            "command=Power: standby command sent"
        )

        return True

    except Exception as exc:

        status_print(
            f"command=Power: failed: {exc}"
        )

        return False


async def status_reporter(remote, stop_event):
    """
    Report the current connection state every five minutes.

    The reporter deliberately does not attempt recovery itself.
    androidtvremote2 keep_reconnecting() owns background reconnection;
    the WAKEUP recovery loop only observes the existing Remote object.
    """

    while not stop_event.is_set():

        try:

            await asyncio.wait_for(
                stop_event.wait(),
                timeout=WAIT_TIME * 60,
            )

            break

        except asyncio.TimeoutError:

            if connection_is_alive(remote):

                if device_in_standby:
                    status_print(
                        "5-minute status report: standby state; "
                        "Remote v2 connection currently active"
                    )
                else:
                    status_print(
                        "5-minute status report: Connection Active"
                    )

            else:

                if device_in_standby:
                    status_print(
                        "5-minute status report: standby state; "
                        "Remote v2 connection unavailable; "
                        "automatic reconnection remains enabled"
                    )
                else:
                    status_print(
                        "5-minute status report: Connection Lost; "
                        "automatic reconnection remains enabled"
                    )


# ============================================================
# Main command test
# ============================================================

async def command_test_main():

    global tconn
    global device_in_standby

    print()
    print("==============================================")
    print(" Android TV Remote v2 Command Test")
    print("==============================================")
    print(f"Target MAC  : {TARGET_MAC}")
    print(f"Certificate : {CERT_FILE}")
    print(f"Private key : {KEY_FILE}")
    print(f"Command wait: {COMMAND_WAIT} seconds")
    print(f"Standby wait: {STANDBY_WAIT} seconds")
    print(f"WAKEUP recovery timeout: {WAKE_REQUEST_TIMEOUT} seconds")
    print(f"Status      : every {WAIT_TIME} minutes")
    print()

    if not CERT_FILE.is_file():

        status_print(
            f"ERROR: Certificate not found: {CERT_FILE}"
        )

        return

    if not KEY_FILE.is_file():

        status_print(
            f"ERROR: Private key not found: {KEY_FILE}"
        )

        return

    remote = None
    reporter_task = None
    stop_reporter = asyncio.Event()

    try:

        # ----------------------------------------------------
        # 1. Fresh connection.
        # ----------------------------------------------------

        tconn = "fresh"

        remote = await getconnection(tconn)

        if remote is None:

            status_print(
                "Initial fresh connection failed. Exiting."
            )

            return

        reporter_task = asyncio.create_task(
            status_reporter(
                remote,
                stop_reporter,
            )
        )

        status_print(
            "Fresh connection obtained. Waiting 5 seconds."
        )

        await asyncio.sleep(5)

        # ----------------------------------------------------
        # 2. First command sequence.
        # ----------------------------------------------------

        if not await run_all_commands(remote):

            status_print(
                "First command sequence did not complete."
            )

            return

        # ----------------------------------------------------
        # 3. Force standby.
        # ----------------------------------------------------

        if not await force_standby(remote):

            status_print(
                "Standby command failed. Exiting."
            )

            return

        status_print(
            "Device should now be in standby."
        )

        status_print(
            "Waiting 5 minutes in standby before official WAKEUP request."
        )

        await asyncio.sleep(STANDBY_WAIT)

        # ----------------------------------------------------
        # 4. Wakeup/recovery.
        # ----------------------------------------------------

        tconn = "wakeup"

        remote = await getconnection(
            tconn,
            remote,
        )

        if remote is None:

            status_print(
                "WAKEUP request timed out or failed. Command test will NOT "
                "continue without a usable connection."
            )

            return

        status_print(
            "WAKEUP request completed. Waiting 5 seconds."
        )

        await asyncio.sleep(5)

        if not connection_is_alive(remote):

            status_print(
                "WAKEUP did not leave a usable connection."
                "Second command sequence will NOT start."
            )

            return

        # ----------------------------------------------------
        # 5. Second command sequence.
        # ----------------------------------------------------

        if await run_all_commands(remote):

            status_print(
                "Second command sequence completed."
            )

        else:

            status_print(
                "Second command sequence did not complete."
            )

    except asyncio.CancelledError:

        status_print(
            "Program cancelled."
        )

    except KeyboardInterrupt:

        status_print(
            "Program stopped by user."
        )

    except Exception as exc:

        status_print(
            f"Fatal error: {exc}"
        )

    finally:

        stop_reporter.set()

        if reporter_task is not None:

            try:
                await reporter_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        if remote is not None:

            try:
                remote.disconnect()
            except Exception:
                pass

        status_print(
            "Command test finished."
        )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    try:
        asyncio.run(command_test_main())
    except KeyboardInterrupt:
        # asyncio.run() may propagate KeyboardInterrupt after
        # cancelling the main task. Keep shutdown quiet.
        print()
        status_print("Program stopped by user.")
