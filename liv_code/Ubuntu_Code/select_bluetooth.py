#!/usr/bin/env python3
import subprocess
import sys
import re

def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def require_root():
    if run("id -u") != "0":
        print("❌ Please run this script as root (sudo).")
        sys.exit(1)

def get_adapters():
    output = run("hciconfig")
    adapters = []

    current = None
    for line in output.splitlines():
        if line.startswith("hci"):
            name = line.split(":")[0]
            current = {"name": name}
            adapters.append(current)
        elif "BD Address" in line and current:
            mac = re.search(r"BD Address:\s+([0-9A-F:]+)", line)
            if mac:
                current["mac"] = mac.group(1)

    for ad in adapters:
        try:
            info = run(f"udevadm info --query=all --name=/sys/class/bluetooth/{ad['name']} | grep ID_VENDOR_FROM_DATABASE")
            ad["vendor"] = info.split("=", 1)[1]
        except:
            ad["vendor"] = "Unknown"

    return adapters

def show_menu(adapters):
    print("\nDetected Bluetooth adapters:\n")
    for i, ad in enumerate(adapters, 1):
        print(f"{i}. {ad['name']} | {ad.get('vendor')} | {ad.get('mac')}")

    choice = input("\nSelect adapter number to KEEP active: ")
    if not choice.isdigit() or not (1 <= int(choice) <= len(adapters)):
        print("❌ Invalid selection")
        sys.exit(1)

    return adapters[int(choice) - 1]

def apply_choice(adapters, keep):
    print(f"\n✅ Keeping {keep['name']} active")
    for ad in adapters:
        if ad["name"] != keep["name"]:
            print(f"⛔ Disabling {ad['name']}")
            run(f"hciconfig {ad['name']} down")

def reboot_prompt():
    ans = input("\nReboot now to apply changes permanently? (y/n): ").lower()
    if ans == "y":
        print("🔄 Rebooting...")
        subprocess.call("reboot")
    else:
        print("ℹ️ Reboot skipped. Changes will revert after reboot.")

def main():
    require_root()
    adapters = get_adapters()

    if len(adapters) < 2:
        print("ℹ️ Only one Bluetooth adapter found. Nothing to switch.")
        sys.exit(0)

    keep = show_menu(adapters)
    apply_choice(adapters, keep)
    reboot_prompt()

if __name__ == "__main__":
    main()
