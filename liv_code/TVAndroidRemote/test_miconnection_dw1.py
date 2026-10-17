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

# User connection requirements:
#
#   fresh  = perform mDNS discovery by MAC and establish a
#            fresh Android TV Remote v2 connection.
#
#   wakeup = use the existing connection handle/reconnection
#            mechanism and, when a usable connection exists,
#            send DPAD_UP to wake/activate the Android TV.
#
# Automatic reconnection remains enabled throughout the run.
tconn = "fresh"

# Current command being executed.
command = None

# How long to wait after every command.
COMMAND_WAIT = 5

# How long to wait after standby before requesting wakeup.
STANDBY_WAIT = 5 * 60

# ------------------------------------------------------------
# Commands available through androidtvremote2 0.3.2.
#
# These are the common commands documented by the project's
# TvKeys.txt. Additional RemoteKeyCode values exist in the
# full remotemessage.proto, but many are not meaningful as
# Android-TV remote buttons.
#
# Each entry is:
#     display name : value accepted by send_key_command()
# ------------------------------------------------------------

KEY_COMMANDS = [
    ("Up", "DPAD_UP"),
    ("Down", "DPAD_DOWN"),
    ("Left", "DPAD_LEFT"),
    ("Right", "DPAD_RIGHT"),
    ("Center", "DPAD_CENTER"),

    ("A", "BUTTON_A"),
    ("B", "BUTTON_B"),
    ("X", "BUTTON_X"),
    ("Y", "BUTTON_Y"),

    ("VolumeDown", "VOLUME_DOWN"),
    ("VolumeUp", "VOLUME_UP"),
    ("VolumeMute", "VOLUME_MUTE"),
    ("Mute", "MUTE"),

    ("Home", "HOME"),
    ("Back", "BACK"),

    ("MediaPlayPause", "MEDIA_PLAY_PAUSE"),
    ("MediaPlay", "MEDIA_PLAY"),
    ("MediaPause", "MEDIA_PAUSE"),
    ("MediaNext", "MEDIA_NEXT"),
    ("MediaPrevious", "MEDIA_PREVIOUS"),
    ("MediaStop", "MEDIA_STOP"),
    ("MediaRecord", "MEDIA_RECORD"),
    ("MediaRewind", "MEDIA_REWIND"),
    ("MediaFastForward", "MEDIA_FAST_FORWARD"),

    ("0", "0"),
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4", "4"),
    ("5", "5"),
    ("6", "6"),
    ("7", "7"),
    ("8", "8"),
    ("9", "9"),

    ("Delete", "DEL"),
    ("Enter", "ENTER"),
    ("ChannelUp", "CHANNEL_UP"),
    ("ChannelDown", "CHANNEL_DOWN"),

    ("F1", "F1"),
    ("F2", "F2"),
    ("F3", "F3"),
    ("F4", "F4"),
    ("F5", "F5"),
    ("F6", "F6"),
    ("F7", "F7"),
    ("F8", "F8"),
    ("F9", "F9"),
    ("F10", "F10"),
    ("F11", "F11"),
    ("F12", "F12"),

    ("TV", "TV"),
    ("Red", "PROG_RED"),
    ("Green", "PROG_GREEN"),
    ("Yellow", "PROG_YELLOW"),
    ("Blue", "PROG_BLUE"),

    ("Explorer", "EXPLORER"),
    ("Menu", "MENU"),
    ("Info", "INFO"),
    ("Guide", "GUIDE"),
    ("Teletext", "TV_TELETEXT"),
    ("Captions", "CAPTIONS"),
    ("DVR", "DVR"),
    ("AudioTrack", "MEDIA_AUDIO_TRACK"),
    ("Settings", "SETTINGS"),
    ("Search", "SEARCH"),
    ("Assistant", "ASSIST"),
]


# ------------------------------------------------------------
# App launch commands.
#
# These use Android TV app links rather than pretending that
# YouTube/Netflix/Prime Video are RemoteKeyCode values.
#
# If an app is not installed, Android TV may simply ignore the
# launch request or show its normal handling behaviour.
# ------------------------------------------------------------

