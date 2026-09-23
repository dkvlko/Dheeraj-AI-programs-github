#!/usr/bin/env python3
"""Python API for the Android TV remote service."""

import json
import socket

SOCKET_PATH = "/run/tvandroidremote/remote.sock"


class TVRemote:
    def __init__(self, socket_path=SOCKET_PATH, timeout=10):
        self.socket_path = socket_path
        self.timeout = timeout

    def send(self, command, **kwargs):
        request = {"command": command, **kwargs}

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

            data = bytearray()
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data.extend(chunk)
                if b"\n" in chunk:
                    break

        return json.loads(bytes(data).decode("utf-8"))

    def status(self):
        return self.send("status")

    def up(self):
        return self.send("up")

    def down(self):
        return self.send("down")

    def left(self):
        return self.send("left")

    def right(self):
        return self.send("right")

    def select(self):
        return self.send("select")

    def back(self):
        return self.send("back")

    def home(self):
        return self.send("home")

    def power(self):
        return self.send("power")

    def vol_up(self):
        return self.send("vol_up")

    def vol_down(self):
        return self.send("vol_down")

    def mute(self):
        return self.send("mute")

    def youtube(self):
        return self.send("youtube")

    def netflix(self):
        return self.send("netflix")

    def type_text(self, text):
        return self.send("type_text", text=text)

    def screenshot(self, filename=None):
        if filename:
            return self.send("screenshot", filename=filename)
        return self.send("screenshot")


if __name__ == "__main__":
    remote = TVRemote()
    print(remote.status())
