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
from scapy.all import ARP, Ether, srp

# -----------------------------
# TV MAC ADDRESS
# -----------------------------

TV_MAC = "b0:41:1d:d4:c8:29".lower()

NETWORK = "192.168.29.0/24"
TV_IP = None

remote_enabled = False


# -----------------------------
# DISCOVER TV
# -----------------------------

def discover_tv():

    global TV_IP

    print("\nScanning network for TV...\n")

    arp = ARP(pdst=NETWORK)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")

    packet = ether / arp
    result = srp(packet, timeout=3, verbose=0)[0]

    for sent, received in result:

        ip = received.psrc
        mac = received.hwsrc.lower()

        print(f"{ip}  {mac}")

        if mac == TV_MAC:
            TV_IP = ip
            print("\nTV FOUND:", TV_IP)
            return

    print("TV not found.")
    exit()


# -----------------------------
# ADB COMMAND
# -----------------------------

def adb(cmd):
    subprocess.run(f"adb -s {TV_IP} {cmd}", shell=True)


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

    subprocess.run("adb start-server", shell=True)
    subprocess.run(f"adb connect {TV_IP}", shell=True)


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

    discover_tv()
    connect()

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