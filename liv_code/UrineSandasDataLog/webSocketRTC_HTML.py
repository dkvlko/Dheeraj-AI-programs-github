import json
import pyautogui
import asyncio
from fastapi import FastAPI,Request, WebSocket,WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import av
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack

from fastapi.templating import Jinja2Templates
from aiortc.contrib.media import MediaPlayer
from pathlib import Path
app = FastAPI()

PROJECT_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "web"))
pcs = set()

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

    try :
     # Send position immediately on connect (onload)
        x, y = pyautogui.position()
        print("Immediate position :",x," ",y)
        await ws.send_text(json.dumps({
                "action": "update_position",
                "x": x,
                "y": y
                }))
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            action = msg.get("action")

            if action == "move":

                dx = msg.get("dx", 0)
                dy = msg.get("dy", 0)
                mode = msg.get("mode")
                # --- get current position ---
                x, y = pyautogui.position()
                screen_w, screen_h = pyautogui.size()
                
                if mode == "relative":
                    # --- clamp to avoid corners ---
                    new_x = max(10, min(screen_w - 10, x + dx))
                    new_y = max(10, min(screen_h - 10, y + dy))
                elif mode == "absolute":
                    new_x = max(10, min(screen_w - 10, dx))
                    new_y = max(10, min(screen_h - 10, dy))

                pyautogui.moveTo(new_x, new_y)

                x2, y2 = pyautogui.position()
                await ws.send_text(json.dumps({
                    "action": "update_position",
                    "x": x2,
                    "y": y2,
                    "mode": mode
                }))
                #print(f"[AFTER] x={x2}, y={y2}")
            elif action == "left_click":
                pyautogui.click()

            elif action == "right_click":
                pyautogui.click(button="right")
    except WebSocketDisconnect:
        print("WebSocket disconnected by client")

    except asyncio.CancelledError:
        print("WebSocket task cancelled (server shutting down)")

    finally:
        print("Cleaning up WebSocket")

        try:
            await ws.close()
        except RuntimeError:
            # already closed → ignore
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
