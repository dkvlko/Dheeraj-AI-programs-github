"""
Android TV Remote with Enable/Disable Toggle

Toggle Remote:
CTRL + ALT + R  -> Enable / Disable remote

When disabled:
keyboard behaves normally

When enabled:
keyboard controls TV
"""

import subprocess
import keyboard
import datetime
import shlex
import re
import shutil

# -----------------------------
# TV MAC ADDRESS
# -----------------------------

TV_MAC = "ec:fa:5c:bf:70:7c".lower()

TV_IP = None
ADB_DEVICE = None
NETWORK_INTERFACE = None
NETWORK_CIDR = None

remote_enabled = False


# -----------------------------
# DISCOVER TV
# -----------------------------

def get_network_info():
    """
    Determine the active IPv4 interface and connected subnet using
    the native Linux 'ip' command.
    """
    result = subprocess.run(
        ["ip", "-4", "route", "show", "scope", "link"],
        capture_output=True,
        text=True,
        check=False
    )

    routes = []

    for line in result.stdout.splitlines():
        parts = line.split()

        if not parts:
            continue

        # Example:
        # 192.168.0.0/24 dev eno1 proto kernel scope link src 192.168.0.10
        network = parts[0]

        if "/" not in network:
            continue

        try:
            interface = parts[parts.index("dev") + 1]
        except (ValueError, IndexError):
            continue

        routes.append((network, interface))

    # Prefer a non-container Ethernet/Wi-Fi interface.
    preferred = [
        item for item in routes
        if not item[1].startswith(("docker", "br-", "virbr", "veth"))
    ]

    if preferred:
        return preferred[0]

    if routes:
        return routes[0]

    return None, None


def get_adb_devices():
    """Return ADB devices as a list of (serial, state)."""
    result = subprocess.run(
        ["adb", "devices"],
        capture_output=True,
        text=True,
        check=False
    )

    devices = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if not line or line.startswith("List of devices attached"):
            continue

        parts = line.split()

        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))

    return devices


def discover_tv():
    global TV_IP, NETWORK_INTERFACE, NETWORK_CIDR

    print("\nDiscovering TV...\n")

    # -------------------------------------------------
    # First determine the active LAN interface/subnet.
    # -------------------------------------------------
    NETWORK_CIDR, NETWORK_INTERFACE = get_network_info()

    if not NETWORK_INTERFACE:
        print("Could not determine the active network interface.")
        return False

    print(f"Network interface: {NETWORK_INTERFACE}")
    print(f"Network: {NETWORK_CIDR}")

    # -------------------------------------------------
    # Use the native Linux neighbour table first.
    # Use the native Linux neighbour table.
    # -------------------------------------------------
    result = subprocess.run(
        ["ip", "neigh", "show", "dev", NETWORK_INTERFACE],
        capture_output=True,
        text=True,
        check=False
    )

    print("\nDevices currently known by Linux:\n")

    for line in result.stdout.splitlines():
        line = line.strip()

        # Example:
        # 192.168.0.102 lladdr ec:fa:5c:bf:70:7c REACHABLE
        match = re.match(
            r"^(\d+\.\d+\.\d+\.\d+)\s+"
            r".*?\blladdr\s+([0-9a-fA-F:]{17})\b",
            line
        )

        if not match:
            continue

        ip = match.group(1)
        mac = match.group(2).lower()

        print(f"{ip:<16} {mac}")

        if mac == TV_MAC:
            TV_IP = ip
            print(f"\nTV FOUND: {TV_IP}")
            return True

    # -------------------------------------------------
    # If the TV is not currently in the neighbour table,
    # use native 'nmap' if available.
    #
    # Since the TV exposes ADB on TCP/5555, scan for
    # hosts with that port open.
    # -------------------------------------------------
    print("\nTV not found in the Linux neighbour table.")

    nmap_path = shutil.which("nmap")

    if nmap_path:
        print(f"Scanning {NETWORK_CIDR} for TCP port 5555...\n")

        result = subprocess.run(
            [nmap_path, "-n", "-p", "5555", "--open", NETWORK_CIDR],
            capture_output=True,
            text=True,
            check=False
        )

        found_ips = []

        for line in result.stdout.splitlines():
            match = re.match(r"^Nmap scan report for (\d+\.\d+\.\d+\.\d+)$", line.strip())

            if match:
                current_ip = match.group(1)
                continue

            if "5555/tcp" in line and "open" in line:
                if "current_ip" in locals():
                    found_ips.append(current_ip)

        # Try each ADB candidate and verify it with adb.
        for ip in found_ips:
            print(f"ADB port found at {ip}:5555")

            result = subprocess.run(
                ["adb", "connect", f"{ip}:5555"],
                capture_output=True,
                text=True,
                check=False
            )

            devices = get_adb_devices()

            for serial, state in devices:
                if serial == f"{ip}:5555" and state == "device":
                    TV_IP = ip
                    print(f"\nTV/ADB DEVICE FOUND: {serial}")
                    return True

        print("No usable Android TV ADB device found.")

    else:
        print("nmap is not installed; skipping TCP/5555 discovery.")
        print("Install it with: sudo apt install nmap")

    print("TV not found.")
    return False

# -----------------------------
# ADB COMMAND
# -----------------------------

def adb(cmd):
    if not ADB_DEVICE:
        print("ADB device is not connected.")
        return False

    result = subprocess.run(
        ["adb", "-s", ADB_DEVICE, *shlex.split(cmd)],
        text=True
    )

    if result.returncode != 0:
        print(f"ADB command failed: {cmd}")

    return result.returncode == 0


