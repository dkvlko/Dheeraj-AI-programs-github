#!/usr/bin/env python3
"""
Command-line client for tvandroidremote.service.

Examples:
  python tvremote.py status
  python tvremote.py up
  python tvremote.py down
  python tvremote.py left
  python tvremote.py right
  python tvremote.py select
  python tvremote.py back
  python tvremote.py home
  python tvremote.py power
  python tvremote.py vol_up
  python tvremote.py vol_down
  python tvremote.py mute
  python tvremote.py youtube
  python tvremote.py netflix
  python tvremote.py type_text "Hello TV"
  python tvremote.py screenshot
"""

import json
import socket
import sys

SOCKET_PATH = "/run/tvandroidremote/remote.sock"


def send(request):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(10)
        sock.connect(SOCKET_PATH)
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
            if b"\n" in data:
                break

        response = json.loads(b"".join(chunks).decode("utf-8"))
        return response
    finally:
        sock.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2

    command = sys.argv[1]

    if command == "type_text":
        if len(sys.argv) < 3:
            print("Usage: tvremote.py type_text 'text'")
            return 2
        request = {"command": "type_text", "text": " ".join(sys.argv[2:])}

    elif command == "screenshot":
        request = {"command": "screenshot"}
        if len(sys.argv) >= 3:
            request["filename"] = sys.argv[2]

    else:
        request = {"command": command}

    try:
        response = send(request)
    except FileNotFoundError:
        print("Remote service is not running.")
        return 1
    except ConnectionRefusedError:
        print("Remote service refused the connection.")
        return 1
    except Exception as exc:
        print(f"Unable to contact remote service: {exc}")
        return 1

    print(json.dumps(response, indent=2))

    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
