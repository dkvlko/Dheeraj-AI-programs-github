"""
Advanced Android TV Remote with Auto IP Discovery

Features
--------
1. Automatically discovers the TV IP from its MAC address
2. Connects to Android TV via ADB
3. Keyboard based remote control

Controls
--------
Arrow keys  -> Navigate
Enter       -> Select
Backspace   -> Back
h           -> Home
p           -> Power toggle
+           -> Volume up
-           -> Volume down
m           -> Mute
y           -> Launch YouTube
n           -> Launch Netflix
s           -> Screenshot
t           -> Type text
q           -> Quit

Requirements
------------
pip install scapy keyboard
"""

import subprocess
import keyboard
import datetime
from scapy.all import ARP, Ether, srp

# --------------------------------
# YOUR TV MAC ADDRESS
# --------------------------------

TV_MAC = "b0:41:1d:d4:c8:29".lower()

# --------------------------------
# NETWORK RANGE (JIO ROUTER)
# --------------------------------

NETWORK = "192.168.29.0/24"

TV_IP = None


# --------------------------------
# DISCOVER DEVICE BY MAC
# --------------------------------

def discover_tv():

    global TV_IP

    print("\nScanning network to find TV...\n")

    arp = ARP(pdst=NETWORK)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")

    packet = ether / arp

    result = srp(packet, timeout=3, verbose=0)[0]

    for sent, received in result:

        ip = received.psrc
        mac = received.hwsrc.lower()

        print(f"Found device {ip}   {mac}")

        if mac == TV_MAC:
            TV_IP = ip
            print("\nTV FOUND")
            print("IP:", TV_IP)
            return

    print("\nTV not found on network.")
    exit()


# --------------------------------
# ADB COMMAND
# --------------------------------

def adb(cmd):
    command = f"adb -s {TV_IP} {cmd}"
    subprocess.run(command, shell=True)


def key(code):
    adb(f"shell input keyevent {code}")


# --------------------------------
# NAVIGATION
# --------------------------------

def up():
    key(19)

def down():
    key(20)

def left():
    key(21)

def right():
    key(22)

def select():
    key(66)

def back():
    key(4)

def home():
    key(3)


# --------------------------------
# POWER
# --------------------------------

def power():
    key(26)


# --------------------------------
# VOLUME
# --------------------------------

def vol_up():
    key(24)

def vol_down():
    key(25)

def mute():
    key(164)


# --------------------------------
# APPS
# --------------------------------

def youtube():
    adb("shell am start -n com.google.android.youtube.tv/.MainActivity")

def netflix():
    adb("shell am start -n com.netflix.ninja/.MainActivity")


# --------------------------------
# SCREENSHOT
# --------------------------------

def screenshot():

    filename = f"tvshot_{datetime.datetime.now().strftime('%H%M%S')}.png"

    adb("shell screencap -p /sdcard/screen.png")
    adb(f"pull /sdcard/screen.png {filename}")

    print("Saved screenshot:", filename)


# --------------------------------
# TEXT INPUT
# --------------------------------

def type_text():

    text = input("Enter text: ")
    text = text.replace(" ", "%s")

    adb(f"shell input text {text}")


# --------------------------------
# CONNECT TO TV
# --------------------------------

def connect():

    print("\nConnecting to TV via ADB...\n")

    subprocess.run("adb start-server", shell=True)
    subprocess.run(f"adb connect {TV_IP}", shell=True)


# --------------------------------
# HELP
# --------------------------------

def help_menu():

    print("\n========= ANDROID TV REMOTE =========\n")

    print("Arrow keys -> Navigate")
    print("Enter      -> Select")
    print("Backspace  -> Back")
    print("h          -> Home")

    print("\nPower")
    print("p          -> Power")

    print("\nVolume")
    print("+          -> Volume Up")
    print("-          -> Volume Down")
    print("m          -> Mute")

    print("\nApps")
    print("y          -> YouTube")
    print("n          -> Netflix")

    print("\nUtilities")
    print("s          -> Screenshot")
    print("t          -> Type text")

    print("\nq          -> Quit\n")


# --------------------------------
# MAIN
# --------------------------------

def main():

    discover_tv()

    connect()

    help_menu()

    keyboard.add_hotkey("up", up)
    keyboard.add_hotkey("down", down)
    keyboard.add_hotkey("left", left)
    keyboard.add_hotkey("right", right)

    keyboard.add_hotkey("enter", select)
    keyboard.add_hotkey("backspace", back)

    keyboard.add_hotkey("h", home)

    keyboard.add_hotkey("p", power)

    keyboard.add_hotkey("+", vol_up)
    keyboard.add_hotkey("-", vol_down)
    keyboard.add_hotkey("m", mute)

    keyboard.add_hotkey("y", youtube)
    keyboard.add_hotkey("n", netflix)

    keyboard.add_hotkey("s", screenshot)
    keyboard.add_hotkey("t", type_text)

    print("Remote ready. Press q to quit.\n")

    keyboard.wait("q")


if __name__ == "__main__":
    main()