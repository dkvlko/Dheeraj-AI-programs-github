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
# Check the existing Remote v2 connection
# ============================================================

def connection_is_alive(remote):
    """
    Inspect the existing androidtvremote2 connection.

    No key or command is sent to the TV.

    Returns True if the underlying Remote v2 protocol
    and asyncio transport still appear to be alive.
    """

    # androidtvremote2 0.3.2 stores the active protocol here.
    protocol = getattr(
        remote,
        "_remote_message_protocol",
        None,
    )

    if protocol is None:
        return False

    # The underlying asyncio TLS transport.
    transport = getattr(
        remote,
        "_transport",
        None,
    )

    if transport is None:
        return False

    if transport.is_closing():
        return False

    # RemoteProtocol creates an on_con_lost Future.
    on_con_lost = getattr(
        protocol,
        "on_con_lost",
        None,
    )

    if on_con_lost is not None:

        if on_con_lost.done():
            return False

    return True


# ============================================================
# Connection status callback
# ============================================================

def connection_status_changed(is_available: bool) -> None:
    """
    Called by androidtvremote2 when the Remote v2 connection
    becomes unavailable or available again.

    keep_reconnecting() invokes this callback indirectly:
      connection lost     -> False
      successful reconnect -> True
    """

    if is_available:
        print()
        print("Connection Active")
        print("Remote v2 connection recovered.")
        print()
    else:
        print()
        print("No useable connection")
        print("Remote v2 connection lost.")
        print("androidtvremote2 will keep trying to reconnect.")
        print()


# ============================================================
# Establish and maintain the Remote v2 connection
# ============================================================

async def connect_remote(tv_ip):
    """
    Establish the Android TV Remote v2 connection.

    This is deliberately kept separate from all command logic.
    The same AndroidTVRemote object is returned and remains alive
    for the rest of the program.

    keep_reconnecting() is enabled on this exact object.
    """

    print(
        "=============================================="
    )
    print(
        " Connecting to Android TV Remote v2"
    )
    print(
        "=============================================="
    )

    print(
        f"Discovered IP : {tv_ip}"
    )

    print(
        f"MAC           : {TARGET_MAC}"
    )

    print()

    remote = AndroidTVRemote(
        CLIENT_NAME,
        str(CERT_FILE),
        str(KEY_FILE),
        tv_ip,
        enable_ime=False,
        enable_voice=False,
    )

    # Register the availability callback BEFORE connecting.
    remote.add_is_available_updated_callback(
        connection_status_changed
    )

    try:

        print(
            f"Connecting to {tv_ip}:6466..."
        )

        await remote.async_connect()

        print()
        print(
            "Remote v2 connection established."
        )

        # IMPORTANT:
        # Keep this exact AndroidTVRemote object alive.
        # keep_reconnecting() operates on this object.
        remote.keep_reconnecting()

        print(
            "Automatic reconnection enabled."
        )

        print()

        return remote

    except Exception:
        # Only disconnect if the initial connection itself failed.
        remote.disconnect()
        raise


# ============================================================
# Wait for an already-created Remote v2 connection
# ============================================================

async def wait_for_connection(remote, check_interval=0.2):
    """
    Wait asynchronously for the existing remote object to become
    usable again.

    Reconnection itself is NOT performed here.
    keep_reconnecting() performs that operation.
    """

    if connection_is_alive(remote):
        return True

    print(
        "Connection unavailable."
    )
    print(
        "Waiting for keep_reconnecting() to restore it..."
    )

    while not connection_is_alive(remote):
        await asyncio.sleep(check_interval)

    print(
        "Remote v2 connection is available again."
    )

    return True


# ============================================================
# Asynchronous POWER -> WAKEUP sequence
# ============================================================

