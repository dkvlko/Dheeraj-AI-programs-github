import subprocess
import time
import re
import sys

CONTROLLER = "30:3A:64:79:95:5E"


# ---------------------------
# SCAN DEVICES
# ---------------------------
def scan_devices():
    print("Scanning for Bluetooth devices (10 seconds)...\n")

    proc = subprocess.Popen(
        ["bluetoothctl"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1
    )

    setup = [
        f"select {CONTROLLER}",
        "power on",
        "agent on",
        "default-agent",
        "scan on"
    ]

    for cmd in setup:
        proc.stdin.write(cmd + "\n")
        proc.stdin.flush()
        time.sleep(1)

    devices = {}
    start = time.time()

    while time.time() - start < 10:
        line = proc.stdout.readline()

        if not line:
            time.sleep(0.1)
            continue

        line = line.strip()

        if "Device" in line and "RSSI" not in line:
            match = re.search(r"Device ([0-9A-F:]+) (.+)", line)
            if match:
                addr, name = match.groups()
                if addr not in devices:
                    devices[addr] = name
                    print(f"Found: {name} [{addr}]")

    proc.stdin.write("scan off\n")
    proc.stdin.flush()
    proc.terminate()

    device_list = list(devices.items())

    if not device_list:
        print("\nNo devices found.")
        sys.exit(0)

    print("\nFinal device list:\n")
    for i, (addr, name) in enumerate(device_list):
        print(f"{i}: {name} [{addr}]")

    return device_list


# ---------------------------
# SELECT DEVICE
# ---------------------------
def select_device(devices):
    try:
        choice = int(input("\nSelect device index: "))
        return devices[choice]
    except:
        print("Invalid selection")
        sys.exit(1)


# ---------------------------
# CONNECT DEVICE
# ---------------------------
def connect_device(addr):
    print(f"\nConnecting to {addr}...\n")

    proc = subprocess.Popen(
        ["bluetoothctl"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1
    )

    # Step 1: prepare environment
    setup_steps = [
        f"select {CONTROLLER}",
        "power on",
        "agent on",
        "default-agent",
        "scan on"
    ]

    for step in setup_steps:
        print(f"> {step}")
        proc.stdin.write(step + "\n")
        proc.stdin.flush()
        time.sleep(1)

    # Give time for device to appear
    time.sleep(3)

    # Step 2: pairing + connection
    steps = [
        f"pair {addr}",
        f"trust {addr}",
        f"connect {addr}",
        "scan off"
    ]

    for step in steps:
        print(f"> {step}")
        proc.stdin.write(step + "\n")
        proc.stdin.flush()
        time.sleep(3)

    # Read output
    output = ""
    start = time.time()

    while time.time() - start < 12:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue

        print(line.strip())
        output += line

    proc.terminate()

    if any(x in output for x in [
        "Connection successful",
        "Connection established",
        "ServicesResolved: yes"
    ]):
        print("\nsuccess")
    else:
        print("\nfailure")


# ---------------------------
# MAIN
# ---------------------------
def main():
    devices = scan_devices()
    addr, name = select_device(devices)

    print(f"\nSelected: {name} [{addr}]")

    connect_device(addr)


if __name__ == "__main__":
    main()