import json
import pyautogui
import asyncio
from fastapi import FastAPI,Request, WebSocket,WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import av
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack

import os
import re
import time

from ewmhlib import EwmhRoot, EwmhWindow
import subprocess
from fastapi.templating import Jinja2Templates
from aiortc.contrib.media import MediaPlayer
from pathlib import Path
import pyperclip



# 1. ENVIRONMENT SETUP
username = "dkvlko"
os.environ["DISPLAY"] = ":1"
os.environ["XAUTHORITY"] = f"/home/{username}/.Xauthority"
app = FastAPI()


PROJECT_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "web"))
pcs = set()


    

# Map common human inputs → pyautogui keys
KEY_MAP = {
    "CTRL": "ctrl",
    "CONTROL": "ctrl",
    "ALT": "alt",
    "SHIFT": "shift",
    "TAB": "tab",
    "ENTER": "enter",
    "ESC": "esc",
    "ESCAPE": "esc",
    "WIN": "win",
    "SUPER": "win"
}


def is_firefox(win):
    prop = win.getProperty("WM_CLASS")

    if not prop or not hasattr(prop, "value"):
        return False

    val = prop.value

    try:
        if isinstance(val, tuple):
            val = val[1]

        if isinstance(val, (list, tuple)):
            val = bytes(val).decode(errors="ignore")

        if isinstance(val, bytes):
            val = val.decode(errors="ignore")

        return "firefox" in val.lower()

    except Exception:
        return False

def focus_firefox(text):
    root = EwmhRoot()

    for win_id in root.getClientList():
        try:
            win = EwmhWindow(win_id)

            if is_firefox(win):
                title_prop = win.getProperty("_NET_WM_NAME")
                title = title_prop.value[1] if title_prop else "Unknown"

                print(f"Focusing: {title}")
                #focus_window(win_id)
                print("Win id : ",win_id)
                subprocess.run(["wmctrl", "-i", "-a", hex(win_id)])
                return True

        except Exception:
            continue

    print("Firefox window not found.")
    return False
    
def typeText(rtext):
    """
    Types the given text into the currently focused window.
    """

    if not rtext:
        return

    # Small delay to ensure target window is ready
    time.sleep(1)

    pyautogui.write(str(rtext), interval=0.02)  # interval controls typing speed

def normalize(key):
    if not key:
        return None
    key = key.strip().upper()
    return KEY_MAP.get(key, key.lower())


def executeKey(key1="", key2="", key3=""):
    keys = [normalize(k) for k in (key1, key2, key3) if normalize(k)]

    if not keys:
        print("No keys provided")
        return

    # small delay helps reliability when switching windows
    time.sleep(1)

    pyautogui.hotkey(*keys)

def execute_window_switch(command_text):
    """
    Parses string like 'CW:Alt+nTAB' and executes the key sequence.
    """
    # Regex explains: Look for 'CW:Alt+', capture digits (\d+), then 'TAB'
    match = re.search(r"CW:ALT\+(\d+)TAB", command_text)
    
    if match:
        # Extract the number 'n'
        n = int(match.group(1))
        print(f"Command detected! Switching {n} windows...")
        
        try:
            # Hold Alt throughout the entire sequence
            with pyautogui.hold('alt'):
                for i in range(n):
                    pyautogui.press('tab')
                    print(f"  Pulse {i+1} of {n}")
                    
                    # 1 second delay as requested
                    time.sleep(1) 
                    
            print("Sequence complete. Alt released.")
            
        except Exception as e:
            print(f"Error executing keys: {e}")
    else:
        print(f"Text '{command_text}' did not match CW format. Ignoring.")

#--------WebRTC--------------

# Custom Track to fix resolution / alignment issues
class ScreenCaptureTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.container = av.open(":1.0", format="x11grab", options={
            "video_size": "1366x768",
            "framerate": "15"
        })
        self.stream = self.container.streams.video[0]

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        for frame in self.container.decode(self.stream):
            new_frame = frame.to_image().resize((1024, 576))
            final_frame = av.VideoFrame.from_image(new_frame)
            final_frame.pts = pts
            final_frame.time_base = time_base
            return final_frame


@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ["failed", "closed"]:
            await pc.close()
            pcs.discard(pc)

    # Video track
    pc.addTrack(ScreenCaptureTrack())

    # Audio track
    try:
        audio_player = MediaPlayer("default", format="pulse", options={"sample_rate": "44100"})
        if audio_player.audio:
            pc.addTrack(audio_player.audio)
    except Exception as e:
        print(f"Audio error: {e}")

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

# -------- WebSocket --------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("WebSocket Connected")

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            action = msg.get("action")
            if action == "text_submit":
                text = msg.get("value")
                match = re.match(r'^([A-Za-z]+):', text)
                prefix=match.group(1)
                text = re.sub(r'^[A-Za-z]+:\s*', '', text)
                print("prefix : ",prefix)
                print("text : ",text)
                if prefix == "GPT":
                    focus_firefox(text)
                    executeKey("ALT", "1", "")
                    executeKey("ALT", "D", "")
                    typeText("https://chatgpt.com/")
                    executeKey("ENTER", "", "")
                    time.sleep(15)
                    typeText(text)
                    #executeKey("ENTER", "", "")
                    executeKey("TAB","","")
                    executeKey("TAB","","")
                    executeKey("ENTER","","")
                    time.sleep(15)
                    pyautogui.moveTo(700,380,0.3)
                    pyautogui.leftClick()
                    time.sleep(1)
                    pyautogui.rightClick()
                    time.sleep(1)
                    executeKey("A","","")
                    time.sleep(5)
                    pyautogui.rightClick()
                    time.sleep(1)
                    executeKey("C","","")
                    time.sleep(5)
                    ptext = pyperclip.paste()
                    await ws.send_text(ptext)
                    #print(ptext)
                    #if value == "CW:ALT+nTAB"
                    #    execute_window_switch(text)
                    #elif value == 
                    #anstext = getAnswerGPT(text)
                    #print(anstext)

    except WebSocketDisconnect:
        print("WebSocket disconnected by client")

    except asyncio.CancelledError:
        print("WebSocket task cancelled (server shutting down)")

    finally:
        print("Cleaning up WebSocket")

        try:
            await ws.close()
        except RuntimeError:
            pass

        print("Cleanup done")
# -------- UI --------
@app.get("/")
async def index():
    with open("web/control.html") as f:
        return HTMLResponse(f.read())


app.mount("/web", StaticFiles(directory="web"), name="web")

@app.on_event("shutdown")
async def on_shutdown():
    await asyncio.gather(*[pc.close() for pc in pcs])