async def power_wakeup_sequence(remote):
    """
    Independent asynchronous command sequence.

    1. Wait 15 seconds after connection.
    2. Verify the existing connection.
    3. Send POWER.
    4. Wait 2 seconds.
    5. Check the connection again.
    6. If necessary, wait for keep_reconnecting().
    7. Send WAKEUP.

    No new AndroidTVRemote object is created here.
    """

    print()
    print(
        "POWER/WAKEUP asynchronous task started."
    )
    print(
        "Waiting 15 seconds before POWER..."
    )
    print()

    await asyncio.sleep(15)

    # --------------------------------------------------------
    # Check connection before POWER
    # --------------------------------------------------------

    await wait_for_connection(remote)

    print(
        "Connection available."
    )

    # --------------------------------------------------------
    # POWER
    # --------------------------------------------------------

    print(
        "Sending POWER..."
    )

    try:

        remote.send_key_command("POWER")

        print(
            "POWER sent."
        )

    except Exception as exc:

        print(
            f"POWER could not be sent: {exc}"
        )

        return

    # --------------------------------------------------------
    # Exactly 2 seconds after POWER
    # --------------------------------------------------------

    print(
        "Waiting 2 seconds before WAKEUP..."
    )

    await asyncio.sleep(2)

    # --------------------------------------------------------
    # Check whether POWER caused the connection to disappear
    # --------------------------------------------------------

    if connection_is_alive(remote):

        print(
            "Connection still available after POWER."
        )

    else:

        print(
            "Connection unavailable after POWER."
        )

        await wait_for_connection(remote)

    # --------------------------------------------------------
    # WAKEUP
    # --------------------------------------------------------

    print(
        "Sending WAKEUP..."
    )

    try:

        remote.send_key_command("WAKEUP")

        print(
            "WAKEUP sent."
        )

    except Exception as exc:

        print(
            f"WAKEUP could not be sent: {exc}"
        )

        return

    print()
    print(
        "POWER/WAKEUP asynchronous task completed."
    )
    print()


# ============================================================
# Asynchronous connection-status monitor
# ============================================================

async def status_monitor(remote):

    while True:

        print(
            f"Waiting {WAIT_TIME} minute(s) "
            "before status report..."
        )

        await asyncio.sleep(
            WAIT_TIME * 60
        )

        print(
            "Checking existing Remote v2 connection..."
        )

        if connection_is_alive(remote):

            print(
                "Connection Active"
            )

        else:

            print(
                "No useable connection"
            )

            print(
                "Automatic reconnection remains enabled."
            )

        print()


# ============================================================
# Run the connection and asynchronous tasks
# ============================================================

async def monitor_connection(tv_ip):

    remote = None
    power_task = None
    status_task = None

    try:

        # ----------------------------------------------------
        # This is the separate connection routine.
        # ----------------------------------------------------

        remote = await connect_remote(tv_ip)

        # ----------------------------------------------------
        # These are independent asynchronous tasks.
        # Neither one creates or replaces the connection.
        # ----------------------------------------------------

        power_task = asyncio.create_task(
            power_wakeup_sequence(remote)
        )

        status_task = asyncio.create_task(
            status_monitor(remote)
        )

        # Keep the monitor alive while both tasks operate.
        await asyncio.gather(
            power_task,
            status_task,
        )

    except InvalidAuth as exc:

        print()
        print(
            "No useable connection"
        )

        print(
            f"Remote v2 authentication error: {exc}"
        )

    except CannotConnect as exc:

        print()
        print(
            "No useable connection"
        )

        print(
            f"Could not connect: {exc}"
        )

    except ConnectionClosed as exc:

        print()
        print(
            "No useable connection"
        )

        print(
            f"Connection closed: {exc}"
        )

    except asyncio.CancelledError:

        print()
        print(
            "Monitor cancelled."
        )

        raise

    except KeyboardInterrupt:

        print()
        print(
            "Monitor stopped by user."
        )

    except Exception as exc:

        print()
        print(
            "No useable connection"
        )

        print(
            f"Unexpected error: {exc}"
        )

    finally:

        # ----------------------------------------------------
        # Cancel asynchronous tasks before closing the remote.
        # ----------------------------------------------------

        current = asyncio.current_task()

        for task in (
            power_task,
            status_task,
        ):

            if (
                task is not None
                and task is not current
                and not task.done()
            ):
                task.cancel()

        for task in (
            power_task,
            status_task,
        ):

            if task is not None and task is not current:

                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

        # ----------------------------------------------------
        # Only disconnect when the entire monitor is stopping.
        # ----------------------------------------------------

        if remote is not None:

            remote.disconnect()

            print(
                "Remote v2 connection closed."
            )


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