APP_COMMANDS = [
    # Android TV package/application IDs.  androidtvremote2's
    # send_launch_app_command() accepts an app ID and converts
    # it to market://launch?id=... internally.
    ("YouTube", "com.google.android.youtube.tv"),
    ("Netflix", "com.netflix.ninja"),
    ("PrimeVideo", "com.amazon.amazonvideo.livingroom"),
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
    Inspect the existing androidtvremote2 connection.

    No key or command is sent.

    The attributes inspected here are the connection objects
    maintained internally by androidtvremote2 0.3.2.
    """

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

    if transport.is_closing():
        return False

    on_con_lost = getattr(
        protocol,
        "on_con_lost",
        None,
    )

    if on_con_lost is not None and on_con_lost.done():
        return False

    return True


def connection_status_changed(is_available: bool) -> None:
    """
    androidtvremote2 0.3.2 availability callback.

    keep_reconnecting() causes this callback to receive False
    after connection loss and True after successful recovery.
    """

    if is_available:
        status_print(
            "Connection Active - Remote v2 connection recovered"
        )
    else:
        status_print(
            "No useable connection - Remote v2 connection lost; "
            "automatic reconnection remains enabled"
        )


# ============================================================
# getconnection()
# ============================================================

async def getconnection(var: str, remote=None):
    """
    Obtain or recover the Android TV Remote v2 connection.

    var:
        "fresh"
            Perform fresh mDNS discovery by TARGET_MAC, create a
            new AndroidTVRemote object, connect to the discovered
            host, and enable automatic reconnection.

        "wakeup"
            Keep using the existing connection handle. Wait for a
            usable connection/reconnection, then send DPAD_UP.
            DPAD_UP is deliberately used rather than POWER because
            POWER could toggle the device back to standby.

    Returns:
        AndroidTVRemote connection object, or None on failure.
    """

    global tconn

    var = var.lower().strip()

    if var not in ("fresh", "wakeup"):
        raise ValueError(
            "tconn must be 'fresh' or 'wakeup'"
        )

    # --------------------------------------------------------
    # FRESH CONNECTION
    # --------------------------------------------------------

    if var == "fresh":

        status_print(
            "tconn=fresh: starting fresh mDNS discovery"
        )

        tv_ip = await find_target_tv()

        if tv_ip is None:

            status_print(
                "tconn=fresh: target Android TV not found"
            )

            return None

        status_print(
            f"tconn=fresh: target discovered at {tv_ip}"
        )

        # Create the connection handle that will remain alive
        # for the rest of this run.
        remote = AndroidTVRemote(
            CLIENT_NAME,
            str(CERT_FILE),
            str(KEY_FILE),
            tv_ip,
            enable_ime=False,
            enable_voice=False,
        )

        # Register callback before connecting.
        remote.add_is_available_updated_callback(
            connection_status_changed
        )

        try:

            status_print(
                f"tconn=fresh: connecting to {tv_ip}:6466"
            )

            await remote.async_connect()

            status_print(
                "tconn=fresh: Remote v2 connection established"
            )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Keep this exact object alive.
            #
            # androidtvremote2 will use this connection handle
            # to reconnect whenever the connection is lost.
            # ------------------------------------------------

            remote.keep_reconnecting()

            status_print(
                "Automatic reconnection enabled"
            )

            tconn = "fresh"

            return remote

        except InvalidAuth as exc:

            status_print(
                f"tconn=fresh: authentication failed: {exc}"
            )

        except CannotConnect as exc:

            status_print(
                f"tconn=fresh: cannot connect: {exc}"
            )

        except ConnectionClosed as exc:

            status_print(
                f"tconn=fresh: connection closed: {exc}"
            )

        except Exception as exc:

            status_print(
                f"tconn=fresh: unexpected error: {exc}"
            )

        remote.disconnect()
        return None

    # --------------------------------------------------------
    # WAKEUP / RECOVER EXISTING CONNECTION
    # --------------------------------------------------------

    if var == "wakeup":

        if remote is None:

            status_print(
                "tconn=wakeup: no existing connection handle"
            )

            return None

        status_print(
            "tconn=wakeup: requesting usable connection"
        )

        # keep_reconnecting() is already running. We wait for
        # the same connection handle to become usable again.
        #
        # This does not create a second AndroidTVRemote object.
        max_wait = 60
        elapsed = 0

        while elapsed < max_wait:

            if connection_is_alive(remote):
                break

            await asyncio.sleep(1)
            elapsed += 1

        if not connection_is_alive(remote):

            status_print(
                "tconn=wakeup: no usable connection after "
                f"{max_wait} seconds"
            )

            return remote

        status_print(
            "tconn=wakeup: usable connection obtained"
        )

        # ----------------------------------------------------
        # Send DPAD_UP.
        #
        # The purpose is to cause activity without toggling
        # standby. DPAD_UP is preferable to POWER here.
        # ----------------------------------------------------

        global command
        command = "Up"

        status_print(
            f"command={command}: sending DPAD_UP"
        )

        try:

            remote.send_key_command("DPAD_UP")

            status_print(
                "command=Up: sent successfully"
            )

        except Exception as exc:

            status_print(
                f"command=Up: send failed: {exc}"
            )

        tconn = "wakeup"

        return remote


# ============================================================
# Execute one command
# ============================================================

async def execute_command(remote, command_name, command_value):
    """
    Send one key command through the existing connection handle.
    """

    global command

    command = command_name

    status_print(
        f"command={command}: sending {command_value}"
    )

    # If the TV went unavailable between two commands,
    # don't create a new connection. keep_reconnecting()
    # owns recovery of this same handle.
    if not connection_is_alive(remote):

        status_print(
            f"command={command}: connection unavailable; "
            "waiting for automatic reconnection"
        )

        # Wait up to one minute for keep_reconnecting().
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


# ============================================================
# Execute app-launch command
# ============================================================

async def execute_app_command(remote, command_name, app_link):
    """
    Launch an application using Android TV Remote v2's
    RemoteAppLinkLaunchRequest facility.
    """

    global command

    command = command_name

    status_print(
        f"command={command}: launching {app_link}"
    )

    if not connection_is_alive(remote):

        status_print(
            f"command={command}: waiting for automatic "
            "reconnection"
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

        remote.send_launch_app_command(app_link)

        status_print(
            f"command={command}: launch request sent"
        )

        return True

    except Exception as exc:

        status_print(
            f"command={command}: launch failed: {exc}"
        )

        return False


# ============================================================
# Run all test commands
# ============================================================

async def run_all_commands(remote):
    """
    Execute the complete command sequence.

    Every command is held for COMMAND_WAIT seconds before
    the next command is sent.
    """

    global command

    status_print(
        f"Beginning command test: {len(KEY_COMMANDS)} key commands"
    )

    # --------------------------------------------------------
    # Remote keys
    # --------------------------------------------------------

    for command_name, command_value in KEY_COMMANDS:

        await execute_command(
            remote,
            command_name,
            command_value,
        )

        await asyncio.sleep(
            COMMAND_WAIT
        )

    # --------------------------------------------------------
    # Application launch commands
    # --------------------------------------------------------

    for command_name, app_link in APP_COMMANDS:

        await execute_app_command(
            remote,
            command_name,
            app_link,
        )

        await asyncio.sleep(
            COMMAND_WAIT
        )

    status_print(
        "All configured commands exhausted"
    )


# ============================================================
# Force standby
# ============================================================

async def force_standby(remote):
    """
    Force the Android TV into standby using POWER.

    POWER is intentionally kept outside KEY_COMMANDS because
    sending POWER during the command-test sequence would put
    the TV into standby before the sequence was complete.
    """

    global command

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

        status_print(
            "command=Power: standby command sent"
        )

        return True

    except Exception as exc:

        status_print(
            f"command=Power: failed: {exc}"
        )

        return False


# ============================================================
# Five-minute connection status reporter
# ============================================================

async def status_reporter(remote, stop_event):
    """
    Print the state of the existing connection every five
    minutes while automatic reconnection continues independently.
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

                status_print(
                    "5-minute status report: Connection Active"
                )

            else:

                status_print(
                    "5-minute status report: No useable connection; "
                    "automatic reconnection is enabled"
                )


# ============================================================
# Main
# ============================================================

async def main():

    global tconn

    print()
    print("==============================================")
    print(" Android TV Remote v2 Command Test")
    print("==============================================")
    print(f"Target MAC  : {TARGET_MAC}")
    print(f"Certificate : {CERT_FILE}")
    print(f"Private key : {KEY_FILE}")
    print(f"Command wait: {COMMAND_WAIT} seconds")
    print(f"Standby wait: {STANDBY_WAIT} seconds")
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

        remote = await getconnection(
            tconn
        )

        if remote is None:

            status_print(
                "Initial fresh connection failed. Exiting."
            )

            return

        # ----------------------------------------------------
        # Start independent 5-minute status reporting.
        # ----------------------------------------------------

        reporter_task = asyncio.create_task(
            status_reporter(
                remote,
                stop_reporter,
            )
        )

        # ----------------------------------------------------
        # Give the freshly connected TV five seconds to settle.
        # ----------------------------------------------------

        status_print(
            "Fresh connection obtained. Waiting 5 seconds."
        )

        await asyncio.sleep(5)

        # ----------------------------------------------------
        # 2. Exercise all configured commands.
        # ----------------------------------------------------

        await run_all_commands(
            remote
        )

        # ----------------------------------------------------
        # 3. Force standby.
        # ----------------------------------------------------

        await force_standby(
            remote
        )

        # ----------------------------------------------------
        # 4. Wait five minutes.
        #
        # Automatic reconnection remains enabled during this
        # entire period.
        # ----------------------------------------------------

        status_print(
            "Device should now be in standby."
        )

        status_print(
            "Waiting 5 minutes before wakeup request."
        )

        await asyncio.sleep(
            STANDBY_WAIT
        )

        # ----------------------------------------------------
        # 5. Request wakeup using the SAME connection handle.
        # ----------------------------------------------------

        tconn = "wakeup"

        remote = await getconnection(
            tconn,
            remote,
        )

        if remote is None:

            status_print(
                "Wakeup failed. Exiting."
            )

            return

        # Give the device five seconds after the wakeup command.
        status_print(
            "Wakeup command completed. Waiting 5 seconds."
        )

        await asyncio.sleep(5)

        # ----------------------------------------------------
        # 6. Run the complete command sequence again.
        # ----------------------------------------------------

        await run_all_commands(
            remote
        )

        status_print(
            "Second command sequence completed."
        )

    except KeyboardInterrupt:

        status_print(
            "Program stopped by user."
        )

    except asyncio.CancelledError:

        status_print(
            "Program cancelled."
        )

    except Exception as exc:

        status_print(
            f"Fatal error: {exc}"
        )

    finally:

        # Stop the periodic status reporter.
        stop_reporter.set()

        if reporter_task is not None:

            try:
                await reporter_task
            except Exception:
                pass

        # Keep the connection alive/reconnecting during the test,
        # but when the complete test exits, release the handle.
        if remote is not None:

            remote.disconnect()

        status_print(
            "Command test finished."
        )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())
# ============================================================
# Main
# ============================================================

async def main():

    print()
    print("==============================================")
    print(" Android TV Remote v2 Connection Monitor")
    print("==============================================")
    print(
        f"Target MAC  : {TARGET_MAC}"
    )
    print(
        f"Certificate : {CERT_FILE}"
    )
    print(
        f"Private key : {KEY_FILE}"
    )
    print(
        f"WAIT_TIME   : {WAIT_TIME} minutes"
    )
    print()

    # --------------------------------------------------------
    # Verify certificate files.
    # --------------------------------------------------------

    if not CERT_FILE.is_file():

        print(
            f"ERROR: Certificate not found:\n"
            f"       {CERT_FILE}"
        )

        return

    if not KEY_FILE.is_file():

        print(
            f"ERROR: Private key not found:\n"
            f"       {KEY_FILE}"
        )

        return

    # --------------------------------------------------------
    # Find the TV dynamically.
    # --------------------------------------------------------

    tv_ip = await find_target_tv()

    if tv_ip is None:

        print()
        print(
            "Target Android TV was not found."
        )

        print(
            "No useable connection"
        )

        return

    # --------------------------------------------------------
    # Connect and monitor.
    # --------------------------------------------------------

    await monitor_connection(tv_ip)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())