def key(code):

    if not remote_enabled:
        return

    adb(f"shell input keyevent {code}")


# -----------------------------
# NAVIGATION
# -----------------------------

def up(): key(19)
def down(): key(20)
def left(): key(21)
def right(): key(22)
def select(): key(66)
def back(): key(4)
def home(): key(3)


# -----------------------------
# POWER
# -----------------------------

def power(): key(26)


# -----------------------------
# VOLUME
# -----------------------------

def vol_up(): key(24)
def vol_down(): key(25)
def mute(): key(164)


# -----------------------------
# APPS
# -----------------------------

def youtube():
    if remote_enabled:
        adb("shell am start -n com.google.android.youtube.tv/.MainActivity")


def netflix():
    if remote_enabled:
        adb("shell am start -n com.netflix.ninja/.MainActivity")


# -----------------------------
# SCREENSHOT
# -----------------------------

def screenshot():

    if not remote_enabled:
        return

    filename = f"tvshot_{datetime.datetime.now().strftime('%H%M%S')}.png"

    adb("shell screencap -p /sdcard/screen.png")
    adb(f"pull /sdcard/screen.png {filename}")

    print("Screenshot saved:", filename)


# -----------------------------
# TEXT INPUT
# -----------------------------

def type_text():

    if not remote_enabled:
        return

    text = input("Enter text: ")
    text = text.replace(" ", "%s")

    adb(f"shell input text {text}")


# -----------------------------
# TOGGLE REMOTE
# -----------------------------

def toggle_remote():

    global remote_enabled

    remote_enabled = not remote_enabled

    if remote_enabled:
        print("\nREMOTE ENABLED\n")
    else:
        print("\nREMOTE DISABLED\n")


# -----------------------------
# CONNECT ADB
# -----------------------------

def connect():

    global ADB_DEVICE

    # Start the ADB server if necessary.
    subprocess.run(
        ["adb", "start-server"],
        check=False
    )

    # -------------------------------------------------
    # First use an already-existing ADB connection.
    # -------------------------------------------------
    devices = get_adb_devices()

    for serial, state in devices:
        if state != "device":
            continue

        # If discovery found an IP, match the ADB device to it.
        if TV_IP and (
            serial == TV_IP
            or serial == f"{TV_IP}:5555"
            or serial.startswith(TV_IP + ":")
        ):
            ADB_DEVICE = serial
            print(f"Using existing ADB connection: {ADB_DEVICE}")
            return True

    # -------------------------------------------------
    # No existing connection. Connect to the dynamically
    # discovered TV IP on the standard ADB TCP port.
    # -------------------------------------------------
    if not TV_IP:
        print("No TV IP address is available for ADB.")
        return False

    print(f"Connecting to TV at {TV_IP}:5555...")

    result = subprocess.run(
        ["adb", "connect", f"{TV_IP}:5555"],
        capture_output=True,
        text=True,
        check=False
    )

    output = (result.stdout.strip() or result.stderr.strip())

    if output:
        print(output)

    # -------------------------------------------------
    # Verify that ADB actually reports the TV as a
    # usable 'device'.
    # -------------------------------------------------
    devices = get_adb_devices()

    for serial, state in devices:
        if (
            state == "device"
            and (
                serial == TV_IP
                or serial == f"{TV_IP}:5555"
                or serial.startswith(TV_IP + ":")
            )
        ):
            ADB_DEVICE = serial
            print(f"ADB connected: {ADB_DEVICE}")
            return True

    print("ADB connection to TV failed.")
    return False

# -----------------------------
# HELP
# -----------------------------

def help_menu():

    print("\n========= ANDROID TV REMOTE =========\n")

    print("Toggle Remote")
    print("CTRL + ALT + R  -> Enable / Disable remote")

    print("\nNavigation")
    print("Arrow keys -> Navigate")
    print("Enter      -> Select")
    print("Backspace  -> Back")
    print("h          -> Home")

    print("\nVolume")
    print("+ / -      -> Volume")
    print("m          -> Mute")

    print("\nApps")
    print("y          -> YouTube")
    print("n          -> Netflix")

    print("\nUtilities")
    print("s          -> Screenshot")
    print("t          -> Type text")

    print("\nq          -> Quit\n")


# -----------------------------
# MAIN
# -----------------------------

def main():

    if not discover_tv():
        print("Remote cannot start because the TV could not be discovered.")
        return

    if not connect():
        print("Remote cannot start because the TV is not available through ADB.")
        return

    help_menu()

    # toggle remote
    keyboard.add_hotkey("ctrl+alt+r", toggle_remote)

    # navigation
    keyboard.add_hotkey("up", up)
    keyboard.add_hotkey("down", down)
    keyboard.add_hotkey("left", left)
    keyboard.add_hotkey("right", right)

    keyboard.add_hotkey("enter", select)
    keyboard.add_hotkey("backspace", back)
    keyboard.add_hotkey("h", home)

    # power
    keyboard.add_hotkey("p", power)

    # volume
    keyboard.add_hotkey("+", vol_up)
    keyboard.add_hotkey("-", vol_down)
    keyboard.add_hotkey("m", mute)

    # apps
    keyboard.add_hotkey("y", youtube)
    keyboard.add_hotkey("n", netflix)

    # utilities
    keyboard.add_hotkey("s", screenshot)
    keyboard.add_hotkey("t", type_text)

    print("Remote ready. Press CTRL+ALT+R to enable.")

    keyboard.wait("q")


if __name__ == "__main__":
    main()
