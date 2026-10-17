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
# Connect and monitor
# ============================================================

async def monitor_connection(tv_ip):

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

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Keep this AndroidTVRemote object alive for the entire
    # lifetime of the monitor.
    #
    # androidtvremote2 keeps the current RemoteProtocol and
    # transport inside this object. keep_reconnecting() uses
    # that same object to reconnect after a connection loss.
    # --------------------------------------------------------

    remote = AndroidTVRemote(
        CLIENT_NAME,
        str(CERT_FILE),
        str(KEY_FILE),
        tv_ip,
        enable_ime=False,
        enable_voice=False,
    )

    # Register the availability callback BEFORE connecting so
    # all subsequent connection-loss/recovery events are seen.
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

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Do NOT create another AndroidTVRemote object and do
        # NOT disconnect this one.
        #
        # keep_reconnecting() monitors the connection held by
        # this exact 'remote' object and reconnects it whenever
        # androidtvremote2 detects on_con_lost.
        # ----------------------------------------------------

        remote.keep_reconnecting()

        print(
            "Automatic reconnection enabled."
        )
        print()

        # ----------------------------------------------------
        # Five-minute status reporting.
        #
        # This is only a periodic report. It does NOT perform
        # the reconnection itself; keep_reconnecting() does that.
        # ----------------------------------------------------

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
        # Only disconnect when the whole monitor is stopping.
        #
        # Do NOT call disconnect() when the TV enters standby;
        # keep_reconnecting() needs this object/connection state.
        # ----------------------------------------------------

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
